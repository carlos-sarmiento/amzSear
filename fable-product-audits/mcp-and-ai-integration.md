# Product Audit: MCP Server & AI-Assistant Integration

**Scope:** `amzsear/mcp/server.py`, `amzsear/mcp/__init__.py`,
`tests/test_mcp_server.py`, `docs/mcp/README.md`, plus `core/` data model. **Use
case audited against:** a personal AI assistant calls these tools so the user
can choose good products, prioritizing **availability, pricing, and reviews**.

---

## Summary

The MCP server is a thin, honest wrapper over the scraping core: 9 tools,
structured JSON output, sensible localhost-hardened Streamable HTTP. The
plumbing is good. The product gap is that the tools mirror the _library's_ API
rather than the _AI shopping loop_. There is no compare tool, no batch lookup,
no filtering/sorting, prices come back as unparsed strings with junk keys,
`None` fields are silently dropped from payloads (so the AI can't tell "out of
stock unknown" from "field missing"), and the most common failure mode — Amazon
serving a CAPTCHA page with HTTP 200 — produces a silent empty result instead of
an actionable error. Setup friction is also real: streamable HTTP only, no
stdio, so registering it with Claude Code/Desktop requires running and
babysitting a separate server process.

---

## Current Capabilities

### Tool inventory

| Tool                         | Parameters                                                     | Returns                                                  | Notes                                                                      |
| ---------------------------- | -------------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------- |
| `search_products`            | `query`, `page` (int/list), `region`, `select`, `detail_level` | `{query, page, region, count, products[]}`               | `detail_level > SEARCH` fetches detail pages for **every** result serially |
| `get_product`                | `asin`, `region`, `detail_level`                               | product dict (`title`, `prices`, `rating`, `details`, …) | Built from an ASIN shell; search-level fields stay empty                   |
| `get_reviews`                | `asin`, `region`                                               | `{asin, reviews_url, reviews, fetch_error}`              | Only tool that always surfaces `fetch_error`                               |
| `list_regions`               | —                                                              | `{default, regions}`                                     | 16 regions, default US                                                     |
| `build_search_url`           | `query`, `page`, `region`                                      | `{url}`                                                  | URL helper                                                                 |
| `build_product_url`          | `asin`, `region`                                               | `{url}`                                                  | URL helper                                                                 |
| `parse_search_html`          | `html`, `region`                                               | `{region, count, products[]}`                            | Offline parsing escape hatch                                               |
| `parse_product_details_html` | `html`                                                         | details dict                                             | Offline parsing escape hatch                                               |
| `parse_reviews_html`         | `html`                                                         | reviews dict                                             | Offline parsing escape hatch                                               |

### What works well

- **Structured output.** Tools return dicts; FastMCP emits `structuredContent`
  plus JSON text. No stringly-typed blobs at the protocol level.
- **Detail levels** (`SEARCH`/`BASIC`/`REVIEWS`/`FULL`) give the AI a knob for
  request cost, and accept both names and ints.
- **The data model is review-rich** when scraping succeeds: `average_rating`,
  `review_count`, `star_distribution`, `feature_ratings`, per-review
  `verified`/`helpful_count`, even Amazon's own AI `reviews_summary`
  (AmzProductDetails.py:26–42).
- **Availability is a first-class field** (`availability`, `is_available`)
  parsed best-effort from search cards — directly aligned with the user's #1
  priority.
- **The `parse_*_html` tools are a quietly great anti-blocking escape hatch**:
  when scraping is blocked, the user can save a page from their browser and have
  the AI parse it. This is underdocumented as a workflow.
- **Local security posture** is right-sized for personal use: localhost bind,
  DNS-rebinding protection, stateless HTTP.

---

## Gaps & Weaknesses

### 1. Silent failure when Amazon blocks scraping (worst AI-experience bug)

`fetch_html` (core/**init**.py:75–93) only raises on HTTP errors. Amazon's
standard bot response is an **HTTP 200 CAPTCHA page**, which parses to zero
products / an all-`None` details object. The AI then sees `{"count": 0}` or a
near-empty product dict and will confidently tell the user "no results found" or
"no reviews exist" — wrong, and unrecoverable without the user noticing. There
is no CAPTCHA/robot-check detection, no `blocked: true` signal, no hint to retry
or fall back to `parse_search_html`.

Related inconsistencies:

- `search_products` lets `FetchError` propagate as a raw exception
  (AmzSear.py:63 has no try/except), while `get_product`/`get_reviews` swallow
  it into a `fetch_error` string. Same failure, three different shapes for the
  AI.
- `get_product` only includes `fetch_error` when truthy; on a 200-CAPTCHA it is
  absent entirely.

### 2. `None` values vanish from payloads

`AmzBase.items()` skips `None` attributes, and `to_dict` builds from `items()`
(AmzBase.py:105–166). So a product that's in stock with unknown availability
returns _no_ `is_available` key at all — indistinguishable from "tool doesn't
track availability." For an AI making availability claims, "unknown" vs "missing
field" matters. Worse, an **invalid** object (`_is_valid == False`, e.g. parse
failure) returns `{}` from `items()` — the AI gets an empty dict with zero
explanation.

### 3. Prices are stringly-typed and messy

`prices` is a dict like `{"0": "$29.99", "1": "$39.99"}` — numeric junk keys
when Amazon doesn't label price types, raw currency strings, list price and sale
price undifferentiated (AmzProduct.py:101–112). The core has `get_prices()`
returning sorted floats but it is **not exposed via MCP**. For a "help me pick
by price" loop, the AI must regex-parse currency strings itself and guess which
price is current. There is no `price` (current), `list_price`, `currency`
normalization.

### 4. No tools shaped like the actual decision loop

The user's loop is: _search → narrow → compare 2–4 finalists → check
reviews/availability → decide._ Missing:

- **`compare_products(asins=[...])`** — today the AI must call `get_product` N
  times (N round-trips, N tool-call confirmations in some clients) and mentally
  join the results. A single batch tool returning a side-by-side of price /
  rating / review_count / availability is the highest-leverage missing tool.
- **Batch ASIN lookup** generally — every fetching tool is single-ASIN.
- **Search filters/sorting** — no `min_rating`, `max_price`, `prime_only`,
  `sort_by`. Amazon's URL supports `&rh=p_36:...` (price) and `&s=review-rank`
  etc.; the AI currently has to over-fetch and filter client-side, burning
  tokens.
- **Review summary tool** — `get_reviews` returns full review texts (each
  potentially thousands of tokens). There's no `max_reviews`, no `sort` (most
  helpful / most recent / critical), no star filter, and the page-level
  aggregates (`star_distribution`, `reviews_summary`) live on a _different_ tool
  (`get_product` at BASIC level). For "are the reviews good?", the AI ideally
  wants aggregates + top-3 helpful + top-3 critical in one cheap call.

### 5. Token efficiency

- `search_products` returns **every** product on the page with all fields
  (`image_url`, `extra_attributes`, `subtext`, …). No `limit`, no field
  selection. A typical Amazon page is ~16–60 results.
- `search_products` with `detail_level="FULL"` fetches product + reviews pages
  for _all_ results serially — dozens of HTTP requests and an enormous payload.
  Nothing in the docstring warns the LLM off this footgun.
- `get_reviews` has no pagination or count cap; review bodies are returned in
  full.
- `image_urls` on details can include the whole thumbnail gallery — useless
  tokens for a text-based decision.

### 6. Tool descriptions are too thin for reliable LLM tool selection

Docstrings are one-liners ("Search Amazon and return amzsear search-result
products."). Missing from descriptions: what `detail_level` values mean and cost
(extra HTTP requests), what `select` does (ASIN vs positional index — genuinely
ambiguous: `select="0"` is treated as an index, but what about a query for
ASIN-like strings?), that `page` accepts a list, which fields come back at each
level, and when to prefer `get_product` over `search_products(select=...)`. An
LLM choosing between 9 tools needs this in the schema. The `build_*_url` tools
also dilute the tool list — they're developer utilities, not shopping tools.

### 7. Pagination is blind

The response echoes `page` but provides no `total_results`, no `has_next_page`.
The AI can't know whether fetching page 2 is worthwhile. (`count` of deduped
results is the only signal.)

### 8. Transport/setup friction for personal use

- **Streamable HTTP only** — `main()` hardcodes `transport="streamable-http"`
  (server.py:265). For a personal tool used from Claude Code/Desktop, **stdio is
  the natural transport**: zero daemon management, one line of config
  (`claude mcp add amzsear -- uvx amzsear-mcp`). Today the user must start the
  server manually and keep it running. A `--transport stdio` flag is ~3 lines.
- Docs don't show how to register the server with any MCP client (claude-code,
  Claude Desktop config JSON) — only how to run it.
- `mcp = create_app()` at module import (server.py:253) does enable
  `mcp run amzsear.mcp.server`, but that's undocumented.

### 9. Region ergonomics (minor)

Default `US` is hardcoded. For a personal tool, an env var (`AMZSEAR_REGION`) or
`--region` server default would save the AI from passing `region` on every call
if the user shops on amazon.de/.co.uk. Invalid regions do raise a clear
`ValueError` — good.

### 10. Scraping robustness as it affects the AI (brief)

- Search-card parsing wraps everything in
  `@capture_exception(IndexError, default={})` (AmzProduct.py:79) — a single
  selector drift returns an _empty_ product silently rather than a partial one
  with a warning. Combined with gap #2, selector rot manifests as quietly
  shrinking/empty payloads, which the AI misreads as "Amazon has nothing."
- The price regex heuristic (matching any `span[class^="a"]` text that looks
  numeric) is fragile and can pick up non-price numbers — the AI has no way to
  detect this.
- The dedicated reviews page (`/product-reviews/`) increasingly requires login
  on Amazon; `get_reviews` may return empty for that reason with no signal
  distinguishing it from "no reviews."

---

## Prioritized Recommendations

Ordered by impact on the "AI helps me choose a product" loop.

| #   | Recommendation                                                                                                                                                                                                                                                                                                                                                                                         | Priority | Why (tied to use case)                                                                           |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------- | ------------------------------------------------------------------------------------------------ |
| 1   | **Detect blocking explicitly.** Sniff CAPTCHA/robot-check markers in fetched HTML; return `{"error": "blocked_by_amazon", "hint": "save the page in a browser and use parse_search_html"}` instead of empty results. Unify error shape across all tools (never raise raw from `search_products`).                                                                                                      | High     | Silent empties make the AI give confidently wrong answers about availability/results             |
| 2   | **Add `compare_products(asins, region)`** returning a compact side-by-side: title, current price, average_rating, review_count, star_distribution, is_available per ASIN.                                                                                                                                                                                                                              | High     | This is the exact final step of every product decision; today it costs N calls + manual joining  |
| 3   | **Normalize prices**: emit `price` (float), `list_price` (float), `currency`, keep raw strings under `prices_raw`. Expose existing `get_prices()` logic.                                                                                                                                                                                                                                               | High     | Pricing is a top-3 user priority; currency-string dicts with junk keys push parsing onto the LLM |
| 4   | **Keep `None`/unknown fields in payloads** (at minimum `is_available`, `availability`, `rating`, `prices` as explicit `null`), and return `{"error": "parse_failed"}` instead of `{}` for invalid objects.                                                                                                                                                                                             | High     | The AI must distinguish "out of stock," "unknown," and "parser broke"                            |
| 5   | **Add stdio transport** (`--transport stdio                                                                                                                                                                                                                                                       | http`, default stdio when no TTY args) and document one-line registration for Claude Code/Desktop. | High     |                                                                                                  |
| 6   | **Slim & cap search results**: `limit` (default ~10), drop `image_url`/`subtext`/`extra_attributes` unless `include_extras=true`; add `total_results`/`has_next_page` when parseable.                                                                                                                                                                                                                  | Medium   | Token cost per search drops several-fold; pagination becomes informed                            |
| 7   | **Upgrade `get_reviews`** with `max_reviews` (default ~10), `sort` (helpful/recent/critical), `star_filter`, and fold in the aggregates (`average_rating`, `star_distribution`, `reviews_summary`) so one call answers "are reviews good?".                                                                                                                                                            | Medium   | Reviews are a top-3 priority; full review dumps waste tokens and miss critical reviews           |
| 8   | **Rewrite tool docstrings for LLM consumption**: explain `detail_level` request costs, `select` semantics, when to use each tool; warn that `detail_level="FULL"` on search fetches every result. Consider hiding `build_*_url` or marking them as utilities.                                                                                                                                          | Medium   | Better tool selection, fewer wasted/expensive calls                                              |
| 9   | **Add `search_products` filters** (`max_price`, `min_rating`, `prime_only`, `sort_by`) mapped to Amazon URL params where possible, client-side filtered otherwise.                                                                                                                                                                                                                                     | Medium   | Cuts over-fetching; lets the AI narrow in one call                                               |
| 10  | **Region default via env/flag** (`AMZSEAR_REGION` / `--region`) applied as the server-wide default.                                                                                                                                                                                                                                                                                                    | Low      | One-time setup instead of per-call boilerplate                                                   |
| 11  | **Document the `parse_*_html` fallback workflow** ("if blocked: save page → parse") in the MCP README and in tool descriptions.                                                                                                                                                                                                                                                                        | Low      | Turns an existing hidden feature into the official anti-blocking story                           |

### Explicitly not recommended (out of scope for this user)

Auth/multi-tenant hardening, rate-limit middleware, hosted deployment,
metrics/observability — the localhost posture is already appropriate for a
personal tool.
