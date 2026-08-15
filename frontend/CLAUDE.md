# CLAUDE.md — Nuxt Web App

These rules extend the root instructions for `frontend`.

## Responsibilities

- Owner authentication and setup
- Research brief and research-run progress
- Ranked idea cards with evidence, score breakdown, confidence, and risk
- Idea approval gate
- Artwork side-by-side comparison with zoom and background toggles
- Artwork approval gate
- Production QA, phrase/typography controls, and mockup preview
- IP-review acknowledgement
- Listing editor, cost summary, and create-draft action
- Job history and retry controls

## UI rules

- Use Nuxt 3 Composition API and `<script setup lang="ts">`.
- Keep API access in typed composables/services; components never call providers directly.
- Use generated API types and runtime-validate important responses.
- Pinia stores workflow/client state only; server state should be fetched and invalidated deliberately.
- Every paid button shows the estimated maximum cost and requires confirmation when above the configured threshold.
- Every asynchronous action shows queued/running/succeeded/failed/cancelled states.
- Disabling a button is not authorization; backend rules remain authoritative.
- Surface evidence links and label observations versus AI inference.
- Never show `safe`, `trademark-free`, `guaranteed`, or `profitable` badges.
- Artwork comparison must support light, dark, and checkerboard backgrounds.
- Always show the original asset and derived asset provenance.

## Accessibility and UX

- Keyboard-operable gates, dialogs, and image selection.
- Visible focus, semantic controls, labels, and error summaries.
- Do not encode status or risk by color alone.
- Preserve unsaved listing text and warn before navigation.
- Responsive desktop-first layout; mobile remains usable.
- Provide empty, loading, partial, error, and retry states.

## Tests

- Vitest for composables, stores, validators, and key components.
- Playwright for the full approval flow with mocked provider jobs.
- Accessibility checks for every gate page.
- No snapshot-only testing for behavior.
