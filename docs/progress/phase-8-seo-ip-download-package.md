# Phase 8: AI SEO Generation, Trademark Screening & Customer Package

## Status: COMPLETE ✅

**Branch:** `feature/phase-8-seo-ip-download-package`

---

## 1. Overview & Objectives

Phase 8 bridges print-ready master PNG production (Phase 7) and Etsy listing draft creation (Phase 9) by providing:
1. **AI Listing SEO Generator:** Generates high-converting Etsy listing titles (<= 140 characters), structured Markdown descriptions, exactly 13 Etsy tags (<= 20 characters each, no duplicates/punctuation), and transparent AI disclosures.
2. **USPTO Trademark & IP Screening:** Performs automated multi-class preliminary trademark searching against official USPTO registry data across print-on-demand Nice classes (`009`, `016`, `021`, `025`, `035`) and internal brand blacklist dictionaries.
3. **Internal IP Risk Classification:**
   - `LOW` (`CLEARED`): No active/conflicting registered marks in POD classes. Enables 1-click Gate 3 approval.
   - `MEDIUM` (`WARNING`): Trademark matches found in secondary / non-POD classes or generic slogans. Requires explicit human acknowledgement checkbox before Gate 3 approval.
   - `HIGH` (`HIGH_RISK`): Exact or high-confidence registered mark in POD classes (apparel, graphics, print). Strictly blocks Gate 3 approval until terms are edited and re-screened.
   - Legal Disclaimer: *"Preliminary automated trademark screening only — not legal advice."*
4. **Customer Download Package Builder:** Assembles a deterministic customer ZIP archive containing:
   - `master.png` (4500x5400 px, 300 DPI, sRGB, transparent background)
   - `print-ready.pdf` (Pure Python zero-dependency PDF 1.4 embedding the master PNG with 300 DPI media box)
   - Active user mockup previews
   - `LICENSE.txt` (Commercial use rights and limitations)
   - `INSTRUCTIONS.txt` (Customer sizing and usage guide)
   - `manifest.sha256` (Cryptographic SHA-256 integrity verification)
5. **Gate 3 Decision & Telegram Notifications:** Authorizes campaign transition from `LISTING_REVIEW` to `READY_FOR_ETSY_DRAFT` (approval) or back to `ARTWORK_APPROVED` (rejection). Never automatically publishes to Etsy.

---

## 2. Architecture & Components

```
                +------------------------------------+
                |       Stage 4: Listing Review       |
                +------------------------------------+
                                  |
            +---------------------+---------------------+
            |                                           |
            v                                           v
+-----------------------+                   +-----------------------+
|  AI Listing Copy Gen  |                   |  USPTO Trademark API  |
|  - Title (≤ 140 ch)   |                   |  - POD Classes        |
|  - 13 Tags (≤ 20 ch)  |                   |    009, 016, 021,     |
|  - Markdown Desc      |                   |    025, 035           |
|  - AI Disclosure      |                   |  - Risk Scorer        |
+-----------------------+                   +-----------------------+
            |                                           |
            +---------------------+---------------------+
                                  |
                                  v
                +------------------------------------+
                |      Customer Package Builder      |
                | - master.png (4500x5400 @ 300 DPI) |
                | - print-ready.pdf (PDF 1.4)        |
                | - Mockups, LICENSE, INSTRUCTIONS   |
                | - manifest.sha256 -> ZIP Archive   |
                +------------------------------------+
                                  |
                                  v
                +------------------------------------+
                |       Gate 3 Human Review Bar      |
                | [Approve / Acknowledge]  [Reject]  |
                +------------------------------------+
```

### Key Modules

