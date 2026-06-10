# FABLE-AUDIT — amzSear Codebase Audit

**Date:** 2026-06-10
**Project:** amzSear v3.0.1 — unofficial Amazon search CLI, Python API & MCP server
**Method:** Four independent read-only audits by parallel agents, one per area. No code was modified.

## Source Reports

| Report                                                                       | Area                                       | Critical | High   | Medium | Low    | Suggestions |
| ---------------------------------------------------------------------------- | ------------------------------------------ | -------- | ------ | ------ | ------ | ----------- |
| [fable-audits/core-library.md](fable-audits/core-library.md)                 | `amzsear/core/` + package root             | 3        | 8      | 12     | 10     | 8           |
| [fable-audits/cli.md](fable-audits/cli.md)                                   | `amzsear/cli/` + CLI docs                  | 0        | 3      | 6      | 10     | 5           |
| [fable-audits/mcp-server.md](fable-audits/mcp-server.md)                     | `amzsear/mcp/` + MCP docs                  | 0        | 3      | 7      | 8      | 6           |
| [fable-audits/tests-docs-packaging.md](fable-audits/tests-docs-packaging.md) | `tests/`, `docs/`, packaging, repo hygiene | 0        | 5      | 9      | 7      | 6           |
| **Total**                                                                    |                                            | **3**    | **19** | **34** | **35** | **25**      |

---

## Executive Summary

The codebase is small (~2,200 LOC) and structurally reasonable, but the audit surfaced three themes that cut across every layer:

1. **Silent failure everywhere.** Fetch errors are swallowed into a private `_fetch_error` attribute, broad `capture_exception(IndexError)` discards partially-parsed products, captcha/empty pages are indistinguishable from "no results", and the CLI exits `0` on ASIN-mode fetch failures. Users and LLM clients cannot tell "no data" from "blocked/broken".
2. **US-English-only parsing despite 16 advertised regions.** Rating, price, and review-count parsing assume `1,234.56` formatting and English text. EU-format prices crash `get_prices` with `ValueError`; German ratings silently parse `4,5` as `45.0`.
3. **Near-zero test and doc coverage of the actual product.** The scraping core and CLI have no tests at all (including no regression test for the already-fixed multi-page bug), and the published API docs describe the pre-v3 numeric-index API that now raises `KeyError`.

Additionally, one feature is provably dead (`_set_repr_max_len` is a no-op), the all-numeric-ASIN (ISBN-10) selection bug exists identically in both the CLI and the MCP server, and the MCP server blocks its event loop on every request while allowing unbounded request amplification against Amazon.

---

## Critical Findings

### CR-1. `AmzSear._set_repr_max_len` is a complete no-op
`amzsear/core/AmzSear.py:108-112` — `__iter__` yields ASIN strings, not products; the `hasattr(product, 'REPR_MAX_LEN')` guard is always false, so the method silently does nothing. The CLI feature that depends on it is broken. *(core C1)*

### CR-2. Multi-page search aborts on first failed page; dead `is not None` check
`amzsear/core/AmzSear.py:62-65`, `amzsear/core/__init__.py:75-93` — `fetch_html` never returns `None` (it raises `FetchError`), so the guard is dead code. One 503/captcha on page 3 of 5 raises out of the constructor and discards pages 1-2. Given Amazon's throttling, this is the common case. *(core C2)*

### CR-3. Locale-broken number parsing produces silently wrong data
`amzsear/core/AmzRating.py:81,99-118`, `amzsear/core/AmzProduct.py:198-200` — German `"4,5"` parses as `45.0` (rating percentage becomes 0.11 for a 4.5-star product); `"1.234"` counts collapse to `1`; EU price `"1.234,56 €"` crashes `get_prices` with `ValueError`. Worse than failing — values look plausible. *(core C3, H4)*

---

## High Findings

### Cross-cutting

