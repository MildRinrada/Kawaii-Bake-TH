"""The authentication app defines exactly one model, and only one.

Account data lives in ``apps.users``. The two flows that would normally need
their own tables  email verification and password reset  use stateless,
signed tokens instead:

* Tokens are HMACs over user state, keyed by ``SECRET_KEY``. They self-invalidate
  when the state they hash changes, so there is nothing to store or clean up.
* See ``apps/authentication/tokens/`` and ``docs/adr/0006-stateless-auth-tokens.md``.

Sessions are stored by ``django.contrib.sessions``, which owns its own table.

``SocialAccount`` is the documented exception ADR 0007 reserved: a provider
sign-in cannot be verified from a signed value we issued, because we did not
issue it. Somebody has to remember that *this* Google subject is *that*
account, and no stateless trick removes the need.
"""

from __future__ import annotations

from django.db import models

from apps.authentication.constants import SocialProvider


class SocialAccount(models.Model):
    """A link between one identity provider's subject and one local account.

    The provider's subject id (``sub``) is the identifier, never the email:
    an email address can change hands at the provider, and matching on it
    would hand the new owner the old owner's account. Email is matched
    exactly once  when *first* linking a provider to an existing local
    account  and only when the provider states it verified the address.

    One account may link several providers; one provider subject links to
    exactly one account, which is what the unique constraint says.
    """

    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )
    provider = models.CharField(max_length=20, choices=SocialProvider.choices)
    provider_uid = models.CharField(max_length=255)
    # What the provider called this identity when it was linked. Kept for
    # the account screen ("signed in with Google as ..."), never used to
    # find a user.
    email = models.EmailField(max_length=254, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "auth_social_account"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_uid"],
                name="uniq_social_account_provider_uid",
            )
        ]
        indexes = [models.Index(fields=["user", "provider"])]

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_uid} -> user {self.user_id}"