| Module | Layer | Purpose |
|---|---|---|
| `backend/app/domain/tags.py` | Domain | Pure Python Etsy tag normalizer, 20-char limit, exact 13 tags validator, 140-char title validator. |
| `backend/app/domain/ip_risk.py` | Domain | Phrase extractor, Nice class matcher, deterministic risk evaluator (`LOW`, `MEDIUM`, `HIGH`). |
| `backend/app/domain/package_builder.py` | Domain | Pure Python PDF 1.4 generator from PNG raster, license & instruction texts, SHA-256 manifest, ZIP packager. |
| `backend/app/providers/uspto.py` | Infrastructure | Live USPTO Open Data Trademark Search API client with `USPTO_API_KEY`. |
| `backend/app/providers/fake.py` | Infrastructure | Deterministic `FakeTrademarkSearchAdapter` for offline development and test assertions. |
| `backend/app/infrastructure/repositories/listing.py` | Infrastructure | PostgreSQL `ListingDraftRepository` with optimistic concurrency locking. |
| `backend/app/application/seo.py` | Application | Structured Gemini/OpenAI SEO generation orchestrator. |
| `backend/app/application/trademark.py` | Application | Multi-phrase trademark screening orchestrator. |
| `backend/app/application/package.py` | Application | Customer download ZIP bundle assembly and storage persistence. |
| `backend/app/application/listing.py` | Application | Listing draft lifecycle and Gate 3 approval enforcing IP rules. |
| `backend/app/application/telegram.py` | Application | Telegram review card and inline button handlers (`listing_app`, `listing_rej`). |
| `frontend/composables/useListing.ts` | Frontend Composable | Reactive listing state and API methods (`loadListing`, `updateListing`, `rescreenTrademark`, `generateSeo`, `decideGate3`). |
| `frontend/components/workflow/listing/` | Frontend UI | `ListingEditorCard.vue`, `TagEditorCard.vue`, `IpRiskCard.vue`, `CustomerPackageCard.vue`, `WorkflowListingTab.vue`. |

---

## 3. Database Schema

The `listing_drafts` PostgreSQL table:

```sql
CREATE TABLE listing_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL UNIQUE REFERENCES workflows(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    tags VARCHAR(20)[] NOT NULL,
    price_minor_units INTEGER,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    ai_disclosure TEXT,
    licence_text TEXT,
    customer_instructions TEXT,
    ip_reviewed_phrase VARCHAR(200),
    ip_risk_level VARCHAR(20) NOT NULL DEFAULT 'unknown',
    ip_findings JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_acknowledged_at TIMESTAMPTZ,
    ip_acknowledged_by VARCHAR(100),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_listing_drafts_tags_cardinality CHECK (cardinality(tags) <= 13)
);
```

---

## 4. API Endpoints

- `GET /api/v1/workflows/{id}/listing`: Fetches or initializes the listing draft, IP findings report, and customer package asset signed URL.
- `PUT /api/v1/workflows/{id}/listing`: Updates title, description, and tags with optimistic concurrency lock verification (`expected_version`).
- `POST /api/v1/workflows/{id}/listing/rescreen`: Re-queries USPTO trademark registry for all listing terms and recalculates risk level.
- `POST /api/v1/workflows/{id}/listing/generate-seo`: Generates AI SEO title, description, 13 tags, and disclosure statement using LLM.
- `POST /api/v1/workflows/{id}/gates/listing`: Decides Gate 3:
  - `decision="approved"` with `acknowledged=True` (if medium risk): Advances state to `READY_FOR_ETSY_DRAFT`.
  - `decision="rejected"`: Reverts state to `ARTWORK_APPROVED`.

---

## 5. Verification & Test Summary

| Test Suite | File | Tests | Result |
|---|---|---|---|
| Tags & Title Domain | `backend/tests/test_tags.py` | 6 | Passed (0.01s) |
| Trademark Screening & Adapters | `backend/tests/test_trademark_screening.py` | 7 | Passed (0.02s) |
| Package & PDF Generator | `backend/tests/test_package_builder.py` | 5 | Passed (0.02s) |
| Full Backend Pytest Suite | `backend/tests/` | 290 | Passed (2.18s) |
| Schema Documentation | `pnpm doc:schema:check` | 1 | Passed |
| Frontend Unit & Component Tests | `frontend/tests/workflowListing.test.ts` | 5 | Passed |
| Full Frontend Vitest Suite | `pnpm test` (all packages) | 142 | Passed |
| Workspace TypeScript Typecheck | `pnpm typecheck` | All 4 packages | Passed (0 errors) |
| Workspace ESLint | `pnpm lint` | Workspace | Passed (0 errors, 0 warnings) |
