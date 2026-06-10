# Audit: amzSear MCP Server

Scope: `amzsear/mcp/server.py`, `amzsear/mcp/__init__.py`, `docs/mcp/README.md`, the
`amzsear-mcp` entry point in `pyproject.toml`, plus the MCP layer's integration points with
`amzsear/core/`. SDK in use: `mcp` 1.27.1 (FastMCP, Streamable HTTP).

## Summary

The MCP server is a thin, mostly clean FastMCP wrapper around the amzsear core: 9 tools, a
separate `*_impl` layer that is unit-testable, structured output via dict return types, and
deliberate DNS-rebinding protection. The biggest problems are concurrency (every tool is a
sync `def` doing blocking `requests` I/O directly on the event loop), unbounded request
amplification (`page` lists × per-product detail fetches with no caps), the complete absence
of authentication combined with a `--host` flag that lets the server be bound to non-localhost
interfaces, and several correctness bugs (IPv6 allow-list pattern that can never match, all-digit
ISBN ASINs misrouted by the `select` heuristic, no ASIN validation leading to silent no-op
responses). Doc/behavior mismatches are minor.

Finding counts:

| Severity    | Count |
| ----------- | ----- |
| Critical    |     0 |
| High        |     3 |
| Medium      |     7 |
| Low         |     8 |
| Suggestions |     6 |

---

## High

### H1. All tools are synchronous and block the asyncio event loop during network I/O

- `amzsear/mcp/server.py:174-227` (every `@app.tool()` is a plain `def`)
- `amzsear/mcp/server.py:76`, `:87`, `:106`, `:112` (network calls inside impls)
- Integration: `amzsear/core/__init__.py:89` (`requests.get(..., timeout=30)`)

FastMCP calls sync tool functions directly on the event loop (see
`mcp/server/fastmcp/utilities/func_metadata.py:93-96` — non-async functions are invoked
inline, not via `anyio.to_thread`). `search_products`, `get_product`, and `get_reviews` perform
blocking `requests.get` calls with a 30 s timeout each. The server is configured as
`stateless_http=True` Streamable HTTP (`server.py:245`), i.e. explicitly intended to serve
concurrent requests — yet a single slow Amazon response freezes the entire server, including
protocol-level traffic (`initialize`, `tools/list`) from other clients.

Impact: one in-flight scrape stalls every other request; with detail fetching over a full
results page (see H2) the loop can be blocked for minutes.

Fix direction: declare the tools `async def` and run impls via `anyio.to_thread.run_sync`, or
use an async HTTP client in core.

### H2. Unbounded request amplification (no caps on pages or per-product detail fetches)

- `amzsear/mcp/server.py:70` (`page: int | list[int]` — list of arbitrary length)
- `amzsear/mcp/server.py:85-87` (detail fetch loop over **all** products when `select` is None)

`search_products(query, page=[1..50], detail_level="FULL")` issues 50 search-page requests,
then for every product found (typically 20–60 per page) 2 further requests (product page +
reviews page). A single tool call can trigger thousands of sequential HTTP requests to Amazon,
each blocking the event loop (H1), each up to 30 s. There is no upper bound on the `page` list
length, no limit on how many products get `fetch_details`, and no way to cancel.

Impact: trivially-triggered self-DoS; near-guaranteed Amazon rate-limiting/CAPTCHA/IP ban; an
LLM client can do this accidentally ("get full details for the first 10 pages").

Fix direction: cap `len(page)` (e.g. ≤ 5), require `select` (or add a `limit` param) before
allowing `detail_level > SEARCH`, or fetch details only for the first N products.

### H3. No authentication, and `--host` allows binding to non-localhost interfaces

- `amzsear/mcp/server.py:258` (`--host` accepts any value, e.g. `0.0.0.0`)
- `amzsear/mcp/server.py:152-168` (`transport_security` for `0.0.0.0` adds `0.0.0.0:*`,
  `localhost:*`, `127.0.0.1:*` to the allow-list)
- `amzsear/mcp/server.py:239-249` (no `auth=`/`token_verifier=` configured)

The HTTP transport has no authentication of any kind. On the default `127.0.0.1` bind that is
an accepted local-tool trade-off, but the CLI invites `--host 0.0.0.0` / LAN-IP binds, and
`transport_security()` dutifully whitelists whatever host is passed (`server.py:154`). Note that
DNS-rebinding protection only validates the *Host/Origin headers*, not the peer address — a LAN
attacker connecting to a `0.0.0.0`-bound server simply sends `Host: localhost:8765` and passes
validation. The result is an unauthenticated, network-reachable proxy for Amazon scraping from
the host's IP.

