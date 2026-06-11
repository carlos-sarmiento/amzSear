# Product Feature Audit: Availability & Product Detail Features

**Date:** 2026-06-10 **Scope:** Availability signals and product-detail
extraction in amzSear, assessed as a product capability for the user's actual
use case: loading Amazon product data so an AI can help choose good products,
with priorities on **availability, pricing, and reviews**.

---

## Summary

amzSear has a _minimal, search-card-only_ availability signal: a best-effort
regex scan of card text that yields `availability` (matched phrase) and
`is_available` (True/False/None). It is English-only, binary, and frequently
"Unknown". The product detail page — the single richest source of availability
truth on Amazon (`#availability` block, buy box, delivery estimates, seller
info) — is fetched at `DetailLevel.BASIC` but **none of its availability, price,
delivery, or seller data is parsed**. So the deeper you drill into a product,
the _less_ availability/pricing information you get: `amzsear --asin XXXX`
returns title, brand, bullets, and rating but **no price and no stock status**.
For an AI-assisted buying workflow, that inverts the user's priorities.

Product detail extraction (brand, bullets, technical details, description, star
distribution) is genuinely useful for AI comparison and is the strongest part of
the feature area. The biggest wins are: (1) parse availability + price +
delivery from the product page, (2) capture the full delivery/stock phrase
(dates, "Only N left") instead of just the matched pattern, (3) flag sponsored
listings, and (4) add an `--available-only` filter.

---

## Current Capabilities

### Availability (search results only)

Implemented in `AmzProduct._get_availability_from_html`
(amzsear/core/AmzProduct.py:130-166):

- Flattens the entire search-card text and scans regex patterns.
- **Unavailable patterns** (→ `is_available=False`): "currently unavailable",
  "temporarily out of stock", "out of stock", "no featured offers available",
  "not available", "discontinued", "sold out".
- **Available patterns** (→ `is_available=True`): "only N left in stock", "in
  stock", "available to ship", "ships from", "free delivery".
- No match → both fields `None` ("Unknown").
- `availability` stores **only the matched substring** (`match.group(0)`), e.g.
  `"FREE delivery"` — the date that follows ("Tue, May 19") is discarded.

### Output surfaces

| Surface               | Availability exposure                                                  |
| --------------------- | ---------------------------------------------------------------------- |
| CLI table (default)   | `Available` column: `Yes` / `No` / `Unknown` (cli.py:209-216)          |
| CLI `--verbose`       | Raw `availability` + `is_available` fields dumped with everything else |
| CLI `--json`          | Both fields included in short and verbose JSON (cli.py:142-143)        |
| CLI `--asin` (detail) | **Nothing** — no availability, no price, in any output mode            |
| MCP `search_products` | Both fields via `to_dict()`                                            |
| MCP `get_product`     | **Nothing** — `AmzProductDetails` has no availability/price fields     |

### Product details (`AmzProductDetails`, fetched at `DetailLevel.BASIC`)

Parses: `full_title`, `brand` + `brand_url`, `about_items` bullets,
`technical_details` (3 selector fallbacks), `product_description`, `image_urls`,
`reviews_summary` (AI insights widget), `star_distribution`, `review_count`,
`average_rating`. Good fallback-selector hygiene; fields default to `None`
gracefully.

### Tests

