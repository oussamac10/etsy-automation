---
name: phase-7-production
description: Complete developer reference and domain rules for Phase 7 print-ready PNG production pipeline, automated QA checks, user-uploaded mockup template store, and interactive 2D canvas compositor.
---

# Phase 7: Print-Ready PNG Production & Realistic Mockups

This skill documents the Phase 7 architecture, domain contracts, worker pipeline, image processing microservice, and frontend state management.

---

## 1. Core Principles & Non-Negotiable Rules

1. **Strict Zero-Dummy Policy**:
   - Phase 7 mockups must originate **strictly from user-uploaded blank templates**.
   - NEVER generate, persist, or render dummy SVG mockups, fake printful placeholders, or fallback mockups based on campaign `intended_product_uses`.
2. **Mockup Gallery UX**:
   - The Mockup Gallery tabs strictly represent **actual user-selected mockups with count > 0**.
   - `campaign.intended_product_uses` is a concept for research and prompt crafting only — it MUST NEVER automatically create empty mockup gallery tabs.
   - If zero mockups exist across all product categories, show a single clean generic empty state.
3. **Domain Resolver as Single Source of Truth**:
   - Always use `filter_active_user_mockups(assets, master_asset_id)` and `get_production_master_asset(assets, master_asset_id)` from `app.domain.production_resolver`.
4. **Canonical Product Normalization**:
   - Backend: `from app.domain.mockup_products import normalize_product_type, get_product_preset, PRODUCT_PRESETS`.
   - Frontend: `import { normalizeProductKey, getProductLabel, getProductIconName, PRODUCT_PRESETS } from "~/utils/mockupProducts"`.
   - Canonical keys: `tshirt`, `sweatshirt`, `tote_bag`, `mug`, `tumbler`, `poster`, `sticker`, `phone_case`, `candle`.
5. **No Forced Browser Reloads**:
   - Artwork candidate switching and mockup generation must update the frontend state immediately using reactive composables (`useProduction`, `useMockups`) and non-overlapping polling. Never use `window.location.reload()`.

---

## 2. Architecture & File Structure

### A. Backend Architecture
- **`backend/app/domain/mockup_products.py`**: Pure domain entity defining canonical product keys, display labels, presets, and `normalize_product_type()`.
- **`backend/app/domain/production_resolver.py`**: Pure domain queries:
  - `get_production_master_asset()`: Finds the 4500×5400 px master PNG asset.
  - `is_valid_user_mockup_asset()`: Validates that an asset is a genuine user template mockup.
  - `filter_active_user_mockups()`: Filters and sorts active mockups by cover flag, listing order, and creation time.
- **`backend/app/domain/mockup_compositor.py`**: Recomposites existing user templates when a new master PNG is generated.
- **`backend/app/application/mockups.py`**: `MockupCompositionService` coordinating template lookup, validation, image worker calls, cover designation, and asset persistence.
- **`backend/app/api/routes/mockup_templates.py`**: Thin controller delegating to `MockupCompositionService`.

### B. Worker Pipeline & Image Processing
- **`workers/general-worker/worker/production.py`**: `execute_production_pipeline()` orchestrating:
  1. Input resolution (source artwork asset, approved slogan prompt).
  2. Calling Image Worker `/pipeline/process-master`.
  3. Uploading print-ready master PNG to S3 (`production/{workflow_id}/{job_id}/master.png`).
  4. Saving `Asset` record (4500×5400 px, 300 DPI, sRGB, alpha transparency).
  5. Recompositing existing user library mockups with the new master PNG.
  6. Finalizing `ProductionJob` status (`SUCCEEDED`) and updating workflow state.
  7. Delivering Telegram completion notification with preview URL and QA status.
- **`workers/image-worker/src/app.ts`** & **`packages/image-pipeline`**:
  - Sharp-based image transformations: safe trim (8%), upscale to 4500×5400 px @ 300 DPI, slogan typography compositing, and automated QA reporting.

### C. Frontend Architecture (Nuxt 3)
- **`frontend/types/production.ts` & `frontend/types/mockup.ts`**: TypeScript interfaces for `ProductionJob`, `ProductionQaReport`, `MasterAsset`, `MockupPlacement`, `MockupTemplateItem`, `MockupAsset`.
- **`frontend/utils/mockupProducts.ts`**: Canonical normalization, labels, Lucide icons, and default placement presets.
- **`frontend/composables/useProduction.ts`**: Production job state, start/switch production triggers, non-overlapping recursive timeout polling, authoritative terminal hydration.
- **`frontend/composables/useMockups.ts`**: Local mockup assets, computed active product tabs, template CRUD, and cover image assignment.
- **`frontend/components/workflow/production/`**:
  - `ProductionStatusCard.vue`: Ready, running, and failed status banners.
  - `MasterPngCard.vue`: Transparent checkerboard preview, dimensions badge, download, and candidate switch buttons.
  - `ProductionQaCard.vue`: Automated QA checklist, DPI, alpha verification, and slogan typography badges.
  - `MockupProductTabs.vue`: Dynamic category buttons with count badges.
  - `MockupCard.vue`: Individual mockup preview, cover badge, actions, and order shift buttons.
  - `MockupEmptyState.vue`: Empty states for individual tabs and global gallery.
  - `MockupGallery.vue`: Orchestrator for the mockup gallery section.
  - `MockupProductPickerModal.vue`: Modal for selecting product type.
- **`frontend/components/workflow/mockup-modal/`**:
  - `MockupTemplatePicker.vue`: Grid of saved templates from library.
  - `MockupUploadDropzone.vue`: Drag-and-drop file upload zone.
  - `MockupPlacementCanvas.vue`: Interactive drag, resize, rotate & blend canvas.
  - `MockupPlacementControls.vue`: Sliders, blend mode, cover toggle, and template saving controls.

---

## 3. Testing & Verification Guide

When making any changes to Phase 7, always run the full test suite:

```bash
# 1. Backend tests
.venv/bin/pytest backend/tests

# 2. Worker tests
.venv/bin/pytest workers/general-worker/tests

# 3. Image Pipeline & Image Worker tests
export PATH="/Users/oussama/.nvm/versions/node/v22.16.0/bin:$PATH"
npm --prefix packages/image-pipeline test
npm --prefix workers/image-worker test

# 4. Frontend Nuxt 3 tests
npm --prefix frontend test
```