Impact: anyone on the network can drive requests through the server (traffic attribution, IP
reputation damage, resource abuse), with H1/H2 making it an effective DoS lever too.

Fix direction: refuse or loudly warn on non-loopback binds, and/or support a bearer token
(the SDK's `token_verifier`/`auth` settings) when binding beyond localhost. Docs should state
the server is unauthenticated.

---

## Medium

### M1. IPv6 loopback allow-list entry can never match (`::1:*` vs `[::1]:*`)

- `amzsear/mcp/server.py:154`, `:157`, `:158-163`

`transport_security` puts the bare string `"::1"` into `hostnames`, producing the patterns
`"::1:*"` and `"http(s)://::1:*"`. Actual IPv6 Host headers are bracketed (`[::1]:8765`), and
the SDK wildcard matcher checks `host.startswith(base_host + ":")` — `"[::1]:8765"` does not
start with `"::1:"`. The SDK's own auto-default uses `"[::1]:*"`
(`mcp/server/fastmcp/server.py:179-184`). Consequence: clients connecting via IPv6 loopback
get HTTP 421 even though the code clearly intends to allow them. Same bug applies when a user
passes any IPv6 literal as `--host`.

### M2. All-digit ASINs (ISBN-10s) are misrouted by the `select` heuristic

- `amzsear/mcp/server.py:80-83`

`select` is treated as a positional index when `isinstance(select, int) or
str(select).isdigit()`. ASINs for books are ISBN-10s and can be all digits (e.g.
`"0136019706"`). Such a select value is converted to `int("0136019706")` and used as a list
index, raising `IndexError: list index out of range` instead of looking up the product by ASIN.
There is no way to select these products by ASIN at all. (Also inconsistent: `select=-1` as an
int works as a relative index, but `select="-1"` as a string fails `isdigit()` and is treated
as an ASIN.)

Fix direction: match the ASIN shape explicitly (`re.fullmatch(r'[A-Z0-9]{10}', select)`) before
falling back to positional indexing, or split into two parameters (`select_asin`, `select_index`).

### M3. No ASIN validation: `get_product`/`get_reviews` silently return empty results

- `amzsear/mcp/server.py:59-65` (`product_for_asin` interpolates `asin` raw into the URL)
- Integration: `amzsear/core/AmzProduct.py:211` (`get_asin()` requires `[A-Z0-9]{10}` after `/dp/`),
  `amzsear/core/AmzProduct.py:245-247` (`fetch_details` returns silently when `get_asin()` is None)

A lowercase, too-short, or otherwise malformed `asin` (e.g. `"b08n5wrwnw"`) produces a product
shell whose `get_asin()` returns `None`; `fetch_details` then returns immediately **without
fetching and without setting `_fetch_error`**. `get_product` responds with just
`{"product_url": ..., "asin": null}` — no error, no hint. An LLM client will read this as "the
product has no data". Conversely, an `asin` containing extra path/query characters
(`"B000123456/ref=evil?x="`) is embedded verbatim into `product_url`, `reviews_url`
(`server.py:115`), and `build_product_url` output (`server.py:130`) — URL content injection into
values the client is told are canonical Amazon URLs — while the actual fetch uses the clean
regex-extracted ASIN, so the reported `reviews_url` can differ from the URL actually fetched.

Fix direction: validate `^[A-Z0-9]{10}$` (after `.upper()`) at the tool boundary and raise a
clear `ValueError`.

### M4. `get_reviews` makes a redundant product-page request and is coupled to its failure

- `amzsear/mcp/server.py:110-118`
- Integration: `amzsear/core/AmzProduct.py:252-268`

`get_reviews_impl` calls `fetch_details(level=DetailLevel.REVIEWS)`. Because
`REVIEWS.value >= BASIC.value`, core first fetches the **product page** (an extra HTTP request
whose result, `product.details`, is then discarded by the tool), and if that product-page fetch
fails, `fetch_details` returns early — the reviews page is **never requested**, and the tool
returns `reviews: null` with a `fetch_error` about the *product* URL. The tool's stated purpose
("Fetch customer reviews for an ASIN") is one request; it performs two and can fail on the
wrong one. This is an MCP-layer integration choice — core offers no reviews-only path, so either
add one or fetch/parse the reviews page directly in the impl (the pieces — `fetch_html`,
`AmzReviews` — are already imported).

### M5. Import-time side effects: module-level `mcp = create_app()`

- `amzsear/mcp/server.py:253`

Importing `amzsear.mcp.server` constructs a full FastMCP app (registering 9 tools) and — via
the FastMCP constructor — calls `configure_logging("INFO")`, mutating global logging state for
any process that merely imports the module (including the test suite and any future programmatic
consumer). `main()` (`server.py:264`) ignores this instance and builds a second app, so for the
documented entry point the module-level app is dead weight. If it exists to support `mcp dev`
/ `mcp run` discovery, that is undocumented; if not, it should be removed.

### M6. Error message and helper advertise integer detail levels the tool schema rejects

- `amzsear/mcp/server.py:45-56`, `:73`, `:101`

`details_level()` accepts ints and its `ValueError` says "must be SEARCH, BASIC, REVIEWS, FULL,
or 0-3", but the tool parameters are typed `Literal["SEARCH", "BASIC", "REVIEWS", "FULL"]`, so
pydantic rejects integers (and lowercase strings — `details_level` calls `.upper()`, but the
Literal validation fires first) before `details_level` ever runs. The int branch
(`server.py:49-52`) is dead code at the MCP boundary, and the error text is misleading in the
one place it can surface. Either widen the tool annotation to match the helper or simplify the
helper to match the annotation.

### M7. `parse_*_html` tools crash unhelpfully on realistic inputs

- `amzsear/mcp/server.py:133-149`

`lxml.html.fromstring(html)` raises `ParserError: Document is empty` on empty/whitespace input,
and `ValueError: Unicode strings with encoding declaration are not supported` when the pasted
page begins with an XML/encoding declaration — which saved Amazon pages can. These surface as
raw tool errors with no guidance. There is also no size bound on `html`; a multi-MB document is
parsed synchronously on the event loop (compounding H1). Validate non-empty input, strip
encoding declarations (or parse bytes), and consider a size cap.

---

## Low

### L1. Redundant/dead branch in `transport_security`

- `amzsear/mcp/server.py:155-156`

`hostnames` is initialized with `{"localhost", "127.0.0.1", "::1", host}`, so the
`if host == "0.0.0.0": hostnames.update({"localhost", "127.0.0.1"})` branch adds nothing —
both values are already present. Dead code.

### L2. Inconsistent `fetch_error` exposure between tools

- `amzsear/mcp/server.py:40-41` vs `:117`

`product_to_dict` includes `fetch_error` only when set; `get_reviews_impl` always includes the
key (value `null` on success). Clients see two different shapes for the same concept.

### L3. MCP layer reaches into core private attributes

- `amzsear/mcp/server.py:40` (`product._fetch_error`), `:63-64` (`_region`, `_is_valid`),
  `:117` (`_fetch_error`)

`product_for_asin` manufactures a "valid" product by poking `_is_valid` and `_region`, and the
serializers read `_fetch_error` directly. Any core refactor of these privates silently breaks
the MCP layer. Core should expose a public constructor-from-ASIN and a public `fetch_error`
accessor.

### L4. Price dict can carry a `None` key into structured output

- `amzsear/mcp/server.py:24-32`, integration: `amzsear/core/AmzProduct.py:107-112`

Core sets `d['prices'][price_names[i].text]` where `.text` can be `None`. `json_safe` copies
dict keys unmodified, so `structuredContent` can contain a `None` key, which serializes as the
string `"null"` (or trips strict validators downstream). `json_safe` should coerce non-string
keys.

### L5. Raw core exceptions leak as tool errors with poor messages

- `amzsear/mcp/server.py:81-83` (`IndexError: list index out of range`, bare `KeyError`),
  `:76`/`:87` (`FetchError` with full URL and underlying `requests` text)

FastMCP converts uncaught exceptions to `isError` results containing `str(exc)`. "list index
out of range" gives an LLM client nothing to act on; `FetchError` strings embed whatever
`requests` reports (which can include proxy details from the environment). Wrap selection errors
with context ("select=12 out of range; 8 results") and consider normalizing fetch errors.

### L6. `search_products` echoes unvalidated `page` and applies no sanity check

- `amzsear/mcp/server.py:70`, `:89-92`

`page=0`, negative pages, or duplicate page numbers are accepted and sent to Amazon verbatim;
the response echoes the raw input. Harmless but sloppy; combined with H2 a duplicate-heavy list
multiplies requests for identical content.

### L7. `get_product` with `detail_level="SEARCH"` is a documented no-op

- `amzsear/mcp/server.py:98-107`; `docs/mcp/README.md:28-29`

Docs advertise the `SEARCH` level for `get_product`, but with `SEARCH` no fetch happens and the
response is just `{"product_url": ..., "asin": ...}` — equivalent to `build_product_url` with
extra steps. Either document this or disallow `SEARCH` for this tool.

### L8. `amzsear/mcp/__init__.py` exports nothing

- `amzsear/mcp/__init__.py:1-2`

The package docstring promises "MCP server support" but exposes no API; consumers must import
the submodule. Re-exporting `create_app` / `main` (lazily, to avoid M5's side effects) would
make the package self-describing.

---

## Doc / behavior mismatches

- `docs/mcp/README.md:28-29` — advertises `SEARCH` detail level for `get_product`, which
  performs no fetch (L7).
- `docs/mcp/README.md:19` — "binds to localhost by default and enables DNS-rebinding
  protection" is accurate, but the docs never mention there is **no authentication** nor warn
  about `--host 0.0.0.0` (H3). The Host-header check is presented as the safety story; it is
  spoofable by direct network clients.
- `docs/mcp/README.md:26-27` — `search_products` docs omit the `select` semantics entirely
  (positional int vs ASIN string heuristic, M2) and that detail fetching applies to *every*
  result when `select` is absent (H2).
- `docs/mcp/README.md:38-39` — "Tool responses include `structuredContent` and a JSON text
  content item": correct for the current FastMCP version (dict returns generate an output
  schema), verified against SDK 1.27.1 behavior.
- Error text "or 0-3" (`server.py:56`) describes inputs the tool schema rejects (M6).

## pyproject.toml (entry point)

- `pyproject.toml:36` — `amzsear-mcp = "amzsear.mcp.server:main"` resolves correctly.
- `pyproject.toml:27` — `mcp[cli]>=1.27.1` is an unconditional runtime dependency. The `[cli]`
  extra pulls `typer`/dev tooling needed only for `mcp dev`-style workflows, and the base `mcp`
  package itself drags starlette/uvicorn/httpx into every plain CLI/API install of amzsear.
  Suggestion: move to an optional extra (`amzsear[mcp]`) with plain `mcp` (no `[cli]`), and a
  helpful ImportError in `amzsear.mcp.server`.
- `pyproject.toml:11-20` — classifiers stop at 3.13 while the project venv runs 3.14; cosmetic.

---

## Suggestions

1. **Offer stdio transport.** Most MCP clients spawn local servers over stdio;
   `main()` hardcodes `transport="streamable-http"` (`server.py:265`). A
   `--transport {stdio,streamable-http}` flag would make `amzsear-mcp` directly usable in
   Claude Desktop-style configs without an HTTP shim, and stdio sidesteps H3 entirely.
2. **Add tool annotations and parameter descriptions.** All nine tools are read-only and
   (except the three fetchers) side-effect free; `readOnlyHint=True` / `openWorldHint` and
   pydantic `Field(description=...)` on parameters would materially improve client behavior.
   Currently the schemas carry parameter names only.
3. **Cap and parallelize detail fetching.** After fixing H1/H2, fetch per-product details
   concurrently (bounded semaphore) instead of sequentially.
4. **Validate `region` eagerly at the tool boundary** with a `Literal` built from
   `REGION_CODES` keys, so invalid regions fail schema validation with the allowed values
   listed instead of a mid-flight `ValueError` (`amzsear/core/__init__.py:65`).
5. **Return ASIN-keyed results from `search_products`.** Products are already deduplicated by
   ASIN in core; including the ASIN list (or keying `products` by ASIN) would make the
   `select` round-trip workflow (search → pick ASIN → `get_product`) more reliable for LLMs.
6. **Test gaps.** `tests/test_mcp_server.py` covers tool listing, one URL builder, and one
   parse path. No coverage for: `details_level` edge cases, `select` routing (M2 would have
   been caught), `get_reviews` failure coupling (M4), IPv6 allow-list (M1), or error shapes.
