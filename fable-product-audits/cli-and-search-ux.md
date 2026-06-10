# Product Audit: Search & CLI User Experience

**Project:** amzSear — personal Amazon product lookup tool
**Audit area:** Search capabilities + CLI ergonomics
**Date:** 2026-06-10
**Use case audited against:** Loading Amazon product info (availability, pricing, reviews) for AI-assisted product choice. Personal tool — no enterprise/business features considered.

---

## Summary

The CLI does the basics well: search by query, page/region selection, select-by-ASIN-or-index, JSON output, browser open, and a separate ASIN lookup mode with a clean summary. However, as a tool for *choosing* products with AI help, it falls short in three ways:

1. **Decision data is thin or lossy.** The default table truncates titles at 50 chars, renders ratings as rounded stars (4.6 → `*****`, indistinguishable from 5.0), and omits review counts entirely — yet reviews are a stated priority. Review *content* is unreachable from the CLI even though the core library supports it (`DetailLevel.REVIEWS`).
2. **No way to narrow or order results.** No sorting (price/rating/review count), no filters (max price, min rating, availability-only), no result limit, no multi-page fetch — even though the core API already accepts page ranges. The user must eyeball a raw page-order list, which is exactly the work the tool should remove.
3. **Failure modes are silent.** A CAPTCHA/bot-wall page returns HTTP 200 with zero product cards, so the CLI prints an empty table and exits 0 — indistinguishable from "no results". This is the single worst UX trap for a scraping tool.

JSON output exists but is built from raw scraped strings (price text dicts with arbitrary keys, rating prose like `"4.5 out of 5 stars"`), making it noisy and unstable for piping into AI tools — the primary downstream consumer here.

---

## Current Capabilities

### Search mode (`amzsear QUERY`)

| Capability        | Flag           | Notes                                                       |
| ----------------- | -------------- | ----------------------------------------------------------- |
| Keyword search    | positional     | Single query, page-order results                            |
| Page selection    | `-p/--page`    | Single page only via CLI (core API accepts iterables)       |
| Region            | `-r/--region`  | 16 marketplaces, validated via `choices`, defaults US       |
| Select one result | `-s/--select`  | By ASIN or 0-based numeric index                            |
| JSON output       | `-j/--json`    | Short (essential fields) or verbose (`-jv`, full `to_dict`) |
| Browser open      | `-b/--browser` | Opens product URL (with `-s`) or search URL(s)              |
| Verbose text      | `-v/--verbose` | Full untruncated field dump per product                     |

### Product mode (`amzsear -a ASIN`)

Fetches the product page directly (`DetailLevel.BASIC` hard-coded): title, brand, rating + review count, top-3 "About this item" bullets, technical-detail count. `-v` and `-j` variants exist. Fetch errors surface as an `error` field rather than crashing.

### Error handling

`FetchError` (network/HTTP), `KeyError` (bad ASIN select), `IndexError` (bad index select) are caught, printed to stderr, exit code 1. Bad region or missing query → argparse error, exit 2.

---

## Gaps & Weaknesses

### A. Choosing products (the core job)

1. **No sorting.** Results print in Amazon page order — heavily sponsored/merchandised. Cannot sort by price, rating, or review count locally even though all three are parsed.
2. **No filtering.** Cannot say "min 4.2 stars", "under $50", "available only". Every comparison is manual.
3. **Review count invisible in default output.** `AmzRating.get_count()` exists but the table shows only a star glyph. A 4.8 with 12 reviews and a 4.8 with 40,000 reviews look identical.
4. **Star rendering loses precision.** `get_star_repr()` rounds to whole stars: 4.5–5.0 all render `*****`. The numeric value (`get_numerator()`) is available and should be shown (e.g. `4.6 (2,341)`).
5. **Titles truncated at 50 chars with no ellipsis or override.** Amazon titles front-load brand names; the distinguishing details (size, count, variant) are routinely cut off. No `--wide`/`--full-title` option short of `-v`'s wall of text.
6. **Review content unreachable from the CLI.** The core supports `DetailLevel.REVIEWS` (`AmzReviews`), but `run_product` hard-codes `DetailLevel.BASIC`. For a user whose priority is reviews, this is the largest missing surface: no `--reviews` flag to pull review text/distribution for an ASIN.
7. **No result-count control.** No `-n/--limit` to show top N; no multi-page fetch (`-p 1-3`) despite `AmzSear(page=range(...))` already working in the core.
8. **Availability is mostly "Unknown".** Search cards rarely carry explicit stock text, so the column the user cares about is usually noise at search level. The real signal lives on the product page, but `-a` mode's short output doesn't print availability at all — only search mode does.

### B. Output for AI consumption

