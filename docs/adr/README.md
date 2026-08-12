# Architecture Decision Records

Every significant architectural decision gets one short, numbered ADR.
Never delete an ADR  supersede it with a new one.

## Index

| # | Title | Status |
|---|-------|--------|
| [0001](0001-use-feature-based-architecture.md) | Use feature-based architecture | Accepted |
| [0002](0002-service-repository-selector-layers.md) | Service / Repository / Selector layers | Accepted |
| [0003](0003-isolate-ai-behind-provider-factory.md) | Isolate AI behind a provider factory | Accepted |
| [0004](0004-infrastructure-package.md) | Infrastructure package for external services | Accepted |
| [0005](0005-api-only-backend.md) | API-only backend with a Next.js frontend | Accepted |
| [0006](0006-stateless-auth-tokens.md) | Stateless tokens for verification and reset | Accepted |
| [0007](0007-session-auth-for-phase-1.md) | Session cookies behind a credential seam | Accepted |
| [0008](0008-cross-app-model-references.md) | Cross-app model references | Accepted |
| [0009](0009-courses-lessons-boundary.md) | The courses ↔ lessons boundary | Accepted |
| [0010](0010-question-bank-and-quiz-boundary.md) | The question bank and the quiz ↔ question boundary | Accepted |
| [0011](0011-review-target-architecture.md) | Review target architecture (explicit FKs over GFK) | Accepted |
| [0012](0012-progress-domain.md) | The progress domain (extracted from lessons) | Accepted |
| [0013](0013-ai-assistant-foundation.md) | AI assistant foundation (providers, prompts, Thai-first) | Accepted |
| [0014](0014-certificates-and-achievements.md) | Certificates & achievements (issuance, verification, badges) | Accepted |
| [0015](0015-gamification-foundation.md) | Gamification foundation (XP ledger, derived levels, streaks) | Accepted |
| [0016](0016-notifications-as-a-push-sink.md) | Notifications as a push sink (post-commit, best-effort, snapshot) | Accepted (amended by 0017) |
| [0017](0017-community-gallery-and-qa.md) | Community content: gallery + Q&A (references, lifecycles, accepted answer) | Accepted |
| [0018](0018-recommendation-and-substitution.md) | Recommendation & ingredient substitution (pure consumer, deterministic, no tables) | Accepted |
| [0019](0019-rewards-economy.md) | Rewards economy (identified-fact pull, immutable ledger, DB-level idempotency) | Accepted |
| [0020](0020-profile-personalization.md) | Profile & personalization (taxonomy M2M backfill, Thai-first language, derived completion, settings composition) | Accepted |
| [0021](0021-course-list-search-and-stored-aggregates.md) | Course list search and stored aggregates (duration, rating) | Accepted |
| [0022](0022-admin-surface-identity-flag.md) | The admin surface reads one flag; authorization stays server-side | Accepted |
| [0023](0023-recipe-id-in-read-payloads.md) | Recipe read payloads carry the primary key | Accepted |
| [0024](0024-badge-catalogue-and-level-span.md) | The badge catalogue is readable; the level curve is stated | Accepted |
| [0025](0025-threat-watch-and-client-guard.md) | Threat watching, and the honest limits of a client-side guard | Accepted |
| [0026](0026-legal-names-consent-and-documents.md) | Legal names, PDPA consent, and editable legal documents | Accepted (amended by 0035) |
| [0027](0027-back-office-admin-api.md) | The back-office admin API | Accepted |
| [0028](0028-cross-user-learning-and-staff-instrumentation.md) | Cross-user learning views and staff instrumentation | Accepted |
| [0029](0029-certificate-template-designer.md) | The certificate template designer | Accepted |
| [0030](0030-notification-campaigns.md) | Notification campaigns, templates and audiences | Accepted (amended by 0036) |
| [0031](0031-staff-account-actions.md) | The user-management workspace and staff account actions | Accepted |
| [0032](0032-gallery-interactions.md) | Community interactions: likes and comments | Accepted |
| [0033](0033-qa-board-signals.md) | What a question board has to tell you before you click | Accepted |
| [0034](0034-google-sign-in.md) | Google sign-in, and the first table authentication owns | Accepted |
| [0035](0035-legal-name-at-issuance.md) | The legal name is asked for where it is used | Accepted |
| [0036](0036-announcement-kinds-and-click-receipts.md) | Announcement kinds are a closed set, and clicks are a floor | Accepted |

ADR 0005 changes the delivery model assumed by 0001–0004: the layering in 0002
and the boundaries in 0003–0004 still hold, but templates and static files are
no longer part of a feature app.

## Creating a New ADR

Copy [template.md](template.md) to `NNNN-short-kebab-title.md` and fill it in.