| ID   | Finding                                                                                                                                                                                                                               | Locations                                                                                                | Source                     |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------- |
| HI-1 | **All-numeric ISBN-10 ASINs misrouted as positional indexes** by the `isdigit()` select heuristic → `IndexError` or silently the *wrong product*; bug duplicated in two layers                                                        | `amzsear/cli/cli.py:39-44`; `amzsear/mcp/server.py:80-83`                                                | CLI H1, MCP M2             |
| HI-2 | **Fetch errors invisible:** `fetch_details` swallows `FetchError` into private, undocumented `_fetch_error` (overwritten, absent from `to_dict`/`repr`); CLI exits 0 with error on stdout; "blocked" indistinguishable from "no data" | `amzsear/core/AmzProduct.py:254-268`; `amzsear/cli/cli.py:84-92,224-274`; `amzsear/mcp/server.py:40,117` | core H6, CLI H2, MCP L2/L3 |

### Core library

| ID   | Finding                                                                                                                                                                                                 | Location                                |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| HI-3 | Constructor arg hierarchy inverted vs docs: lower-level args overwrite higher ones; wasted network fetch for `query`/`url`                                                                              | `amzsear/core/AmzSear.py:44-84`         |
| HI-4 | `capture_exception(IndexError, default={})` drops entire products when any one sub-element (e.g. image) is missing                                                                                      | `amzsear/core/AmzProduct.py:79-128`     |
| HI-5 | Price-detection regex: false positives (dates, model numbers become "prices") and false negatives (no-decimal currencies ¥/₹ dropped); `h3[data-attribute]` price-name selector targets pre-2019 markup | `amzsear/core/AmzProduct.py:102-112`    |
| HI-6 | Star-distribution regex `(\d)\s*star\s*(\d+)%` cannot match plural "stars" — feature effectively broken                                                                                                 | `amzsear/core/AmzProductDetails.py:189` |
| HI-7 | Shared mutable defaults in `requires_valid_data(default=[])` — one list shared across all invalid instances for process lifetime                                                                        | `amzsear/core/AmzBase.py:97,109,119`    |
| HI-8 | `AmzBase.get`/`__contains__` raise misleading `KeyError` for declared-but-unparsed attributes; `get()` ignores `_is_valid` while `keys()` honors it                                                     | `amzsear/core/AmzBase.py:46-52,74-95`   |

### CLI

| ID   | Finding                                                                                                          | Location                                                          |
| ---- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| HI-9 | `--browser` in search mode opens the search-results page while `--help` and docs Example 4 promise product pages | `amzsear/cli/cli.py:56-58,114-115`; `docs/cli/README.md:32,71-77` |

### MCP server

| ID    | Finding                                                                                                                                                                              | Location                                |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------- |
| HI-10 | All 9 tools are sync `def`s doing blocking `requests` I/O (30 s timeout) directly on the asyncio loop — one slow fetch freezes the whole stateless HTTP server                       | `amzsear/mcp/server.py:174-227`         |
| HI-11 | Unbounded request amplification: uncapped `page` list × `fetch_details` on *every* result when `select` absent → one call can fire thousands of sequential requests to Amazon        | `amzsear/mcp/server.py:70,85-87`        |
| HI-12 | No authentication + `--host 0.0.0.0` accepted and whitelisted; Host-header DNS-rebinding check is spoofable by direct LAN clients → unauthenticated network-reachable scraping proxy | `amzsear/mcp/server.py:152-168,239-258` |

### Tests / docs / packaging

