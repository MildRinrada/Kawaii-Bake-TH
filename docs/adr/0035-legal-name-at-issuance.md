# ADR 0035 - The legal name is asked for where it is used

- **Status:** accepted
- **Date:** 2026-08-12
- **Phase:** Sign-up rework
- **Amends:** [0026](0026-legal-names-consent-and-documents.md) decision 1

## Context

ADR 0026 made `first_name` / `last_name` mandatory at registration so
that certificates would never print a handle. That solved the credential
problem and created a smaller one: every visitor pays for it, and most
never claim a certificate. Sign-up asked for five fields where three
identify an account; the design review of the page named those two as
the first thing to cut.

Nothing about the credential requirement changed - a certificate naming
"@mildbakes" is still not a credential. What changed is *when* the
question is asked.

## Decisions

### 1. Registration collects identity only

Email, handle, password, consent. The registration serializer no longer
declares the name fields at all, so - `StrictSerializer` rejecting
unknown keys - sending them is a 400 rather than a silent write. New
accounts start with an empty legal name, which the model already allowed
(`blank=True`, kept for pre-rule accounts under 0026).

### 2. Issuance asks, once, and remembers

`POST /courses/{slug}/certificate/` takes an optional
`{first_name, last_name}`. With no stored name and none in the body it
answers **409 `legal_name_required`**; the client asks the learner and
repeats the request. The answer is written to the account
(`user_service.set_legal_name`), so the second certificate never asks.

A submitted name never overwrites a stored one. Certificates already
issued carry the stored name in an immutable snapshot, and letting a
later request diverge from it would produce two credentials naming two
different people for one learner.

`last_name` may be blank - a mononym is a real kind of name - but the two
cannot both be empty.

### 3. The snapshot chain loses its fallbacks

`_printable_name` was `legal name → display name → username`. The middle
and last links existed for accounts that predated 0026; with the gate in
decision 2 they are unreachable for any new issuance, and keeping them
would quietly re-open the exact hole 0026 closed (a nickname-shaped
display name printed as a credential). It is now the legal name or the
409.

## Consequences

- Sign-up is three fields plus consent. PDPA consent (0026 decision 2) is
  untouched: still explicit, still stamped at registration.
- The frontend asks for the name in a dialog on the certificate card, and
  handles `legal_name_required` from the server as the same question
  arriving the other way round.
- Accounts created through Google (ADR 0034) are in exactly the same
  position: no legal name until a certificate needs one.
- Three tests in `apps/certificates` that asserted the fallback chain now
  assert the refusal instead; `test_registration_does_not_ask_for_a_legal_name`
  asserts both halves of decision 1.

## Alternatives considered

**Ask at first enrolment.** Closer to the moment a name matters, but
enrolling is browsing behaviour - it is free, reversible, and most
enrolments never finish. It would move the toll rather than remove it.

**Keep the fields, make them optional.** Optional fields on a sign-up
form are still fields: read, considered, skipped. And a name collected
without saying what it is for is precisely the PDPA smell 0026 set out to
fix.