`tests/test_product_availability.py` — 3 synthetic-card tests (unavailable,
delivery text, price-only → unknown). No real-HTML fixtures, no region/language
coverage, no product-page availability tests (since the feature doesn't exist).

---

## Gaps / Weaknesses

### 1. Product page availability is not extracted at all (highest impact)

The product page exposes `#availability` ("In Stock", "Only 3 left in stock —
order soon", "Currently unavailable", "Usually ships within 1 to 2 months"), the
buy-box price, delivery estimates, and "Ships from / Sold by".
`AmzProductDetails` parses **none** of it, and `selectors.py` has no selectors
for it. Consequences:

- `--asin` lookup and MCP `get_product` cannot answer the user's #1 and #2
  questions (is it available, what does it cost).
- Search-level "Unknown" can never be resolved by drilling in.
- "Ships in 1-2 months" — exactly the trap the user wants to avoid — is
  invisible.

### 2. Binary signal with no granularity

`is_available` collapses meaningfully different states: in stock now, "Only 2
left", "ships later", available only from 3rd-party sellers. "Only N left in
stock" is matched but mapped to plain `True` — the low-stock urgency signal is
captured in `availability` text only by accident, and not surfaced distinctly
anywhere.

### 3. Delivery dates discarded

The regex matches `"free delivery"` and throws away `"Tue, May 19"`. Delivery
estimates are a practical availability proxy ("arrives in 2 days" vs "arrives in
6 weeks") and would cost nothing extra to capture — just widen the captured
span.

### 4. English-only patterns × 16 supported regions

`REGION_CODES` advertises DE, FR, JP, ES, IT, BR, MX, CN, NL, AE… but every
availability pattern is English. For non-English regions the signal is
effectively always "Unknown" (or wrong, since "free delivery" can appear in
English on some localized pages). Either localize the patterns or document that
availability is US/UK-only.

### 5. "Unknown" is the default failure mode and is silent

Any card without explicit delivery/stock text → `Unknown`. There is no way to
distinguish "parser couldn't tell" from "Amazon showed nothing". A heuristic
like _has a buy-box price + delivery promise → very likely available_ is not
applied. No telemetry/indication of how often Unknown occurs, and no test
against real current Amazon HTML to detect selector rot.

### 6. Sponsored listings are not flagged

README's own example output shows `"[Sponsored]Kids' Travel Guide..."` leaking
into the title. Sponsored results are ad placements, often worse value — an AI
ranking products should know which rows are ads. No `is_sponsored` field, no
filter, no stripping of the marker from the title.

### 7. No seller / Prime / fulfillment info

- No "Sold by Amazon vs 3rd-party marketplace" distinction (search cards and buy
  box both expose this) — directly relevant to trustworthiness and returns.
- No Prime-eligibility flag (the Prime badge is a simple `i.a-icon-prime`
  selector on search cards).

### 8. No variant awareness

A product "available" in one color/size may be sold out in the one the user
wants. Product pages expose the variation matrix (`#twister`,
`data-defaultasin`, dimension values). Nothing is extracted; not even a "this
product has N variants" hint.

### 9. No consumer-side filtering or sorting

Cannot do `--available-only`, cannot sort by availability, no MCP parameter to
exclude unavailable/sponsored items. The AI consumer must post-filter — workable
but wasteful, especially when search returns many discontinued items.

### 10. Product-detail completeness nits

- `technical_details` merges all matching tables blindly; warranty/feedback rows
  can pollute it, and the three selectors can overwrite each other's keys —
  acceptable but noisy for AI input.
- `extra_attributes` (search card) uses a fragile zip-pairing of sibling spans;
  output is essentially undocumented noise.
- No price on the detail page (buy-box `.a-price`, list price/strikethrough, "N
  offers from $X") — pricing is priority #2 and the detail object has zero price
  fields.
- `reviews_summary` selector (`.cr-insights-widget`) targets a widget Amazon
  frequently A/B tests; silently `None` when absent (fine), but worth a fallback
  selector.

---

## Prioritized Recommendations

Ordered by impact on the user's workflow (availability → pricing → reviews;
personal tool, no enterprise features).

### P0 — Parse availability, price, and delivery from the product page

Add to `AmzProductDetails` (+ selectors): `availability_text` (raw
`#availability` text), `availability_status` (enum: `in_stock` / `low_stock` /
`ships_later` / `unavailable` / `unknown`), `stock_count` (from "Only N left"),
`buybox_price`, `list_price`, `delivery_estimate`, `ships_from`, `sold_by`.
Surface them in `--asin` short/verbose/JSON output and MCP `get_product`. This
single change fixes the worst inversion: detail lookups currently know _less_
about availability and price than search results.

### P0 — Upgrade the search-card signal from binary to a small enum + full phrase

Keep `is_available` for compatibility, but add `availability_status` with
`low_stock` ("Only N left") and `ships_later` ("Usually ships within...")
states, and capture the **whole phrase including dates** ("FREE delivery Tue,
May 19" not "FREE delivery"). Cheap change in `_get_availability_from_html` —
widen the capture and map patterns to states.

### P1 — Flag sponsored listings

Add `is_sponsored: bool` per product (detect the sponsored label component /
"[Sponsored]" title prefix, and strip it from `title`). Expose in table (e.g.
`*` marker), JSON, and MCP. An AI choosing products should discount ads.

### P1 — `--available-only` filter (CLI + MCP)

`amzsear "usb hub" --available-only` and
`search_products(..., exclude_unavailable=True)` dropping
`is_available is False` items (keep Unknown). Trivial, directly serves "filter
out unavailable items".

### P1 — Capture delivery estimate as a field

`delivery_estimate: str` on search products (the text after delivery patterns).
Lets the AI rank "arrives Thursday" above "arrives in 6 weeks" — a stronger
availability signal than the binary flag.

### P2 — Prime eligibility + seller type

`is_prime: bool` from the search-card Prime badge; `sold_by` / `ships_from` from
the product-page buy box (P0 item above covers the page side). For a personal
buyer, "Sold by Amazon, Prime" vs "3rd-party, ships from overseas" is
decision-grade information.

### P2 — Honest regional behavior

Either add localized pattern sets for the regions the user actually uses, or
have non-English regions return a documented `unknown` plus a README note.
Silent wrongness is worse than declared absence. (Skip full i18n — enterprisey;
just cover the user's regions.)

### P2 — Real-HTML regression fixtures

Save a couple of real search/product pages as test fixtures and assert
availability/detail extraction against them, so Amazon markup drift (the main
reliability risk for everything above) is caught by `pytest` instead of by a bad
purchase decision.

### P3 — Variant availability hint

At minimum `has_variants: bool` + dimension names from the product page; full
per-variant stock requires extra requests and is likely not worth it for a
personal tool.

### Not recommended (out of scope for this user)

Restock alerts/watching (needs persistence + scheduling — separate tool
territory), multi-region price arbitrage, inventory APIs, business seller
analytics.

---

## Quick Reference: Signal Coverage Today vs Proposed

| Signal                    | Search card today | Detail page today | Proposed                          |
| ------------------------- | ----------------- | ----------------- | --------------------------------- |
| In stock / out of stock   | Best-effort regex | Not parsed        | Parse `#availability` (P0)        |
| Low stock ("Only N left") | Lumped into True  | Not parsed        | `low_stock` status + count (P0)   |
| Ships-later               | Missing           | Not parsed        | `ships_later` status (P0)         |
| Delivery date estimate    | Discarded         | Not parsed        | `delivery_estimate` field (P0/P1) |
| Price on detail page      | n/a               | Not parsed        | `buybox_price`, `list_price` (P0) |
| Sponsored flag            | Leaks into title  | n/a               | `is_sponsored` + strip (P1)       |
| Sold by / ships from      | Missing           | Not parsed        | Buy-box fields (P2)               |
| Prime eligibility         | Missing           | Not parsed        | `is_prime` badge check (P2)       |
| Variant availability      | Missing           | Not parsed        | `has_variants` hint (P3)          |
| Filter unavailable        | Missing           | n/a               | `--available-only` (P1)           |
| Non-English regions       | Always Unknown    | n/a               | Localize or document (P2)         |