| ID    | Finding                                                                                                                        | Location                      |
| ----- | ------------------------------------------------------------------------------------------------------------------------------ | ----------------------------- |
| HI-13 | Zero tests for the entire core package (`AmzSear`, `AmzRating`, `AmzBase`, `AmzProductDetails`, `AmzReviews`, URL builders)    | `tests/`                      |
| HI-14 | Zero CLI test coverage (307 untested lines; HI-1, HI-2, HI-9 would all have been caught)                                       | `amzsear/cli/cli.py`          |
| HI-15 | No regression test for the multi-page bug fixed in commit `a6cb91e` — testable fully offline via `AmzSear(html=[...])`         | `tests/`                      |
| HI-16 | `docs/core/AmzSear.md` documents the old numeric-index API; its own example `amz.get(0)` raises `KeyError` on current code     | `docs/core/AmzSear.md:73-148` |
| HI-17 | `docs/core/AmzProduct.md` omits half the v3 API surface: `availability`, `details`, `reviews`, `get_asin()`, `fetch_details()` | `docs/core/AmzProduct.md`     |

---

## Medium Findings

### Core library

| ID    | Finding                                                                                                                                                | Location                                            |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------- |
| ME-1  | Legacy pre-2018 search URL form and dated selector set (`h3[data-attribute]`, exact-class matches, `getparent()` walks)                                | `amzsear/core/consts.py:30`; `AmzProduct.py:89-122` |
| ME-2  | `extra_attributes` zip-pairing heuristic shifts the whole key/value mapping on one unpaired span                                                       | `amzsear/core/AmzProduct.py:120-122`                |
| ME-3  | Product validity check nearly always true (`_index`/`prices`/`extra_attributes` always set) — `is_valid()` meaningless                                 | `amzsear/core/AmzProduct.py:74-77,125`              |
| ME-4  | `AmzReviews` total-count selector is a product-page selector; reviews pages also require login since ~2023 — login interstitial parses as "no reviews" | `amzsear/core/AmzReviews.py:180,197-202`            |
| ME-5  | `data-a-dynamic-image` JSON blob appended raw to `image_urls` as a "URL"                                                                               | `amzsear/core/AmzProductDetails.py:151`             |
| ME-6  | Three detail-table selectors merged without precedence — duplicate parses and last-wins key collisions                                                 | `amzsear/core/AmzProductDetails.py:122-134`         |
| ME-7  | Query interpolated with `safe='/'` and unvalidated `page_num` → broken slash-queries and URL parameter smuggling                                       | `amzsear/core/__init__.py:46`                       |
| ME-8  | `AmzSear(url=...)` fetches arbitrary absolute URLs verbatim — SSRF-shaped surface when exposed via MCP                                                 | `amzsear/core/AmzSear.py:58-65`                     |
| ME-9  | `aget` `raise_error`/`default` are dead for all declared attributes; awkward tuple-list return shape                                                   | `amzsear/core/AmzSear.py:162-190`                   |
| ME-10 | `AmzSear.__repr__` truncates the index separator (quote-count miscounted) — always-wrong output                                                        | `amzsear/core/AmzSear.py:88-92`                     |
| ME-11 | `helpful_count`/`verified` conflate "absent/unparseable" with real `0`/`False`; regex misses localized text                                            | `amzsear/core/AmzReviews.py:112-127`                |
| ME-12 | No HTTP session reuse, retries, or delay — cold TCP+TLS per page; classic captcha-trigger profile                                                      | `amzsear/core/__init__.py:88-93`                    |

### CLI

| ID    | Finding                                                                                        | Location                             |
| ----- | ---------------------------------------------------------------------------------------------- | ------------------------------------ |
| ME-13 | `query` + `--asin` together: query, `-p`, `-s` silently ignored, no warning                    | `amzsear/cli/cli.py:24-26,71-95`     |
| ME-14 | Empty result set (the common captcha case) prints only a header row / `{}`, exit 0, no message | `amzsear/cli/cli.py:129-145,170-206` |
| ME-15 | Region choices case-sensitive in CLI (`-r us` rejected) though core normalizes case            | `amzsear/cli/cli.py:111-112`         |
| ME-16 | Docs omit `-V/--version` from usage and option list                                            | `docs/cli/README.md:16-34`           |
| ME-17 | Docs claim bare `amzsear` shows extended usage; it now errors with exit 2                      | `docs/cli/README.md:14`              |
| ME-18 | No ASIN format validation — garbage `--asin` values build nonsense URLs with confusing errors  | `amzsear/cli/cli.py:73-79`           |

