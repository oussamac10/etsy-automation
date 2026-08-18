# Etsy PNG Automation — Project Roadmap & Task Tracker

Current state, completed milestones, and granular task breakdowns for upcoming phases. Detailed specifications live in [`docs/PHASES.md`](docs/PHASES.md) and progress evidence in [`docs/progress/`](docs/progress/).

---

## 🎯 Current Status Overview

- [x] **Phase 1 — Foundation:** Complete (`docs/progress/phase-1-foundation.md`)
- [x] **Phase 2 — Domain and persistence:** Complete (`docs/progress/phase-2-domain-database.md`)
- [x] **Phase 3 — Authentication and settings:** Complete (`docs/progress/phase-3-auth-settings.md`)
- [x] **Phase 4 — Telegram remote control:** Complete (`docs/progress/phase-4-telegram-remote-control.md`)
- [x] **Phase 5 — Idea input, research, and Gate 1 approval:** Complete (`docs/progress/phase-5-idea-research.md`)
- [x] **Phase 6 — Artwork generation and Gate 2 approval:** Complete (`docs/progress/phase-6-artwork-generation-approval.md`)
- [x] **Phase 7 — PNG production pipeline:** Complete (`docs/progress/phase-7-png-production-pipeline.md`)
- [ ] **Phase 8 — SEO, IP risk review, and download package:** Next Active Milestone
- [ ] **Phase 9 — Etsy integration:** Planned
- [ ] **Phase 10 — Deployment, scheduling, and monitoring:** Planned
- [ ] **Phase 11 — Post-publishing profit intelligence & winner expansion:** Future, start only after real Etsy sales data exists
- [ ] **Phase 12 — Optional SaaS expansion:** Future

---

## Completed Phases

### Phase 1 — Foundation ✅

- [x] Monorepo: pnpm workspaces (`frontend`, `workers/image-worker`, `packages/*`) plus two Python projects (`backend`, `workers/general-worker`).
- [x] Nuxt 3 + Vue 3 + TypeScript + Pinia + Tailwind CSS 4.
- [x] FastAPI + Pydantic 2 + SQLAlchemy 2 + Alembic + asyncpg.
- [x] Dramatiq worker on Redis ([ADR-0001](docs/adr/0001-queue-dramatiq.md)).
- [x] Fastify + Sharp image worker service.
- [x] PostgreSQL 16, Redis 7, MinIO S3 object storage with bucket initialization.
- [x] Docker Compose with comprehensive health checks on all services.
- [x] Provider ports and deterministic fake adapters for complete offline testing.
- [x] Workflow state machine engine with optimistic concurrency and idempotency.
- [x] CI pipelines: unit, integration, linting, type-checking, and security scans.

### Phase 2 — Domain and Persistence ✅

- [x] Core domain model entities: `User`, `ProductWorkflow`, `OriginalIdea`, `ResearchRun`, `ProductConcept`, `DesignPrompt`, `ArtworkJob`, `Asset`, `Approval`, `ProductionJob`, `ListingDraft`, `ProviderUsage`, `AuditEvent`, `WorkflowTransition`.
- [x] Three design modes: `market-led` (Discover Ideas), `user-idea` (Use My Idea), `hybrid` (Hybrid Approach).
- [x] Preserved immutable user original idea alongside separately optimized market concept.
- [x] UUID primary keys, UTC timestamps, `Decimal` money ledger, and audit log.
- [x] Reversible Alembic migration `0002_phase_2_domain` and repository layer.

### Phase 3 — Authentication and Settings ✅

- [x] Single-owner Argon2id password authentication with secure HTTP-only cookies and CSRF protection.
- [x] Strict session-derived ownership enforcement across all endpoints.
- [x] Encrypted provider credentials storage with AES-GCM and key rotation (`0003_phase_3_auth_settings`).
- [x] Defaults configuration for budget, image quality, target country, language, and product types.

### Phase 4 — Telegram Remote Control ✅

