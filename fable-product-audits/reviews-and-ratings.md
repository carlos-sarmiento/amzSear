# Product Audit: Reviews & Ratings

**Project:** amzSear — personal Amazon product-info tool for AI-assisted purchase decisions
**Area:** Reviews & ratings features
**Date:** 2026-06-10
**Scope:** `amzsear/core/AmzReviews.py`, `AmzRating.py`, `AmzProductDetails.py`, `AmzProduct.py`, `selectors.py`, `cli/cli.py`, `mcp/server.py`, docs, tests

---

## Summary

amzSear has a solid *skeleton* for reviews and ratings — three layers of data (search-card rating, product-page review stats, dedicated reviews-page parsing) with sensible models. But the plumbing between the layers and the surfaces (CLI, JSON, MCP) leaks most of the value:

- **The CLI cannot fetch review text at all.** `--asin` mode hard-codes `DetailLevel.BASIC` (cli.py:84) and search mode never calls `fetch_details`, so `AmzReviews` is reachable only via MCP or the Python API.
- **Star-rating precision is destroyed in the default CLI view** (`get_star_repr` rounds 4.3 and 4.7 both to 4 or 5 asterisks) and the review *count* — the single most important trust signal — is absent from the search table.
- **Rating data is exposed to AI as unparsed display strings** (`"4.5 out of 5 stars"`, `"43,116"`) instead of the numeric values the library already knows how to compute.
- **Only one page (~10) of reviews is fetched, with no sort/filter control**, no top-positive/top-critical split, no date normalization, and no rating-distribution context in the `get_reviews` MCP response.
- Several extracted fields are well-chosen for the use case (verified badge, helpful votes, star histogram, Amazon's own AI review summary) — they just need to actually reach the user/AI.

For the user's stated goal — *"load Amazon product info so an AI can help me choose good products"* — the highest-leverage fixes are about exposure and precision, not new scraping.

---

## Current Capabilities

### Data extracted today

| Layer                                   | Source page    | Fields                                                                                                                                                           |
| --------------------------------------- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AmzRating` (per search result)         | Search results | `ratings_text` ("4.5 out of 5 stars"), `ratings_count_text`; helpers: `get_perc()`, `get_numerator()`, `get_count()`                                             |
| `AmzProductDetails` (DetailLevel BASIC) | Product page   | `average_rating` (float), `review_count` (int), `star_distribution` ({5: 85, ...} percentages), `reviews_summary` (Amazon AI summary)                            |
| `AmzReviews` / `AmzReview` (REVIEWS)    | Reviews page   | Per review: reviewer, rating (float), title, date (raw text), full text, verified-purchase bool, helpful_count, images; collection: total_count, feature_ratings |

### Surfaces

| Surface                  | What you get                                                                                      |
| ------------------------ | ------------------------------------------------------------------------------------------------- |
| CLI search (short)       | Star glyphs only (`****`), rounded to whole stars; no count                                       |
| CLI search (json)        | `rating.to_dict()` → raw text strings only                                                        |
| CLI `--asin` (short)     | `4.8/5 (43,116 reviews)` — good format, but BASIC level only                                      |
| MCP `search_products`    | Optional `detail_level` up to FULL → full nested dicts incl. reviews                              |
| MCP `get_product`        | Same, per ASIN                                                                                    |
| MCP `get_reviews`        | Reviews-page parse only (review list + total_count + feature_ratings)                             |
| MCP `parse_reviews_html` | Offline parsing of user-supplied HTML — a nice escape hatch when live fetch is blocked/logged-out |

### Genuine strengths

- The `AmzReview` model captures exactly the right per-review signals for AI judgment: full text, verified badge, helpful votes, per-review star rating.
- `star_distribution` and `reviews_summary` (Amazon's own AI-generated summary) on the product page are high-value, low-cost extractions — one request gets both.
- `DetailLevel` enum gives clean cost control (0–3 HTTP requests).
- `parse_reviews_html` acknowledges the real-world problem that Amazon gates review pages.

---

## Gaps & Weaknesses

### 1. Reviews are unreachable from the CLI

- `run_product` hard-codes `DetailLevel.BASIC` (cli.py:84). There is no `--reviews` / `--level` flag anywhere in `get_parser()`.
- Search mode never calls `fetch_details` at all.
- Result: the documented `AmzReviews` capability is invisible to a CLI user. Only MCP and direct Python use can see review text.

### 2. Precision and trust signals lost in CLI output

- Search table shows `get_star_repr()` — rounds to nearest whole star. 3.6 and 4.4 both render as `****`. For comparing candidate products this erases the exact signal the user cares about.
- Review **count** is not shown in the search table at all. A 4.8 with 12 ratings and a 4.8 with 40,000 ratings look identical. This directly undermines the "flag low-review-count items" need.
- `print_json` (short) emits `rating.to_dict()` = `{"ratings_text": "4.5 out of 5 stars", "ratings_count_text": "43,116"}`. The library already has `get_numerator()` / `get_count()`; the JSON forces the AI to re-parse locale-dependent strings (decimal commas in DE/FR regions will break naive parsing).

### 3. `get_reviews` MCP response lacks context for judgment

- Returns only the review list, `total_count`, and `feature_ratings`. No `average_rating`, no `star_distribution` — an AI must make a second `get_product` call to know whether 10 sampled reviews are representative.
- `feature_ratings` is mislabeled: docstring promises `{"Sound quality": 4.5}` but the parser captures mention *counts* like `"2K"` (AmzReviews.py:204-216). An AI consuming this will misinterpret counts as ratings.

### 4. Single-page, uncontrolled review sample

- `fetch_details` fetches `product-reviews/<ASIN>` once — first ~10 reviews in Amazon's default sort. No pagination, no sort (`recent` vs `helpful`), no star filter (`filterByStar=critical`), no "top positive / top critical" pair.
- For AI-assisted choice, the *critical* reviews are the most informative; today the sample is whatever Amazon front-loads (usually positive-skewed).
- Note: Amazon now commonly requires sign-in for `/product-reviews/` — the BASIC product page (which embeds ~8 top reviews under the existing `TOP_REVIEWS` selector `[data-hook="review"]`) is the more reliable source, but `AmzProductDetails` never parses them even though the selector is already defined (selectors.py:42, unused).

### 5. Review recency not computable

- `AmzReview.date` keeps the raw locale string ("December 3, 2024" — or German/French text in other regions). No ISO normalization, so "are recent reviews worse than old ones?" — a classic quality-trend check — requires the AI to guess date formats.

### 6. Q&A is a stub

- `DetailLevel.FULL` is accepted everywhere (CLI types, MCP `Literal`) but the Q&A fetch is commented out (AmzProduct.py:270-273). The QA selectors in selectors.py:56-58 are generic placeholders. FULL silently behaves as REVIEWS — a small honesty problem in the API surface.

### 7. No comparison or screening aids

- Nothing compares review profiles across the candidate set (the core decision workflow: search → shortlist → compare).
- No flagging of low-review-count or suspicious profiles (e.g., high average + tiny count + 0% verified in sample, or bimodal 5★/1★ distributions). The ingredients (count, distribution, verified flags) are all extracted already — only the presentation is missing.

---

## Prioritized Recommendations

Ordered by impact on the user's workflow (availability/pricing/reviews for AI-assisted choice), weighted by effort. All are personal-scale; nothing enterprisey.

### P1 — Expose what's already extracted

1. **Add review count + numeric rating to the CLI search table.** Replace `****` with `4.6 (43,116)` (or append count to stars). One-line-ish change in `print_short`; restores the most important trust signal.
2. **Emit numeric rating in short JSON.** In `print_json`, output `{"value": 4.5, "max": 5, "count": 43116}` (from `get_numerator`/`get_denominator`/`get_count`) alongside or instead of the raw text. Removes locale-parsing burden from the AI.
3. **Add a `--level`/`--reviews` CLI flag** so `amzsear --asin X --reviews` fetches `DetailLevel.REVIEWS` and prints review titles/text. Today the CLI silently caps at BASIC.
4. **Enrich `get_reviews` MCP output** with `average_rating`, `review_count`, and `star_distribution` (either parse them from the reviews page header or piggyback the product-page values). One MCP call should be self-sufficient for quality judgment.

### P2 — Make the review sample trustworthy

5. **Parse the embedded top reviews from the product page** using the already-defined-but-unused `TOP_REVIEWS` selector, populating `AmzReviews` at `DetailLevel.BASIC`. This sidesteps the login wall on `/product-reviews/` and makes review text available in the single-request path.
6. **Support sort/filter on the reviews fetch**: `sortBy=recent` and `filterByStar=critical|positive` URL params, exposed as MCP tool args (`get_reviews(asin, sort=..., star_filter=...)`). Fetching "top critical" is the single best addition for AI judgment.
7. **Normalize review dates to ISO** (keep raw text too). Enables recency-weighted assessment ("recent reviews mention a quality drop").
8. **Fix or rename `feature_ratings`** — it currently returns mention counts, not ratings. Either parse actual aspect sentiment or rename to `feature_mentions`.

### P3 — Decision-support features

9. **Comparison output**: a CLI/MCP convenience that, given 2–5 ASINs, returns a side-by-side table of rating, count, star distribution, % verified in sample, and top critical themes. This is the user's actual workflow; today the AI must orchestrate N calls and merge.
10. **Lightweight screening flags** computed from existing fields, attached to product dicts: `low_review_count` (count < threshold), `polarized_distribution` (1★ + 5★ ≫ middle), `low_verified_share` (sample-based). Heuristics only — clearly labeled, no ML, fits personal scale.
11. **Either implement or remove `DetailLevel.FULL` (Q&A).** Q&A content ("does this fit X?") is genuinely useful for purchase decisions, but if it stays unimplemented, the API should not advertise it.

### Explicitly not recommended

- Review pagination beyond 2–3 pages, sentiment-analysis pipelines, or fake-review ML detection — beyond personal scale and the AI consumer can do qualitative judgment from a well-chosen sample.

---

## Quick Reference: Gap → Recommendation

| Gap                                             | Rec # | Effort | Impact |
| ----------------------------------------------- | ----- | ------ | ------ |
| Review count missing from CLI search table      |     1 | Low    | High   |
| Rating as display string in JSON                |     2 | Low    | High   |
| Reviews unreachable from CLI                    |     3 | Low    | High   |
| `get_reviews` lacks rating/distribution context |     4 | Low    | High   |
| Reviews page often login-gated                  |     5 | Medium | High   |
| No critical-review access                       |     6 | Medium | High   |
| Dates not machine-readable                      |     7 | Low    | Medium |
| `feature_ratings` mislabeled                    |     8 | Low    | Medium |
| No multi-product comparison                     |     9 | Medium | High   |
| No low-count / polarization flags               |    10 | Low    | Medium |
| `DetailLevel.FULL` is a silent no-op            |    11 | Low    | Low    |