### MCP server

| ID    | Finding                                                                                                                                                              | Location                              |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| ME-19 | IPv6 allow-list pattern `::1:*` can never match bracketed `[::1]:port` Host headers → HTTP 421 on IPv6 loopback                                                      | `amzsear/mcp/server.py:154-163`       |
| ME-20 | No ASIN validation: malformed ASINs return silent empty responses (no fetch, no error); ASINs with path/query chars injected verbatim into "canonical" returned URLs | `amzsear/mcp/server.py:59-65,115,130` |
| ME-21 | `get_reviews` makes a redundant product-page request, discards its result, and fails on the wrong URL when it errors                                                 | `amzsear/mcp/server.py:110-118`       |
| ME-22 | Import-time side effects: module-level `mcp = create_app()` registers 9 tools and mutates global logging; `main()` ignores it                                        | `amzsear/mcp/server.py:253`           |
| ME-23 | Error message advertises integer detail levels (`0-3`) that the `Literal` tool schema rejects; int branch is dead code                                               | `amzsear/mcp/server.py:45-56`         |
| ME-24 | `parse_*_html` tools crash unhelpfully on empty input or XML encoding declarations; no size cap on `html`                                                            | `amzsear/mcp/server.py:133-149`       |

### Tests / docs / packaging

| ID    | Finding                                                                                           | Location                       |
| ----- | ------------------------------------------------------------------------------------------------- | ------------------------------ |
| ME-25 | `docs/regions.md` missing the `AE` region (15 of 16 listed)                                       | `docs/regions.md:3-19`         |
| ME-26 | No docs at all for publicly-exported `AmzProductDetails`, `AmzReviews`/`AmzReview`, `DetailLevel` | `docs/core/`                   |
| ME-27 | README flagship example shows 4 columns; CLI prints 5 (`Available`) — README contradicts itself   | `README.md:14-26,76-78`        |
| ME-28 | README still announces "Version 2" at v3.0.1; no mention of 3.x breaking changes                  | `README.md:7,42-46,160-187`    |
| ME-29 | README references deleted `amazon_screenshot.png` — broken image on GitHub and PyPI               | `README.md:28`                 |
| ME-30 | `docs/cli/README.md` links to deleted `legacy/v1` directory                                       | `docs/cli/README.md:3`         |
| ME-31 | Stale `dist/amzsear-2.0.{0,1}.tar.gz` tracked in git (only the *obsolete* versions are committed) | `dist/`                        |
| ME-32 | `docs/.DS_Store` committed; no `.DS_Store` ignore rule                                            | `docs/.DS_Store`; `.gitignore` |
| ME-33 | No CI, no lint/format config, no dev/test dependency group — despite a fast hermetic test suite   | repo root                      |

---

## Low Findings (condensed)