9. **Short JSON is raw scrape text, not normalized data.** `prices` is a dict like `{"Paperback": "$8.37", "1": "$10.90"}` (arbitrary numeric keys when names are missing); `rating` is `{"ratings_text": "4.5 out of 5 stars", "ratings_count_text": "1,234"}`. Numeric helpers (`get_prices()`, `get_numerator()`, `get_count()`) exist but aren't used. AI tools get cleaner answers from `{"price_min": 8.37, "price_max": 10.90, "rating": 4.5, "review_count": 1234}`.
10. **JSON schema is unstable/asymmetric.** Search JSON keys differ from product-lookup JSON keys (`prices` vs none, `rating` object vs float). No top-level metadata (query, page, region, result count, fetched-at) — useful context when pasting into a chat.
11. **No markdown output.** Given the workflow is "paste into an AI chat", a `--markdown` table (full titles, numeric rating, review count, price range, URL) would be the highest-leverage output format. CSV is a cheaper nice-to-have.
12. **JSON keyed by ASIN, not a list.** An object keyed by ASIN loses result order in some consumers and is awkward to slice; a `results: [...]` array with `asin` fields is friendlier.

### C. Failure modes & trust

13. **Bot-detection produces silent empty success.** Amazon's CAPTCHA page is HTTP 200; `fetch_html` succeeds, zero cards parse, the CLI prints a header-only table and exits 0. The user can't tell "nothing matched" from "I'm blocked". Should detect CAPTCHA markers / zero-card pages, print a clear stderr message ("Amazon returned a robot check — try again later or use -b to open in browser"), and exit non-zero.
14. **Exit code 0 on zero results.** Even genuine empty result sets should arguably exit non-zero (grep-style) so shell scripts and AI agents can branch on it.
15. **No caching.** Every invocation re-hits Amazon — slow, and it increases bot-wall risk during an iterative compare session (the normal usage pattern: search, select 0, select 2, -a ...). A short-TTL on-disk cache of fetched HTML would make repeat queries instant and stealthier.

### D. Flag design & ergonomics

16. **`-s` digit heuristic misfires on numeric ASINs.** `item_key.isdigit()` routes all-digit inputs to index lookup, but older book ASINs (ISBN-10s like `0439708184`) are 10 digits. Rule should be: 10-char all-digit string → try ASIN first.
17. **`query` + `-a` conflict is silent.** `amzsear 'harry potter' -a B000X` silently ignores the query. Should warn or be a mutually-exclusive group.
18. **`-b` without `-s` opens search URLs**, not products — defensible, but undocumented and surprising; help text says "Open the product page".
19. **Help text is bare.** No examples in `--help` epilog, no mention that `-s` takes index *or* ASIN until you read docs, no hint that `-jv` differs from `-j`.
20. **No `--quiet`/color/TTY awareness.** Minor for personal use, but a numbered index column in the table (so `-s 3` is obvious without counting rows) is a near-free win.
21. **Docs drift:** `docs/regions.md` omits AE (United Arab Emirates), which the code supports.

---

## Prioritized Recommendations

Ranked by impact on the stated use case (availability, pricing, reviews → AI-assisted choice).

| #   | Recommendation                                                                                                        | Why it matters for this user                                               | Effort                                                      |
| --- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ----------------------------------------------------------- |
|   1 | **Detect CAPTCHA/empty pages; clear stderr message + non-zero exit**                                                  | Eliminates the "silent empty table" trust-killer                           | Low                                                         |
|   2 | **Add numeric rating + review count to default table** (e.g. `4.6 (2,341)` instead of `*****`)                        | Reviews are a top priority; data already parsed                            | Low                                                         |
|   3 | **Normalize JSON: numeric `price_min`/`price_max`, `rating`, `review_count`, results array, query metadata**          | The output is consumed by AI tools; clean numbers beat scrape prose        | Low                                                         |
|   4 | **Local sort & filter flags:** `--sort price                                                                          | rating                                                                     | reviews`, `--min-rating`, `--max-price`, `--available-only` |
|   5 | **`--reviews` flag on `-a` mode** exposing `DetailLevel.REVIEWS` (review text, rating distribution)                   | Core already supports it; CLI is the only blocker                          | Low                                                         |
|   6 | **`--markdown` output format** (full titles, numeric ratings, counts, prices, URLs)                                   | Purpose-built for pasting into AI chats                                    | Low                                                         |
|   7 | **Multi-page fetch (`-p 1-3`) and `-n/--limit`**                                                                      | Better candidate pool in one command; core API already accepts page ranges | Low                                                         |
|   8 | **Index column in table output** so `-s N` is visible at a glance                                                     | Removes row-counting friction in the select workflow                       | Low                                                         |
|   9 | **Short-TTL result cache** (`~/.cache/amzsear/`, with `--no-cache`)                                                   | Faster iterative comparing; fewer requests → fewer bot walls               | Medium                                                      |
|  10 | **Show availability in `-a` short output**; fix `-s` digit-ASIN heuristic; warn on `query`+`-a`; help epilog examples | Polish: aligns output with priorities, removes small traps                 | Low                                                         |

### Explicitly not recommended (out of scope for a personal tool)

- Multi-region price comparison, price-history tracking services, alerting/notification systems, auth/proxy rotation infrastructure, plugin systems, config files for team sharing. These add enterprise-flavored complexity the user doesn't want.
