# FABLE Feature Audit — amzSear

**Date:** 2026-06-10
**Method:** 5 independent agent audits, one per product area. Full reports in `fable-product-audits/`.
**Use case:** Personal tool — load Amazon product info (availability, pricing, reviews) so an AI assistant can help choose good products. Enterprise/business features explicitly out of scope.

| Area                           | Report                                                     |
| ------------------------------ | ---------------------------------------------------------- |
| Pricing                        | `fable-product-audits/pricing-features.md`                 |
| Reviews & ratings              | `fable-product-audits/reviews-and-ratings.md`              |
| Availability & product details | `fable-product-audits/availability-and-product-details.md` |
| Search & CLI UX                | `fable-product-audits/cli-and-search-ux.md`                |
| MCP & AI integration           | `fable-product-audits/mcp-and-ai-integration.md`           |

---

## Executive Summary

amzSear has a solid scraping skeleton and a review-rich data model, but **the value leaks before it reaches the consumer**. The recurring theme across all five audits: data the library already extracts (numeric ratings, review counts, float prices, review text) never reaches the CLI table, the JSON output, or the MCP payloads — and the data that matters most (detail-page price and stock status) is never extracted at all.

Three cross-cutting failures dominate:

1. **The product detail page extracts no price and no availability.** Drilling into a product via `--asin` or MCP `get_product` answers everything *except* the user's top two questions ("is it available?", "how much?"). Search results know more about availability than detail lookups do — an inversion of the priority order.
2. **Amazon's bot-wall fails silently.** CAPTCHA pages return HTTP 200, parse to zero products, and surface as "no results" with exit code 0. The AI confidently reports wrong conclusions; the CLI user can't tell "blocked" from "nothing matched."
3. **Output is raw scrape prose, not normalized data.** `{"0": "$29.99"}` price dicts, `"4.5 out of 5 stars"` strings, vanishing `None` fields, whole-star glyphs that render 4.6 and 5.0 identically, and no review counts in the table — even though `get_prices()`, `get_numerator()`, and `get_count()` already compute the numerics.

The good news: most high-impact fixes are **exposure work, not new scraping**. The per-review model (verified badge, helpful votes, full text), star distribution, Amazon's own AI review summary, and detail-level cost knob already exist.

---

## Top 10 Findings (cross-area)

| #   | Finding                                                                                                                                    | Areas affected                  |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------- |
|   1 | Detail page (`AmzProductDetails`) parses **zero price and zero availability** — no `#availability`, buy-box, delivery, or seller selectors | Pricing, Availability, MCP      |
|   2 | **Silent bot-wall failure**: HTTP 200 CAPTCHA → empty results, exit 0, no `blocked` signal — AI reports "no results" confidently           | CLI, MCP, all data areas        |
|   3 | **Prices are stringly-typed with junk keys** (`{"0": "$29.99"}`); `get_prices()` floats never exposed; no currency field                   | Pricing, CLI, MCP               |
|   4 | **Rating precision destroyed in CLI**: whole-star glyphs (4.6 ≡ 5.0) and **no review count** in the search table                           | Reviews, CLI                    |
|   5 | **Review text unreachable from the CLI**: `--asin` hard-codes `DetailLevel.BASIC`; no `--reviews`/`--level` flag                           | Reviews, CLI                    |
|   6 | **Comma-decimal corruption**: `get_prices()` turns `29,99 €` into `2999.0` — wrong by 100× in 10 of 16 supported regions                   | Pricing                         |
|   7 | **No sort/filter anywhere**: no max-price, min-rating, available-only, or sort-by in CLI or MCP — the AI must over-fetch and post-process  | CLI, MCP, Pricing, Availability |
|   8 | **No compare tool**: the actual decision loop (compare 2–4 finalists) requires N round-trips and manual joining                            | MCP, Reviews                    |
|   9 | **`None` fields vanish from JSON/MCP payloads**: "availability unknown" is indistinguishable from "field doesn't exist"; invalid → `{}`    | MCP, Availability               |
|  10 | **English-only availability patterns** across 16 advertised regions; non-English regions are effectively always "Unknown"                  | Availability                    |

---

## Findings by Area

### 1. Pricing (weakest of the three priorities)

- Detail page extracts **no price at all** — the richest pricing source (deal price, list price, coupons, unit price, used offers) is untapped.
- Price-type labels lost: stale `h3[data-attribute]` selector means Kindle/Paperback prices collapse into anonymous keys `"0"`, `"1"`.
- No list-vs-deal distinction → deal detection (a direct "good product" signal) is impossible.
- No coupon, unit-price ($/count), shipping cost, or used/refurb capture.
- Comma-decimal locales corrupted 100× (DE, FR, ES, IT, NL, BR, …).
- No price history across runs — every invocation is amnesiac; a tiny local `(asin, timestamp, price)` log would answer "is this a good price?"
- Zero test coverage for price extraction; selector drift breaks the top-priority data silently.