| ID    | Finding                                                                                                                     | Location                                                            | Source                     |
| ----- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | -------------------------- |
| LO-1  | Dual `try absolute / except ImportError relative` import pattern in every module; re-executed inside methods per parse call | all core modules                                                    | core                       |
| LO-2  | `to_dict(flatten=True)` ignores documented `recursive` requirement; nested keys silently overwrite parent keys              | `amzsear/core/AmzBase.py:138-166`                                   | core                       |
| LO-3  | Fragile `%`-style repr padding in `AmzBase.__repr__`                                                                        | `amzsear/core/AmzBase.py:58-60`                                     | core                       |
| LO-4  | O(n) `__contains__`/`__len__`/`get` via parallel lists instead of a dict                                                    | `AmzBase.py:40-47`; `AmzSear.py:129-136`                            | core                       |
| LO-5  | `get_star_repr` banker's rounding: 4.5 stars renders as 4                                                                   | `amzsear/core/AmzRating.py:142`                                     | core                       |
| LO-6  | Brand cleanup mangles names containing "Store"; locale variants unhandled                                                   | `amzsear/core/AmzProductDetails.py:101-104`                         | core                       |
| LO-7  | `get_asin` misses `/gp/product/` URLs → silent product drops                                                                | `amzsear/core/AmzProduct.py:211`                                    | core                       |
| LO-8  | Dead code: `QA_URL`, `QUERY_BUILD_DICT`, Q&A selectors, publicly-exported `DetailLevel.FULL` does nothing extra             | `consts.py:28,35`; `selectors.py:16,56-58`; `AmzProduct.py:270-273` | core                       |
| LO-9  | `lxml_html_clean` declared but never imported by core                                                                       | `pyproject.toml`                                                    | core                       |
| LO-10 | Scraped text (titles/reviews) propagated unsanitized — ANSI-escape terminal-injection vector                                | `AmzProduct.py:90`; `AmzBase.py:54-72`                              | core                       |
| LO-11 | Unreachable `isinstance(value, dict)` branch in `print_verbose`                                                             | `amzsear/cli/cli.py:152-160`                                        | CLI                        |
| LO-12 | Fetch errors printed to stdout instead of stderr in product formatters                                                      | `amzsear/cli/cli.py:247,273`                                        | CLI                        |
| LO-13 | CLI pokes core privates (`_urls`, `_region`, `_is_valid`, `_fetch_error`) — silent breakage on refactor                     | `amzsear/cli/cli.py:46,57,80-81,224-272`                            | CLI                        |
| LO-14 | Denylist (not allowlist) filtering of kwargs into `AmzSear(**amz_args)` — new flags leak as `TypeError`                     | `amzsear/cli/cli.py:33`                                             | CLI                        |
| LO-15 | `run(*passed_args)` signature: `run('query')` iterates the string char-by-char                                              | `amzsear/cli/cli.py:16-19`                                          | CLI                        |
| LO-16 | Dead fallback `args.get('region', DEFAULT_REGION)` (argparse default always present)                                        | `amzsear/cli/cli.py:74`                                             | CLI                        |
| LO-17 | No `--page` validation (`-p 0`, negatives accepted)                                                                         | `amzsear/cli/cli.py:107-108`                                        | CLI                        |
| LO-18 | No `BrokenPipeError`/`KeyboardInterrupt` handling — raw tracebacks on `\                                                    | head` or Ctrl-C                                                     | `amzsear/cli/cli.py:16-68` |
| LO-19 | `if details.average_rating:` hides a legitimate 0.0 rating                                                                  | `amzsear/cli/cli.py:285`                                            | CLI                        |
| LO-20 | Docs nits: broken `legacy/v1` link, metavar mismatch (`NUM` vs `PAGE`), grammar slip                                        | `docs/cli/README.md:3,29`                                           | CLI                        |
| LO-21 | Dead branch in `transport_security` (`0.0.0.0` update adds values already present)                                          | `amzsear/mcp/server.py:155-156`                                     | MCP                        |
| LO-22 | Inconsistent `fetch_error` shape between tools (key sometimes omitted, sometimes `null`)                                    | `amzsear/mcp/server.py:40-41,117`                                   | MCP                        |
| LO-23 | Price dict can carry a `None` key into `structuredContent`                                                                  | `amzsear/mcp/server.py:24-32`                                       | MCP                        |
| LO-24 | Raw core exceptions leak as tool errors ("list index out of range"; `FetchError` may embed proxy details)                   | `amzsear/mcp/server.py:76-87`                                       | MCP                        |
| LO-25 | `page=0`/negative/duplicate pages accepted and echoed verbatim                                                              | `amzsear/mcp/server.py:70,89-92`                                    | MCP                        |
| LO-26 | `get_product` with `detail_level="SEARCH"` is a documented no-op                                                            | `amzsear/mcp/server.py:98-107`; `docs/mcp/README.md:28-29`          | MCP                        |
| LO-27 | `amzsear/mcp/__init__.py` exports nothing despite promising "MCP server support"                                            | `amzsear/mcp/__init__.py`                                           | MCP                        |
| LO-28 | Availability tests pin exact matched-text casing — coupled to regex internals                                               | `tests/test_product_availability.py:27,33`                          | tests                      |
| LO-29 | Availability coverage tests 3 of 13 patterns; ordering and false-positive hazards untested                                  | `tests/test_product_availability.py`                                | tests                      |
| LO-30 | MCP tests skip error paths, parse tools, `transport_security`, `details_level` rejection                                    | `tests/test_mcp_server.py`                                          | tests                      |
| LO-31 | Development on Python 3.14 but classifiers stop at 3.13; 3.10 floor never exercised                                         | `pyproject.toml:15-19`                                              | tests                      |
| LO-32 | `AmzRating.md` documents `"4.5/5"` format the parser never produces                                                         | `docs/core/AmzRating.md:7-8`                                        | tests                      |
| LO-33 | README claims "Python version 3 or greater"; real floor is 3.10                                                             | `README.md:34`                                                      | tests                      |
| LO-34 | FastMCP `log_level="ERROR"` doesn't silence low-level `mcp.server` INFO logs in tests                                       | `tests/test_mcp_server.py:46,64,88`                                 | tests                      |
| LO-35 | LICENSE copyright year stale (2017) — harmless                                                                              | `LICENSE.txt`                                                       | tests                      |

