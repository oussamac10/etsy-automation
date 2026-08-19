# Phase 9: Etsy Integration & Draft Creation

## Status: COMPLETE ✅

**Branch:** `feature/phase-9-etsy-integration`

---

## 1. Overview & Objectives

Phase 9 implements the complete, end-to-end official Etsy Open API v3 integration for `etsy-automation`:
1. **OAuth 2.0 PKCE Shop Connection:**
   - 1-click authorization flow using PKCE code verifier / SHA-256 challenge.
   - Redis-backed temporary state management (`etsy:oauth_state:{state}`) with 600-second TTL.
   - Automatic single-use consumption and CSRF verification.
   - No seller API keys or access tokens manually entered or pasted.
2. **Encrypted Token Security & Auto-Refresh:**
   - Fernet AES-128-CBC + HMAC encrypted storage in PostgreSQL `shop_connections` table.
   - Transparent key rotation support with `key_version`.
   - Proactive token refresh with 5-minute pre-expiration buffer.
3. **Idempotent Draft Listing Pipeline:**
   - Strict `state: "draft"` guarantee — **NEVER** activates or publishes listings automatically.
   - Safe shop-scoped listing creation (`POST /v3/application/shops/{shop_id}/listings`).
   - Mockup preview image uploads ordered deterministically (`is_cover` first, then by `listing_order`).
   - Digital download ZIP package upload (`POST /v3/application/shops/{shop_id}/listings/{listing_id}/files`).
   - Resilient retry and crash recovery (reuses existing Etsy listing ID and skips already-uploaded images).
4. **Owner Notifications & Control:**
   - Real-time frontend progress tracking in Nuxt 3 with step-by-step dispatch indicators.
   - Direct link to Etsy Shop Manager (`https://www.etsy.com/your/shops/me/listing-editor/edit/{listing_id}`).
   - Proactive Telegram bot notification with direct link and zero publish buttons.

---

## 2. Architecture & Flow

```
                      +------------------------------------------+
                      |         Owner in Web App / Nuxt 3        |
                      +------------------------------------------+
                                       |
              +------------------------+------------------------+
              | (Settings: Connect)                             | (Workflow: Create Draft)
              v                                                 v
  +-----------------------+                         +-----------------------+
  |  OAuth 2.0 PKCE Flow  |                         |  Listing Dispatcher   |
  |  - Generate Verifier  |                         |  - Pre-dispatch check |
  |  - Redirect to Etsy   |                         |  - Token auto-refresh |
  |  - Single-use State   |                         |  - S3 -> Etsy Streams |
  +-----------------------+                         +-----------------------+
              |                                                 |
              v                                                 v
  +-----------------------+                         +-----------------------+
  | Encrypted Persistence |                         |  Etsy Open API v3     |
  | - Fernet AES-128-CBC  |                         |  - POST listings      |
  | - shop_connections   |                         |    (state="draft")    |
  | - Key Versioning      |                         |  - POST images        |
  +-----------------------+                         |  - POST files (ZIP)   |
                                                    +-----------------------+
                                                                |
                                                                v
                                                    +-----------------------+
                                                    |  Telegram & Nuxt UI   |
                                                    |  - Direct Shop Link   |
                                                    |  - NO Publish Button  |
                                                    +-----------------------+
```

---

## 3. Implemented Components

### 3.1 Database & Persistence
- **Model:** `backend/app/infrastructure/models/shop_connection.py` (`ShopConnection` table: `shop_connections`).
- **Listing Columns:** Added `etsy_shop_id`, `etsy_listing_id`, `etsy_listing_url`, `etsy_state`, `etsy_image_ids`, `etsy_file_id`, `etsy_dispatch_status`, `etsy_draft_created_at`, `etsy_last_synced_at`, `etsy_failure_reason` to `ListingDraft`.
- **Migration:** `backend/migrations/versions/0011_phase_9_etsy_shop_connection.py`.
- **Repository:** `backend/app/infrastructure/repositories/shop_connection.py` (`SqlShopConnectionRepository`).
- **UnitOfWork:** `backend/app/application/unit_of_work.py` (`uow.shop_connections`).

