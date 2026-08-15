# API Costs and Budget Model

Verified 2026-08-01. Prices change; the app must keep them in versioned configuration and display estimates before paid calls.

## Current provider prices

| Provider/operation | Current price used by MVP | Notes |
| --- | ---: | --- |
| OpenAI `gpt-5.6-luna` text | $0.20 / 1M input; $1.20 / 1M output tokens | Good default for structured research synthesis and SEO; escalate only when evaluation shows need. |
| OpenAI web search | $10 / 1,000 calls + search-content tokens | Equivalent to $0.01 per search call before tokens. |
| OpenAI `gpt-image-2`, medium 1024×1536 | about $0.041/image output | Prompt/input tokens add a small amount. It currently does not support transparent output, so validate/remove the background later. |
| OpenAI `gpt-image-2`, high 1024×1536 | about $0.165/image output | Use only for an approved final when evaluation justifies it. |
| Recraft V4.1 raster | $0.035/image | Standard alternative artwork. |
| Recraft V4.1 Pro raster | $0.21/image | Optional premium generation. |
| Recraft V4.1 vector | $0.08/image | Use only when vector output has a clear purpose. |
| Recraft background removal | $0.01/request | Run on the selected asset only when needed. |
| Recraft crisp upscale | $0.004/request | Low-cost deterministic-style upscale. |
| Recraft creative upscale | $0.25/request | Avoid by default because it can alter artwork. |
| Etsy Open API | No per-call price published in the API documentation | Access and rate limits apply. Publishing/renewing a listing is a marketplace action with a separate fee. |
| Etsy listing publication/renewal | $0.20/listing | Charged when listed or renewed, not for ordinary editing. A draft should not be treated as a published listing. |
| Etsy transaction fee | 6.5% of the relevant sale amount | Payment processing and possible country/advertising fees are additional. |
| USPTO TSDR data API | Registration/API key required; no per-call fee identified on the official page | Use only for preliminary signals. Require final human search/review. |
| Sharp/SVG/ZIP/mockup templates | $0 API usage | Compute/storage/hosting still cost money. |

Official sources:

- OpenAI pricing: <https://developers.openai.com/api/docs/pricing>
- OpenAI image guide and calculator: <https://developers.openai.com/api/docs/guides/image-generation>
- Recraft API pricing: <https://www.recraft.ai/docs/api-reference/pricing>
- Etsy API access: <https://developers.etsy.com/documentation/>
- Etsy rate limits: <https://developers.etsy.com/documentation/essentials/rate-limits/>
- Etsy fees: <https://www.etsy.com/legal/fees/>
- USPTO TSDR API information: <https://www.uspto.gov/trademarks/apply/check-status-view-documents/trademark-bulk-data>

## Estimated API cost per completed listing

### Recommended MVP run

Assumptions:

- 5 web-search calls
- about 10,000 text input tokens and 5,000 output tokens on `gpt-5.6-luna`
- 1 medium OpenAI portrait image
- 1 standard Recraft raster image
- background removal and crisp upscale on the winner
- local typography, mockups, and ZIP

```text
Web search calls          5 × $0.01       = $0.050
Text model input          0.010M × $0.20  = $0.002
Text model output         0.005M × $1.20  = $0.006
OpenAI medium image                         $0.041
Recraft standard image                      $0.035
Background removal                          $0.010
Crisp upscale                               $0.004
-------------------------------------------------
Estimated base API cost                     $0.148
```

Search-content and image prompt tokens add a little, so budget approximately **$0.15–$0.20 before retries**.

Real designs often need regeneration. A safer operational allowance is:

| Mode | Expected API allowance per completed listing | Use |
| --- | ---: | --- |
| Lean | $0.15–$0.30 | One generation per provider, few retries |
| Normal | $0.30–$0.60 | Two to four extra attempts/edits |
| Premium | $0.80–$1.50+ | High/Pro images and several retries |

These are engineering budgets, not guaranteed bills. Actual cost must come from recorded usage.

## Example monthly budget

For 30 completed listings/month:

| Item | Lean | Normal | Premium |
| --- | ---: | ---: | ---: |
| Generation/research APIs | $4.50–$9 | $9–$18 | $24–$45+ |
| Etsy publication fees for 30 listings | $6 | $6 | $6 |
| Hosting/database/storage | $0–$25 during a small MVP | $0–$25 | $25+ |
| Estimated total before sales fees | about $10.50–$40 | about $15–$49 | about $55+ |

Etsy transaction, payment processing, advertising, VAT/tax, and regulatory fees depend on sales and seller location and are not included in the API budget.

## Cost-control implementation

Store prices like this conceptually:

```json
{
  "provider": "openai",
  "operation": "image_generation",
  "model": "gpt-image-2",
  "quality": "medium",
  "size": "1024x1536",
  "estimated_output_usd": "0.041",
  "effective_from": "2026-08-01",
  "source_url": "https://developers.openai.com/api/docs/guides/image-generation"
}
```

Rules:

1. Estimate before enqueueing.
2. Reserve the maximum estimated amount against the run budget.
3. Reconcile with actual token/unit usage afterward.
4. Require manual approval above the threshold.
5. Stop retries when the remaining budget is insufficient.
6. Alert when a configured price is older than 30 days.
7. Do not auto-switch to a premium model.