---

## Key Improvement Suggestions (consolidated)

1. **Make failures visible.** Public `fetch_error` (or raise-by-default), per-page error collection in `AmzSear`, captcha/login-interstitial detection in `fetch_html` with a distinct `FetchError` subclass, non-zero CLI exit codes, stderr for errors. *(addresses CR-2, HI-2, ME-4, ME-14)*
2. **Add a locale-aware number parser** shared by `AmzRating`, `get_prices`, and review counts. *(fixes CR-3 at the root)*
3. **Fix ASIN selection once, in core:** match `^[A-Z0-9]{10}$` before falling back to positional indexing; validate ASIN at CLI/MCP boundaries. *(HI-1, ME-18, ME-20)*
4. **Use `requests.Session` with retry/backoff** and optional politeness delay; consider connection reuse for multi-page and detail fetches. *(ME-12)*
5. **MCP hardening:** `async def` tools running impls via `anyio.to_thread`, cap `page` list and per-call detail fetches, refuse/warn on non-loopback binds or add token auth, offer stdio transport. *(HI-10–HI-12)*
6. **Build an HTML-fixture test harness** (`tests/fixtures/` with one search, product, and reviews page) — closes most of HI-13–HI-15 in one step, as `AGENTS.md` already mandates.
7. **Add minimal CI** (uv sync + unittest on 3.10 and latest, plus ruff) — the suite is already fast and hermetic.
8. **One docs refresh pass:** regenerate `docs/core/*.md` from the (accurate) source docstrings, fix README version messaging/image/columns, add the `AE` region, document `AmzProductDetails`/`AmzReviews`/`DetailLevel`. *(HI-16, HI-17, ME-25–ME-30)*
9. **Repo hygiene:** `git rm --cached` the stale dist tarballs and `.DS_Store`, add ignore rules; single-source the version via hatchling dynamic versioning; consider making MCP an optional extra (`amzsear[mcp]`).
10. **Structural cleanups:** dict-backed `AmzSear` instead of parallel lists, move network I/O out of constructors (`from_query`/`from_html` classmethods — also fixes HI-3), centralize all selectors in `selectors.py`, narrow `capture_exception` scope, delete dead code (Q&A selectors, `DetailLevel.FULL`, dual-import fallbacks).