### 3.2 Provider & HTTP Client
- **Provider Port:** `backend/app/ports/providers.py` (`EtsyGateway` protocol & DTOs).
- **Live HTTP Adapter:** `backend/app/providers/etsy.py` (`EtsyProvider`):
  - Strict `state: "draft"` parameter in listing creation payload.
  - HTTP 429 rate limit backoff and retries.
  - Multipart image and file binary upload streams with filename/content-type headers.
- **Offline Fake Adapter:** `backend/app/providers/fake.py` (`FakeEtsyProvider`) for hermetic testing.

### 3.3 Application Services & Workers
- **OAuth & Token Management:** `backend/app/application/etsy_auth.py` (`generate_oauth_url`, `handle_oauth_callback`, `get_valid_etsy_token`).
- **Draft Creation Pipeline:** `backend/app/application/etsy_draft.py` (`validate_pre_dispatch`, `execute_etsy_draft_pipeline`).
- **Worker Task:** `workers/general-worker/worker/etsy.py` & `workers/general-worker/worker/tasks.py` (`create_etsy_draft_task`).
- **Telegram Notification:** `backend/app/application/telegram.py` (`send_etsy_draft_created_notification`).

### 3.4 API Routes
- `GET /api/v1/auth/etsy/connect` — Returns PKCE authorization URL.
- `GET /api/v1/auth/etsy/callback` — Exchanges authorization code, fetches shop ID/name, encrypts tokens, redirects to frontend settings.
- `GET /api/v1/integrations/etsy` — Returns safe status (connected, shop name, token health, granted scopes).
- `DELETE /api/v1/integrations/etsy` — Disconnects shop and deletes credentials.
- `POST /api/v1/workflows/{id}/etsy/draft` — Queues draft creation via Outbox.
- `GET /api/v1/workflows/{id}/etsy/status` — Returns draft dispatch status and Etsy listing ID.

### 3.5 Frontend (Nuxt 3 / Vue 3)
- **Types:** `frontend/types/etsy.ts` & `frontend/types/listing.ts`.
- **Composable:** `frontend/composables/useEtsy.ts`.
- **Components:**
  - `frontend/components/settings/EtsyConnectionCard.vue` integrated into `frontend/pages/settings.vue`.
  - `frontend/components/workflow/listing/EtsyDraftCard.vue` integrated into `frontend/components/workflow/listing/WorkflowListingTab.vue`.

---

## 4. Verification & Testing

| Test Category | Suite | Passed | Description |
|:---|:---|:---:|:---|
| Backend OAuth & Tokens | `test_etsy_auth.py` | 8/8 | PKCE verifier/challenge, state validation, token encryption, and auto-refresh |
| Backend Live Provider | `test_etsy_provider.py` | 6/6 | Etsy HTTP adapter, draft state enforcement, image/file multipart streams |
| Backend Draft Pipeline | `test_etsy_draft.py` | 3/3 | Pre-dispatch validation, pipeline execution, Telegram notification |
| Backend Idempotency | `test_etsy_idempotency.py` | 1/1 | Crash recovery, reuse of existing listing ID, deduplication of uploaded mockups |
| Backend API Routes | `test_etsy_routes.py` | 6/6 | Connect, callback redirect, status, disconnect, and draft trigger |
| Database Schema Docs | `test_schema_docs.py` | 1/1 | Schema documentation synchronization with SQLAlchemy models |
| Full Backend Suite | `backend/tests/` | 332/332 | Complete Python unit & domain test suite |
| Frontend Workspace | `pnpm test` | 162/162 | Domain, image-pipeline, frontend, and image-worker Vitest suites |
| Frontend Typecheck | `pnpm typecheck` | 0 errors | `vue-tsc --noEmit` & `nuxt prepare` |

---

## 5. Non-Negotiable Safety Checklist

- [x] **No Publish API:** The application codebase contains NO endpoint to publish or activate an Etsy listing.
- [x] **Strict Draft State:** All Etsy listing creation payloads strictly send `"state": "draft"`.
- [x] **No Automatic Publishing Workers:** Workers only create drafts, upload mockups, and attach digital ZIP files.
- [x] **No Publishing via Telegram:** Telegram notifications provide only a direct link to Etsy Shop Manager with zero publish actions.
- [x] **Encrypted Credentials:** Tokens are encrypted with AES-128-CBC + HMAC key versioning and never returned in API payloads.
