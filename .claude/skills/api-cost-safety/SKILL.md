---
name: api-cost-safety
description: Handle cost ledger rules, run budgets, provider usage, and pricing validations before invoking external APIs (OpenAI, Recraft). Use for Phase 5/6 API client code.
---

# API Cost and Budget Safety Skill

Maintain strict cost ceilings and audit logs before initiating network requests to paid providers.

## Absolute Rules
1. **Estimate Before Dispatch**: Calculate the pricing estimate based on context tokens or image sizes. If a job exceeds the remaining budget, reject it immediately.
2. **Centralized Prices**: Read current pricing configurations from a versioned store (e.g. `docs/API_COSTS.md` or settings). Do not hardcode rates directly in the client logic.
3. **Idempotency Keys**: Guarantee that all paid calls use an `idempotency_key` derived from the workflow state, to prevent multiple charges in case of retries.
4. **Log Everything**: Always persist the `ProviderUsage` and `AuditEvent` records BEFORE and AFTER making the external API call. Never run external calls within an active database transaction.
5. **No Cost Redactions**: Redact prompts or metadata if necessary, but never redact cost, unit counts, or transaction records.
