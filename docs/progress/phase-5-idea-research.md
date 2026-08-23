# Phase 5 — Idea Input, Research, and Gate 1 Approval

**Status:** Complete ✅  
**Date:** 2026-08-08  
**Branch:** `feature/phase-5-idea-research`  
**Next phase:** Phase 6 — Artwork generation and Gate 2 approval  

---

## 1. Overview & Objectives

Phase 5 establishes the core idea discovery and market intelligence pipeline:

1. **Three Idea Discovery Modes**:
   - **Market-Led (`market-led`)**: Autonomous seasonal and evergreen trend extraction across niches, buyer segments, and product types.
   - **User-Idea (`user-idea`)**: Seller prompt and slogan input with faithful preservation of the original input.
   - **Hybrid (`hybrid`)**: Combines user seed ideas with real-time market search signals and keyword expansion.
2. **Dual-Engine Market Intelligence**:
   - Web search evidence via **Tavily Search API**.
   - Structured JSON opportunity extraction via **Gemini Flash / OpenAI** models.
3. **Structured Opportunity Synthesis**:
   - Keyword clustering, demand/competition scoring, confidence levels, and positive/negative prompt generation.
4. **Gate 1 Approval Screen**:
   - Multi-concept comparison with one-click approval, prompt refinement, or rejection.
   - Strict invariant: original user input is immutable while optimized concepts and prompt versions are separately tracked.

---

## 2. Architecture & Flow

```text
+-----------------------------------------------------------+
|                      Nuxt 3 Dashboard                     |
|  (New Campaign Form: Market-Led, User-Idea, or Hybrid)    |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|                   FastAPI Backend API                     |
|       - Validates input payload & enforces mode rules     |
|       - Enqueues research task via Dramatiq               |
|       - Transitions workflow to RESEARCH_QUEUED           |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|                 General Worker (Dramatiq)                 |
|  - Queries Tavily Search API for live market evidence     |
|  - Synthesizes ranked concepts via LLM structured schema   |
|  - Generates positive & negative image generation prompts |
|  - Records cost in ProviderUsage ledger                   |
|  - Persists ProductConcept & DesignPrompt records         |
|  - Transitions workflow to IDEA_REVIEW                    |
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|                  Gate 1: Human Approval                   |
|  - Owner reviews candidate concepts in web dashboard      |
|  - Optional prompt editing & version creation             |
|  - [Approve] -> Transitions workflow to ARTWORK_QUEUED    |
|  - [Reject] -> Allows regeneration or workflow termination|
+-----------------------------------------------------------+
```

---

## 3. Implemented Components

### 3.1 Domain & Persistence Layer

- **`OriginalIdea` Model**: Preserves immutable user inputs (raw prompt, niche, target audience, style preferences, seed keywords).
- **`ResearchRun` Model**: Tracks query parameters, search evidence, raw LLM responses, and confidence scores.
- **`ProductConcept` Model**: Represents shortlisted ideas with title, description, differentiation, demand/competition scores, and risk level.
- **`DesignPrompt` Model**: Versioned prompt configurations with positive prompt, negative prompt, and revision change notes.

### 3.2 Research Provider Adapters

- **`TavilySearchAdapter` (`backend/app/providers/tavily.py`)**: Executes multi-angle queries for Etsy trends, buyer search terms, and competitor listings.
- **`GeminiSynthesisAdapter` / `OpenAISynthesisAdapter`**: Generates validated Pydantic JSON schemas with deterministic scoring and complete prompt pairs.
- **`FakeResearchProvider` (`backend/app/providers/fake.py`)**: Deterministic offline fixtures for CI and hermetic testing.

### 3.3 Application Use Cases & Tasks

- **`run_research_task` (`workers/general-worker/worker/tasks.py`)**: Full background execution pipeline with idempotency, budget ceiling checks, and cost ledger accounting.
- **Gate 1 Approval API (`backend/app/api/routes/workflows.py`)**: Endpoints for listing concepts, updating prompt versions, and submitting Gate 1 decisions (`APPROVED` / `REJECTED`).

### 3.4 Frontend Nuxt 3 UI

- **Campaign Creation Form**: Tabbed selector for `Discover Ideas`, `Use My Idea`, and `Hybrid Approach` with real-time validation.
- **Gate 1 Concept Card**: Ranked concept tiles with demand scores, keyword tags, prompt inspector modal, and approve/reject actions.

---

## 4. Verification & Testing

- **Integration Tests**:
  - `backend/tests/integration/test_worker_research_task.py`: Validates happy path, retry handling, budget refusal, and error handling.
  - `backend/tests/integration/test_api_idea_approval.py`: Validates Gate 1 idempotent transitions and prompt revision tracking.
  - `backend/tests/integration/test_research_budget.py`: Enforces monthly USD spend limits and budget ceilings.
- **Monorepo Checks**: 100% passing across unit, integration, linting (`ruff`), and strict type-checking (`mypy`).