- [x] Telegram Bot gateway with secure webhook verification and paired owner ID allow-list.
- [x] Poller daemon for local development (`worker.telegram_poller`).
- [x] Command handlers for `/status`, `/pause`, `/resume`, and `/stop`.
- [x] Interactive pairing flow with temporary code generation and expiration.

### Phase 5 — Idea Input, Research, and Gate 1 Approval ✅

- [x] Dashboard campaign forms for all 3 modes with dynamic validation and tailored helper text.
- [x] Multi-angle market research with Tavily Search API.
- [x] Structured opportunity synthesis via Gemini Flash and OpenAI models.
- [x] Keyword clustering, demand/competition scoring, and positive/negative prompt generation.
- [x] Gate 1 Concept Selection & Approval screen with design prompt revision tools.

### Phase 6 — Artwork Generation and Gate 2 Approval ✅

- [x] Recraft V4.1 (primary) with dynamic negative prompt omission for V4+ models.
- [x] Gemini Flash / Pro fallback image generation adapter.
- [x] S3 / MinIO asset upload, SHA-256 checksums, and public endpoint pre-signed URL signing (`http://localhost:9000`).
- [x] Multi-candidate comparison gallery in Nuxt 3 with Gate 2 Approve, Reject, and Regenerate actions.
- [x] Settings page UI credentials card supporting saving, revealing, and deleting encrypted API keys (`gemini`, `tavily`, `recraft`, `telegram`).
- [x] Migration `0008_phase_6_telegram` adding `telegram` to the `provider_name` PostgreSQL enum.

### Phase 7 — PNG Production Pipeline ✅

- [x] **Image Worker Fastify Endpoints (`workers/image-worker`)**:
  - [x] `POST /pipeline/trim-and-pad`: Safe-bounding box trim, transparency margin alignment (8% padding).
  - [x] `POST /pipeline/upscale`: High-fidelity bicubic/lanczos3 upscale to standard POD print dimensions (4500×5400 px, 300 DPI).
  - [x] `POST /pipeline/custom-mockup`: High-fidelity user-uploaded template compositor with realistic multiply texture blending.
  - [x] `POST /pipeline/process-master`: Unified master PNG generation pipeline.
- [x] **Deterministic SVG/PNG Typography Engine**:
  - [x] Font registry and SVG overlay generator for approved concept slogans.
  - [x] Automatic layout positioning and high-contrast color styling.
- [x] **Automated Quality Assurance (QA) Engine**:
  - [x] Validate print dimensions (4500×5400 px).
  - [x] Inspect alpha transparency ratio (verify transparent background and non-clipped edges).
  - [x] Check color profile (sRGB) and 300 DPI EXIF metadata.
  - [x] Generate structured JSON QA report (`dimensions_valid`, `has_transparency`, `safe_margins_valid`, `qa_passed`).
- [x] **User-Uploaded Mockup Template Store & Compositor**:
  - [x] Owner-scoped S3 storage under `mockup-templates/{owner_id}/{product_type}/`.
  - [x] Exact placement manifests (`left_pct`, `top_pct`, `width_pct`, `height_pct`, `angle_deg`, `blend_mode`).
  - [x] Fast compositing on demand via Nuxt 3 interactive modal.
- [x] **Worker Production Task (`workers/general-worker`)**:
  - [x] Extracted orchestrator `worker/production.py` (`execute_production_pipeline`).
  - [x] Uploads final transparent PNG to S3 bucket under `production/{workflow_id}/{job_id}/master.png`.
  - [x] Recomposites all existing user library mockups automatically upon candidate switch.
  - [x] Atomic UoW persistence and workflow state transition to `ARTWORK_APPROVED`.
  - [x] Telegram completion notification with master preview link and QA status.