### 2. Reviews & Ratings (best data model, worst exposure)

- Per-review model is genuinely good (full text, verified badge, helpful votes, per-review stars) — but reaches only MCP/Python, never the CLI.
- JSON/MCP emit display strings (`"4.5 out of 5 stars"`, `"43,116"`) despite numeric helpers existing.
- `get_reviews` MCP response lacks `average_rating`/`star_distribution` context — a second call is needed to judge if ~10 sampled reviews are representative.
- Review sample is one page, Amazon's default positive-skewed sort; no `sortBy=recent` or `filterByStar=critical` — yet **critical reviews are the most informative for choosing**.
- The `TOP_REVIEWS` selector is defined but never used: product pages embed ~8 reviews that would sidestep the login wall on `/product-reviews/`.
- `feature_ratings` is mislabeled — returns mention counts ("2K"), not ratings; an AI will misread it.
- `DetailLevel.FULL` (Q&A) is a silent no-op — accepted everywhere, fetch commented out.
- Review dates are raw locale strings — recency trends ("recent reviews mention quality drop") not computable.

### 3. Availability & Product Details

- Search-card signal is binary and lossy: in-stock / "Only 2 left" / ships-later all collapse to `True`; matched fragment only ("FREE delivery"), discarding the delivery date that follows.
- Detail page: `#availability` block, buy box, delivery estimate, "Ships from / Sold by" — none parsed (see top finding #1).
- "Unknown" is the silent default; no heuristic (buy-box price + delivery promise → likely available) applied.
- Sponsored listings unflagged — "[Sponsored]" leaks into titles (visible in the README's own example); no `is_sponsored` for the AI to discount ads.
- No Prime badge, seller-type (Amazon vs 3rd-party), or variant-availability signals — all cheap to extract, all decision-grade.
- No `--available-only` filter in CLI or MCP.
- Tests are 3 synthetic snippets; no real-HTML fixtures, so selector rot goes undetected.

### 4. Search & CLI UX

- Default table is decision-thin: titles truncated at 50 chars (cutting the distinguishing variant/size info), rounded stars, no review count, no index column.
- No sorting, filtering, result limit, or multi-page fetch — even though the core API already accepts page ranges.
- JSON is unstable and asymmetric: search vs `-a` schemas differ; keyed by ASIN (loses order); no query metadata.
- No `--markdown` output — the highest-leverage format for a paste-into-AI-chat workflow.
- No caching: iterative compare sessions re-hit Amazon, slow and raising bot-wall risk.
- Small traps: `-s` digit heuristic misroutes 10-digit ISBN ASINs to index lookup; `query` + `-a` silently ignores the query; `-a` short output omits availability entirely; help text lacks examples; `docs/regions.md` omits AE.

### 5. MCP & AI Integration (the heart of the workflow)

- 9 tools mirror the library API, not the shopping loop: missing `compare_products(asins)`, batch lookup, filtered search, capped/sorted review summary.
- Three different error shapes for the same fetch failure (raise raw / optional `fetch_error` / always-present field).
- Token footguns: `search_products` returns every result with all fields, no `limit`; `detail_level="FULL"` on search serially fetches detail+review pages for *every* result with no docstring warning; `get_reviews` dumps full review texts uncapped.
- One-liner docstrings too thin for LLM tool selection — `detail_level` costs, `select` semantics (index vs ASIN), tool-choice guidance all absent.
- Streamable HTTP only — no stdio transport, so Claude Code/Desktop registration requires babysitting a daemon; client-registration docs absent.
- Bright spot: `parse_*_html` tools are an underdocumented anti-blocking escape hatch (save page in browser → AI parses it).

---

## Consolidated Roadmap

Prioritized by impact on the "AI helps me choose a product" loop, weighted by effort. Personal-scale only.

### P0 — Fix the data foundation

| Item                                                                                                                              | Why                                                              | Effort |
| --------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------ |
| Parse availability, buy-box price, list price, delivery estimate, seller from the **product detail page**; expose in `-a` and MCP | Single change fixing the worst inversion across 3 audit areas    | Medium |
| Detect CAPTCHA/bot-wall pages; emit explicit `blocked` error + non-zero exit; unify error shapes across MCP tools                 | Silent empties make every downstream answer untrustworthy        | Low    |
| Normalize numerics in all JSON/MCP output: `price_value`/`price_min`/`price_max` + `currency`, `rating` float, `review_count` int | The whole point is AI consumption; numerics remove parsing guess | Low    |
| Keep `None` fields as explicit `null`; return `{"error": "parse_failed"}` instead of `{}` for invalid objects                     | "Unknown" ≠ "missing" ≠ "parser broke"                           | Low    |
| Fix locale-aware decimal parsing in `get_prices()`                                                                                | 100× silent errors in 10 regions                                 | Low    |

### P1 — Expose what's already extracted

| Item                                                                                                       | Why                                                      | Effort |
| ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ------ |
| CLI table: numeric rating + review count (`4.6 (2,341)`), index column, wider/full titles                  | Restores the trust signals; data already parsed          | Low    |
| `--reviews`/`--level` flag on `-a` mode (unlock `DetailLevel.REVIEWS` from CLI)                            | Reviews are a stated priority; CLI is the only blocker   | Low    |
| Parse embedded top reviews from the product page (unused `TOP_REVIEWS` selector) at BASIC level            | Sidesteps the login wall on `/product-reviews/`          | Medium |
| Availability enum (`in_stock`/`low_stock`/`ships_later`/`unavailable`/`unknown`) + full phrase incl. dates | Binary `True` hides "Only 2 left" and "ships in 6 weeks" | Low    |
| `is_sponsored` flag + strip marker from titles                                                             | The AI should discount ads when ranking                  | Low    |
| Enrich MCP `get_reviews` with `average_rating`, `review_count`, `star_distribution`                        | One call should suffice to judge review quality          | Low    |

### P2 — Shape tools around the decision loop

| Item                                                                                                  | Why                                                         | Effort                                                                  |
| ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------- |
| MCP `compare_products(asins)` — side-by-side price / rating / count / distribution / availability     | The exact final step of every decision; today N calls       | Medium                                                                  |
| Sort & filter: `--sort price\                                                                         | rating\                                                     | reviews`, `--min-rating`, `--max-price`, `--available-only` (CLI + MCP) |
| Review fetch controls: `sortBy=recent`, `filterByStar=critical`, `max_reviews` cap                    | Critical reviews are the most informative; cap saves tokens | Medium                                                                  |
| `--markdown` output format; JSON as ordered `results: []` array with query metadata                   | Purpose-built for the paste-into-AI-chat workflow           | Low                                                                     |
| MCP stdio transport + documented one-line Claude Code/Desktop registration                            | Kills the daemon-babysitting friction                       | Low                                                                     |
| Slim search payloads: `limit` (default ~10), drop `image_url`/`extras` by default; docstring rewrites | Several-fold token savings per search                       | Low                                                                     |
| Multi-page fetch (`-p 1-3`) and `-n` limit in CLI                                                     | Core already supports page ranges                           | Low                                                                     |

### P3 — Quality of life

| Item                                                                                  | Why                                                 | Effort |
| ------------------------------------------------------------------------------------- | --------------------------------------------------- | ------ |
| Short-TTL local HTML cache (`~/.cache/amzsear/`, `--no-cache`)                        | Faster compare sessions, fewer bot walls            | Medium |
| Lightweight local price history (`(asin, timestamp, price)` JSONL) + MCP history tool | Directly answers "is this a good price?"            | Medium |
| Prime badge + seller-type extraction from search cards                                | Decision-grade trust signals                        | Low    |
| Screening flags: `low_review_count`, `polarized_distribution`, `low_verified_share`   | All inputs already extracted; heuristics only       | Low    |
| ISO-normalize review dates (keep raw)                                                 | Enables recency-trend judgment                      | Low    |
| Real-HTML regression fixtures for price/availability/review extraction                | Selector rot currently caught by bad purchases      | Medium |
| Fix/rename `feature_ratings`; implement or remove `DetailLevel.FULL` (Q&A)            | Honesty of the API surface                          | Low    |
| Region default via `AMZSEAR_REGION` env; localize availability patterns or document   | Less per-call boilerplate; no silent regional wrong | Low    |
| Polish: `-s` ISBN heuristic, `query`+`-a` warning, help epilog examples, regions doc  | Removes small traps                                 | Low    |

### Explicitly not recommended (out of scope)

Auth/proxy rotation infrastructure, hosted deployment, metrics/observability, alerting/restock-watch services, multi-region arbitrage, sentiment-analysis pipelines, fake-review ML detection, plugin systems — all enterprise-flavored complexity for a personal tool.
