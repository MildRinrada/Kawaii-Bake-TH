"""JWT credential issuer.

Not implemented in Phase 1. This file marks the seam; adding JWT means writing
``JwtCredentialIssuer`` here and pointing ``settings.AUTH_CREDENTIAL_ISSUER``
at it. No view, serializer, service, repository, selector or URL changes.

Sketch of the eventual implementation::

    class JwtCredentialIssuer:
        def issue(self, *, request, user, remember):
            access, refresh = mint_tokens(user)
            return IssuedCredential(body={"access": access})
            # `refresh` is attached by apply() as an httpOnly cookie 
            # never returned in the body, and never stored in localStorage.

        def apply(self, *, response, credential):
            response.set_cookie("refresh", ..., httponly=True, secure=True,
                                samesite="Lax")

Two decisions to make at that point, both already routed:

* ``/api/v1/auth/token/refresh/`` is reserved in the URL conf.
* Real logout requires a revocation list. Without one, an access token stays
  valid until it expires, so ``revoke()`` would be a client-side lie  which is
  precisely why Phase 1 uses sessions instead.
"""

from __future__ import annotations
