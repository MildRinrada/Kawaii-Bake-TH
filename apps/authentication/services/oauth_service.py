"""OAuth / social sign-in.

The seams ADR 0007 left for this are the ones being used: ``api/credentials/``
is still the only place a session is established (this module returns a user
and lets the view issue the credential), and accounts created here get
``set_unusable_password()``, which ``user_selector.get_for_password_reset``
already excludes  so a social-only account can never be sent reset mail for
a password it does not have.

The one thing the flow could not avoid is a provider-link table; see
``SocialAccount`` and ADR 0007.

**What is trusted, and why.** Google's ID token is verified by Google
(``tokeninfo``), and this module then checks the three claims that make a
verified token *ours*: the audience is this deployment's client id, the
issuer is Google, and the address is one Google says it confirmed. The
subject id  never the email  is what identifies the account on every
later sign-in.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.authentication.constants import (
    GOOGLE_ISSUERS,
    GOOGLE_TOKENINFO_URL,
    OAUTH_HTTP_TIMEOUT_SECONDS,
    SocialProvider,
)
from apps.authentication.exceptions import (
    AccountDisabledError,
    SocialAuthFailedError,
    SocialAuthUnavailableError,
    SocialEmailUnverifiedError,
)
from apps.authentication.models import SocialAccount
from apps.authentication.permissions.rate_limit_permissions import (
    clear_login_rate_limit,
    enforce_login_rate_limit,
)
from apps.users.models import User
from apps.users.selectors import user_selector
from apps.users.services import user_service
from apps.users.validators.user_validator import normalize_email, validate_username

logger = logging.getLogger("kawaiibake.security")

# tokeninfo returns the flag as the *string* "true"; the JWT payload
# spells it as a real boolean. Accept both, and nothing else - a missing
# claim must never read as verified. (`1` is absent on purpose: it is the
# same set member as `True` in Python.)
TRUTHY = {"true", "True", True, "1"}


def _fetch_token_info(credential: str) -> dict[str, Any]:
    """Ask Google what this ID token contains, if anything.

    Args:
        credential: The raw ID token from Google Identity Services.

    Returns:
        The decoded claims.

    Raises:
        SocialAuthFailedError: If Google rejects the token or is unreachable.
    """
    query = urllib.parse.urlencode({"id_token": credential})
    request = urllib.request.Request(  # noqa: S310 - fixed https constant
        f"{GOOGLE_TOKENINFO_URL}?{query}",
        headers={"Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(  # noqa: S310 - fixed https constant
            request, timeout=OAUTH_HTTP_TIMEOUT_SECONDS
        ) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        # A 400 from tokeninfo *is* "this token is not valid", and a
        # network failure is indistinguishable from it to the caller.
        logger.info("social_auth_failed provider=google reason=%s", type(exc).__name__)
        raise SocialAuthFailedError from exc


def _derive_username(*, email: str) -> str:
    """Invent a free handle for an account that never chose one.

    Social sign-up has no handle field  the provider does not have the
    concept  so one is derived from the address and made unique. The
    result still passes the same validator a typed handle would, which is
    what keeps reserved words ("admin@…") out.

    Args:
        email: The verified address from the provider.

    Returns:
        An unclaimed, valid handle.
    """
    base = "".join(
        char for char in email.split("@")[0].lower() if char.isalnum() or char in "-_"
    ).strip("-_")
    base = (base or "baker")[:24]
    if len(base) < 3:
        base = f"{base}baker"

    for suffix in ("", *(str(number) for number in range(1, 1000))):
        candidate = f"{base}{suffix}"
        try:
            validate_username(candidate)
        except ValidationError:
            # Malformed or reserved ("admin") - the next suffix escapes it.
            continue
        if not user_selector.username_exists(username=candidate):
            return candidate

    # 1000 collisions on one mail name is not a thing that happens; the
    # unique constraint would still be the arbiter if it did.
    raise SocialAuthFailedError


def _verified_google_claims(credential: str) -> dict[str, Any]:
    """Verify a Google credential and return the claims worth trusting.

    Raises:
        SocialAuthUnavailableError: If no client id is configured.
        SocialAuthFailedError: If the token is not a valid token for us.
        SocialEmailUnverifiedError: If Google has not confirmed the address.
    """
    client_id = settings.GOOGLE_OAUTH_CLIENT_ID
    if not client_id:
        raise SocialAuthUnavailableError

    claims = _fetch_token_info(credential)

    # Audience: a token minted for a *different* application is a valid
    # Google token and must still be refused - this is the check that
    # stops one being replayed here.
    if claims.get("aud") != client_id:
        logger.info("social_auth_failed provider=google reason=audience")
        raise SocialAuthFailedError
    if claims.get("iss") not in GOOGLE_ISSUERS:
        logger.info("social_auth_failed provider=google reason=issuer")
        raise SocialAuthFailedError
    if not claims.get("sub"):
        raise SocialAuthFailedError
    if not claims.get("email"):
        raise SocialEmailUnverifiedError
    if claims.get("email_verified") not in TRUTHY:
        logger.info("social_auth_failed provider=google reason=email_unverified")
        raise SocialEmailUnverifiedError
    return claims


def sign_in_with_google(*, credential: str, client_ip: str = "") -> tuple[User, bool]:
    """Sign a visitor in with a Google ID token, creating the account if new.

    Three cases, in this order:

    1. **Known subject** - the link row decides, and nothing else is read.
    2. **Known address, first Google sign-in** - the provider states it
       verified the address, so the accounts are the same person and the
       link is created. This is the only place email is matched.
    3. **Neither** - a new account: verified email, unusable password, a
       derived handle, and consent stamped, because pressing the button
       under a line that says so *is* the consent event.

    Args:
        credential: The ID token from Google Identity Services.
        client_ip: Caller IP, used for throttling.

    Returns:
        The signed-in user and whether this call created the account.

    Raises:
        RateLimitedError: If too many sign-in attempts came from this address.
        SocialAuthUnavailableError: If Google sign-in is not configured.
        SocialAuthFailedError: If the credential does not check out.
        SocialEmailUnverifiedError: If Google has not confirmed the address.
        AccountDisabledError: If the linked account is deactivated.
    """
    claims = _verified_google_claims(credential)
    subject = claims["sub"]
    email = normalize_email(claims["email"])

    # Throttled on the same counter as password sign-in: the button is a
    # sign-in path, and a provider token is still an unauthenticated POST.
    enforce_login_rate_limit(email=email, client_ip=client_ip)

    link = (
        SocialAccount.objects.filter(
            provider=SocialProvider.GOOGLE, provider_uid=subject
        )
        .select_related("user")
        .first()
    )
    created = False

    if link is not None:
        user = link.user
    else:
        user = user_selector.get_by_email(email=email)
        if user is None:
            with transaction.atomic():
                user = user_service.create_account(
                    email=email,
                    username=_derive_username(email=email),
                    password=None,
                    is_email_verified=True,
                    email_verified_at=timezone.now(),
                    terms_accepted_at=timezone.now(),
                )
                created = True
        try:
            link = SocialAccount.objects.create(
                user=user,
                provider=SocialProvider.GOOGLE,
                provider_uid=subject,
                email=email,
            )
        except IntegrityError:
            # Two tabs, one first sign-in: the row that won is the link.
            link = SocialAccount.objects.select_related("user").get(
                provider=SocialProvider.GOOGLE, provider_uid=subject
            )
            user = link.user
            created = False

    if not user.is_active:
        logger.info("social_auth_failed reason=disabled user_id=%s", user.pk)
        raise AccountDisabledError

    link.last_login_at = timezone.now()
    link.save(update_fields=["last_login_at"])
    clear_login_rate_limit(email=email, client_ip=client_ip)
    user_service.record_login(user=user)
    logger.info(
        "social_auth_succeeded provider=google user_id=%s created=%s ip=%s",
        user.pk,
        created,
        client_ip,
    )
    return user, created