- [x] **Frontend Architecture & UX (`frontend/`)**:
  - [x] Strict user-uploaded mockups with zero dummy/fallback mockups.
  - [x] Dynamic mockup product tabs (strictly categories with count > 0).
  - [x] Seamless artwork candidate switching & non-overlapping recursive polling without browser reload.
  - [x] Decomposed subcomponents: `ProductionStatusCard.vue`, `MasterPngCard.vue`, `ProductionQaCard.vue`, `MockupGallery.vue`, `MockupProductTabs.vue`, `MockupCard.vue`, `MockupEmptyState.vue`, `MockupPlacementCanvas.vue`, `MockupPlacementControls.vue`.
  - [x] Dedicated composables: `useProduction.ts`, `useMockups.ts`, and shared types in `frontend/types/`.

---

### Phase 8 — SEO, IP Risk Review, and Download Package ⏳

#### Phase 8 Backend & Workers

- [ ] **AI Listing SEO Generator**:
  - [ ] LLM prompt pipeline generating:
    - [ ] Etsy Listing Title (under 140 characters, front-loaded with high-intent keywords).
    - [ ] Etsy Description (formatted with materials, sizing chart, care instructions, file formats).
    - [ ] Exactly 13 Etsy Search Tags (strictly ≤ 20 characters per tag, no punctuation, zero duplicates).
    - [ ] Mandatory Etsy AI Disclosure statement.
- [ ] **Preliminary IP & Trademark Screening**:
  - [ ] Keyword and slogan scan against USPTO common trademark dictionaries.
  - [ ] Compute trademark risk level (`CLEARED`, `WARNING`, `HIGH_RISK`) with matched phrases.
- [ ] **Customer Download Package Builder**:
  - [ ] Deterministic ZIP bundle generator containing:
    - [ ] Master 300 DPI transparent PNG.
    - [ ] Print-ready PDF version.
    - [ ] Product mockups for buyer preview.
    - [ ] Commercial Use Licence (`LICENSE.txt`).
    - [ ] Customer Instructions & Sizing Guide (`INSTRUCTIONS.txt`).
    - [ ] Cryptographic checksum manifest (`manifest.sha256`).
- [ ] **Gate 3 Listing & Package Approval API**:
  - [ ] `PUT /api/v1/workflows/{id}/listing`: Update title, description, tags with validation.
  - [ ] `POST /api/v1/workflows/{id}/gates/listing`: Decide Gate 3 (`APPROVED` -> `LISTING_APPROVED` or `REJECTED`).
- [ ] **Telegram Gate 3 Integration**:
  - [ ] Send listing summary, tag cloud, IP risk notice, and inline `[Approve Listing]` / `[Edit Listing]` buttons.

#### Phase 8 Frontend (Nuxt 3)

- [ ] **Gate 3 Review Screen (`frontend/pages/workflow/[id].vue`)**:
  - [ ] Title & Description editor with character limit counters and live validation.
  - [ ] Interactive 13-Tag Tag Chip Editor with auto-trimming and 20-character counter per tag.
  - [ ] IP Risk Notice Card with required human acknowledgement checkbox before approval.
  - [ ] Customer ZIP package inspector and 1-click package download button.
  - [ ] Final Gate 3 "Approve & Ready for Etsy" action button.

---

### Phase 9 — Etsy Integration & Draft Creation ⏳

#### Phase 9 Backend & Workers

- [ ] **Etsy Open API v3 OAuth 2.0 Integration**:
  - [ ] PKCE authorization URL generation with secure state verification.
  - [ ] Token exchange callback (`GET /api/v1/auth/etsy/callback`) and token refresh loop.
  - [ ] Encrypted token storage in PostgreSQL via `ShopConnection` model.
- [ ] **Etsy Draft Listing Dispatcher**:
  - [ ] Create draft listing via `POST /v3/application/shops/{shop_id}/listings` with state strictly set to `draft`.
  - [ ] Upload primary transparent image and mockup preview images.
  - [ ] Upload digital ZIP package file to Etsy digital listing files endpoint.
  - [ ] **Absolute Non-Negotiable Safeguard:** Never publish or activate listings; zero API calls with state `active`.
- [ ] **Resilience & Rate Limiting**:
  - [ ] Respect Etsy API 10 req/sec rate limits with token bucket queue.
  - [ ] Idempotent retries and failure recovery.
- [ ] **Telegram Completion Notification**:
  - [ ] Send direct link to the newly created draft in the seller's Etsy Shop Manager.

#### Phase 9 Frontend (Nuxt 3)

- [ ] **Settings Page — Etsy Shop Connection Card (`frontend/pages/settings.vue`)**:
  - [ ] "Connect Etsy Shop" OAuth button, shop name display, and token status badge.
  - [ ] Disconnect / Reconnect options.
- [ ] **Workflow Page — Send to Etsy Action**:
  - [ ] "Create Etsy Draft" button unlocked after Gate 3 approval.
  - [ ] Success banner showing the Etsy Listing ID with direct external link to Etsy Shop Manager.

---

### Phase 10 — Deployment, Scheduling, and Monitoring ⏳

#### Phase 10 Backend & Infrastructure

- [ ] **Continuous Research Scheduler**:
  - [ ] Configurable background cron to trigger market-led seasonal research runs automatically.
- [ ] **Spend Caps & Cost Alerting**:
  - [ ] Enforce monthly USD spend caps in `ProviderUsage` ledger.
  - [ ] Telegram emergency alerts when reaching 80% and 100% of budget.
- [ ] **Health Monitoring & Backup Automation**:
  - [ ] Automated PostgreSQL database pg_dump backup schedule.
  - [ ] Container resource limits and read-only filesystem hardening.
- [ ] **Telegram Digest Reports**:
  - [ ] Weekly summary of research runs, approved artworks, created drafts, and ledger spend.

#### Phase 10 Frontend (Nuxt 3)

- [ ] **Analytics & Ledger Dashboard (`frontend/pages/analytics.vue`)**:
  - [ ] Monthly cost breakdown charts by AI provider (Recraft, Gemini, Tavily, OpenAI).
  - [ ] Cost-per-listing metrics and total draft count.
- [ ] **Research Scheduler UI**:
  - [ ] Settings interface to toggle and configure automated research schedules.

---

### Phase 11 — Post-Publishing Profit Intelligence & Winner Expansion (Future — Low Priority)

**Do not begin until Etsy draft/publishing flow is working and the shop has enough real sales data to learn from.** This phase is intentionally lower priority than getting products published and collecting evidence.

#### Sales & Profit Intelligence

- [ ] Import Etsy orders, transactions, refunds, fees, and listing performance into owner-scoped analytics.
- [ ] Calculate revenue, net profit, profit margin, API/design cost per listing, and profit per campaign.
- [ ] Rank niches, styles, seasons, keyword clusters, buyer segments, and themes using actual sales results.
- [ ] AI Profit Advisor explaining winners, weak listings, cost problems, and concrete profit-improvement actions.

#### Winner Expansion

- [ ] Detect best-selling/profitable listings and extract reusable patterns such as niche, style, season, buyer, keyword cluster, and visual direction.
- [ ] `Winner Expansion` action that proposes new, materially differentiated product ideas based on winning patterns.
- [ ] Generate new PNG concepts from those ideas and route approved concepts back through the existing artwork, production, SEO, and trademark workflow.
- [ ] Never blindly clone an existing design; add safeguards against near-duplicates, trademark reuse, and overfitting to tiny sales samples.

#### Learning Feedback Loop

- [ ] Feed validated sales/performance signals back into Phase 5 research scoring.
- [ ] Increase weighting for historically profitable patterns while preserving seasonal/current-market research.
- [ ] Track recommendation history and whether recommendations later became profitable.
- [ ] Dashboard showing winners, losers, profit trends, recommendations, and generated follow-up products.

Acceptance: recommendations must cite measurable shop evidence, remain advisory until owner approval, generate materially differentiated concepts, and never automatically publish listings.

---

### Phase 12 — Optional Multi-Shop SaaS Expansion (Future)

- [ ] Multi-tenant isolation and user role management.
- [ ] Multiple Etsy shop connections per account.
- [ ] Subscription tiers and usage metering.
