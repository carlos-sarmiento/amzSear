# Audit: Tests, Documentation & Packaging — amzSear

Date: 2026-06-10 Scope: `tests/`, `pyproject.toml`, `uv.lock`, `.gitignore`,
`README.md`, `LICENSE.txt`, `AGENTS.md`, `docs/`, repo hygiene. Method: static
read-through of tests/docs against actual source in `amzsear/`; ran the existing
suite offline (`python -m unittest discover -s tests` — 9 tests, all pass, no
network).

## Summary

The two test files that exist are well-built (offline, deterministic, in-memory
MCP transport), but they cover only a thin slice of the codebase: availability
parsing and MCP plumbing. The core scraping/data classes (`AmzSear`,
`AmzRating`, `AmzBase`, `AmzProductDetails`, `AmzReviews`), the URL builders,
and the entire CLI have **zero tests** — including no regression test for the
multi-page bug that was explicitly fixed in commit `a6cb91e`. The docs are
substantially out of date with the v3 code: `docs/core/AmzSear.md` documents the
old numeric-index API while the code now keys products by ASIN, `AmzProduct.md`
omits five attributes and two public methods, the regions table is missing `AE`,
and two classes/one enum have no docs at all. Packaging is mostly sane (entry
points verified, versions consistent), but stale `dist/` tarballs and a
`.DS_Store` are committed, the README references an image that doesn't exist in
the repo, and there is no CI, no lint config, and no dev/test dependency group.

Finding counts: Critical 0 · High 5 · Medium 9 · Low 7 · Suggestions 6

---

## Critical

None. Nothing in scope is broken in a way that corrupts data or fails the build
today.

---

## High

### H1. No tests at all for the core package (`amzsear/core/`)

- **Where:** `tests/` (only `test_mcp_server.py`, `test_product_availability.py`
exist)
- **Description:** There is no test coverage for:
  - `AmzSear` construction (query→url→html→element→products hierarchy,
    `amzsear/core/AmzSear.py:44-84`), including ASIN deduplication
    (`AmzSear.py:80-84`) and product filtering (`AmzSear.py:74,79`)
  - `AmzSear` accessors: `get`/`rget`/`aget`/`items`/`indexes`/`to_dataframe`
    (`AmzSear.py:114-240`)
  - `AmzRating` parsing and all numeric methods (`get_numerator`,
    `get_denominator`, `get_count`, `get_perc`, `get_star_repr`)
    (`amzsear/core/AmzRating.py`)
  - `AmzBase` dict-like behavior, `to_dict(recursive/flatten)`,
    `requires_valid_data` semantics (`amzsear/core/AmzBase.py`)
  - `AmzProduct.get_prices` (incl. `KeyError` path, comma handling —
    `AmzProduct.py:170-200`) and `get_asin` (incl. `%2F`-encoded URLs —
    `AmzProduct.py:202-214`)
  - `build_url` / `build_base_url` (invalid region `ValueError`) and
    `fetch_html`'s `FetchError` wrapping (mockable via `requests` —
    `amzsear/core/__init__.py:41-93`)
  - `AmzProductDetails` and `AmzReviews` parsing (entire modules untested)
- **Impact:** The scraping core is the part most likely to break (Amazon HTML
drift, refactors), and any regression there is invisible until a live run fails.
Price parsing (`get_prices`) and rating extraction directly feed CLI output.

### H2. Zero CLI test coverage

- **Where:** `amzsear/cli/cli.py` (307 lines, untested)
- **Description:** No tests for argument parsing (`get_parser`), `-s`
ASIN-vs-numeric-index dispatch (`cli.py:38-44`), JSON output shape
(`print_json`, `cli.py:129-145`), short-format table (`print_short`,
`cli.py:170-206`), `format_availability` (`cli.py:209-216`), or error-exit paths
(`cli.py:60-68`). All of this is testable offline: `run('query', ...)` accepts
passed args, and output functions take an `AmzSear` built from `products=[...]`
or `html=...`.
- **Impact:** The CLI is the product's headline feature (it's the README's first
example). Output-format regressions (e.g. the `price_tup` min/max logic at
`cli.py:180-186`, which compares price _strings_ keyed by float lists) ship
silently.

### H3. No regression test for the multi-page fix

- **Where:** `tests/`; commit `a6cb91e` "Fix multi-page search keeping only last
page results"
- **Description:** A real, user-visible bug (multi-page search dropping pages)
was fixed, but no test pins the behavior. The fixed code path
(`AmzSear.py:69-84`, products `extend` across `html_element` list) is
exercisable fully offline by passing a list of two HTML strings to
`AmzSear(html=[...])` and asserting both pages' ASINs are present.
- **Impact:** The exact bug class that already bit users can silently regress.

### H4. `docs/core/AmzSear.md` documents the old numeric-index API; code is ASIN-keyed

- **Where:** `docs/core/AmzSear.md:73-94` (get), `:137-148` (rget), `:99-106`
(indexes) vs `amzsear/core/AmzSear.py:114-160,201-208`
- **Description:**
  - `get()` doc says _"Gets the AmzProduct by index ... key (str): The index
    number of the product"_ — the code keys by **ASIN** (`AmzSear.py:122`: "The
    ASIN of the product").
  - `rget()` doc example uses indexes `['0', '2', '4', '7']` — actual indexes
    are ASINs like `'B00728DYLA'` (code docstring at `AmzSear.py:142-144` shows
    the correct example).
  - The doc example `amz[0]` / `amz.get(0, ...)` (`AmzSear.md:78-81`) would
    raise `KeyError` in current code, since `str(0)` is never an ASIN index.
- **Impact:** Following the published API docs produces code that throws. This
is the primary API reference for the package.

### H5. `docs/core/AmzProduct.md` is missing half the current API surface

- **Where:** `docs/core/AmzProduct.md` vs
`amzsear/core/AmzProduct.py:50-65,202-275`
- **Description:** The doc omits:
  - Attributes: `availability`, `is_available`, `details`, `reviews` (all in
    `_all_attrs`, `AmzProduct.py:63-65`)
  - Methods: `get_asin()` (`AmzProduct.py:202`) and
    `fetch_details(level, region)` (`AmzProduct.py:216`) — the two headline v3
    features (ASIN lookup, detail levels)
  - Constructor signature: doc says `AmzProduct(html_element=None)`; actual is
    `AmzProduct(html_element=None, region=DEFAULT_REGION)` (`AmzProduct.py:67`)
- **Impact:** New v3 functionality (availability, product details, reviews) is
undiscoverable from the docs; users can't find `fetch_details` or `DetailLevel`
from the core docs at all.

---

## Medium

### M1. `docs/regions.md` is missing the `AE` region

- **Where:** `docs/regions.md:3-19` vs `amzsear/core/consts.py:7`
(`'AE': '.ae'`)
- **Description:** `REGION_CODES` contains 16 regions including `AE` (United
Arab Emirates); the table lists only 15. Ironically, `docs/cli/README.md:18`
_does_ show `AE` in the usage string.
- **Impact:** The page both READMEs link to as the authoritative region list is
incomplete.

### M2. No docs for `AmzProductDetails`, `AmzReviews`/`AmzReview`, or `DetailLevel`

- **Where:** `docs/core/` (only AmzBase/AmzProduct/AmzRating/AmzSear docs
exist); `docs/core/README.md:4-8` lists only those four classes
- **Description:** `amzsear/__init__.py:18-26` publicly exports
`AmzProductDetails`, `AmzReviews`, `AmzReview`, and `DetailLevel`, and the
README/MCP docs reference detail levels — but none have a docs page.
- **Impact:** Roughly half of the public API is undocumented.

### M3. README top example output omits the `Available` column the CLI actually prints

- **Where:** `README.md:14-26` vs `amzsear/cli/cli.py:171`
(`fields = ['ASIN','Title','Prices','Rating','Available']`)
- **Description:** The flagship example output shows 4 columns; the current CLI
prints 5. README text at `README.md:76-78` even describes the `Available`
column, contradicting its own example block.
- **Impact:** First thing users see doesn't match the tool's real output.

### M4. README is stuck on "Version 2"; package is 3.0.1

- **Where:** `README.md:7` ("Version 2 has been released!"), `README.md:42-46`
("upgrade to version 2"), `README.md:160-187` ("What's New in Version 2.0") vs
`pyproject.toml:3` / `amzsear/__init__.py:3` (3.0.1)
- **Description:** No mention of 3.x anywhere in README despite breaking API
changes (ASIN indexing, availability, MCP server, details fetching).
- **Impact:** Misleading release messaging on the PyPI/GitHub landing page; the
v2 feature table doesn't describe what 3.x changed or broke.

### M5. README references a missing image

- **Where:** `README.md:28` (`![Amazon Comparison Shot](amazon_screenshot.png)`)
- **Description:** `amazon_screenshot.png` does not exist anywhere in the repo
(removed with legacy cleanup, commit `fed553a`).
- **Impact:** Broken image on GitHub and on PyPI (README is the package
long-description, `pyproject.toml:5`).

### M6. `docs/cli/README.md` links to deleted `legacy/v1` directory and omits flags

- **Where:** `docs/cli/README.md:3` (`[original version](../../legacy/v1)`);
flags list `:26-34`
- **Description:** The `legacy/` tree was removed in commit `fed553a`, so the
link is dead. The optional-args list also omits `-V/--version` (exists at
`cli.py:122-124`). The usage block at `:17-20` likewise lacks `-V`.
- **Impact:** Dead link plus an undocumented flag in the canonical CLI
reference.

### M7. Stale build artifacts committed: `dist/amzsear-2.0.0.tar.gz`, `dist/amzsear-2.0.1.tar.gz`

- **Where:** `git ls-files` → `dist/amzsear-2.0.0.tar.gz`,
`dist/amzsear-2.0.1.tar.gz`; `.gitignore:9` ignores `dist/`
- **Description:** Two old sdists are tracked in git. They predate the `dist/`
ignore rule (ignore rules don't untrack files). The newer 3.0.1 artifacts in
`dist/` are untracked (correct), making the tracked set inconsistent — only the
_obsolete_ versions are in version control.
- **Impact:** Repo bloat, confusing release provenance, and the tarballs ship in
every clone.

### M8. `docs/.DS_Store` is committed

- **Where:** `git ls-files` → `docs/.DS_Store`; no `.DS_Store` rule in
`.gitignore`
- **Description:** macOS Finder metadata is tracked, and `.gitignore:1-13` has
no pattern to prevent more from being added.
- **Impact:** Junk in the repo; signals missing hygiene rules (`.DS_Store`
should be ignored globally in `.gitignore`).

### M9. No CI, no lint/format config, no dev/test dependency group

- **Where:** repo root — no `.github/workflows/`, no
`[dependency-groups]`/`[tool.uv] dev-dependencies` in `pyproject.toml:1-50`, no
ruff/flake8/mypy/pytest config anywhere
- **Description:** The 9 existing tests run offline in <0.1 s but nothing runs
them automatically. There's no pinned dev toolchain, so "run the tests" depends
on the runtime venv happening to have `mcp` + `lxml` installed.
- **Impact:** Regressions land unnoticed; contributors have no enforced
baseline. Given the tests are already fast and hermetic, CI is nearly free to
add.

---

## Low

### L1. Availability tests assert exact matched-text casing, coupling tests to regex internals

- **Where:** `tests/test_product_availability.py:27,33`
(`assertEqual(product.availability, "Currently unavailable")`, `"FREE
delivery"`) vs `AmzProduct.py:150-152,162-164` (`match.group(0)`)
- **Description:** The tests pin the exact substring (and its original casing)
returned by `re.search(...).group(0)`. That's fine as characterization, but the
meaningful contract is `is_available`; if the implementation ever normalizes the
text (e.g. lowercases or returns the canonical pattern), tests fail without
behavior change.
- **Impact:** Minor brittleness; consider asserting case-insensitively or only
on `is_available` plus non-None `availability`.

### L2. Availability coverage tests 3 of 13 patterns

- **Where:** `tests/test_product_availability.py` vs `AmzProduct.py:139-165`
- **Description:** Only "Currently unavailable", "FREE delivery", and the
unknown case are covered. Untested: `temporarily out of stock`, `out of stock`,
`no featured offers available`, `discontinued`, `sold out`, `only N left in
stock`, `in stock`, `ships from`, etc. Also untested: pattern _ordering_
(unavailable patterns win over available ones — `AmzProduct.py:149-152` runs
first) and the false-positive hazard that `not available` matches inside
unrelated card text.
- **Impact:** The branchy part of the availability classifier is unverified.

### L3. MCP tests only cover the offline tools; no error-path tests

- **Where:** `tests/test_mcp_server.py`
- **Description:** Good: in-memory session, no network, structuredContent
assertions. Missing: `details_level` rejection of bad values (`server.py:56`
raises `ValueError`); `list_regions_impl` / `build_search_url_impl` shapes;
`parse_product_details_html_impl` / `parse_reviews_html_impl` (pure offline
parsers, `server.py:142-149`); `transport_security("0.0.0.0")` branch
(`server.py:155-156`); `product_to_dict` `fetch_error` inclusion
(`server.py:40-41`). The network tools (`search_products`, `get_product`,
`get_reviews`) are reasonably untestable live, but their impls could be tested
with a mocked `fetch_html`.
- **Impact:** Roughly half the server module's logic is unasserted.

### L4. `tests/__pycache__/` exists for Python 3.14 but classifiers stop at 3.13

- **Where:** `tests/__pycache__/*.cpython-314.pyc`, `.venv/pyvenv.cfg` (3.14) vs
`pyproject.toml:15-19`
- **Description:** Development clearly happens on 3.14, but
`Programming Language :: Python :: 3.14` is absent from classifiers. (Pycache
itself is correctly git-ignored.)
- **Impact:** Cosmetic metadata gap on PyPI; also means the advertised-supported
floor (3.10) is likely never exercised locally.

### L5. `docs/core/AmzRating.md` example values don't match real data shape

- **Where:** `docs/core/AmzRating.md:7-8` (`ratings_text` e.g. `"4.5/5"`) vs
`AmzRating.py:16` (`"4.5 out of 5 stars"`) and `AmzRating.py:41-45` (validity
requires the "N out of N" form)
- **Description:** The documented example format `"4.5/5"` is not what the
parser produces or validates against.
- **Impact:** Minor doc inaccuracy.

### L6. README "Installation" claims "Python version 3 or greater"

- **Where:** `README.md:34` vs `pyproject.toml:21`
(`requires-python = ">=3.10"`)
- **Description:** Understates the real floor; pip on 3.9 would refuse or
resolve an old version.
- **Impact:** Misleading install guidance.

### L7. FastMCP test `log_level="ERROR"` doesn't suppress INFO logs

- **Where:** `tests/test_mcp_server.py:46,64,88`; observed in test run output
(`INFO Processing request of type CallToolRequest ...`)
- **Description:** Despite passing `log_level="ERROR"` to `create_app`, the
low-level `mcp.server` logger still emits INFO lines during tests (the setting
only affects FastMCP's own logger). Tests pass, but output is noisy.
- **Impact:** Noise only; could mask real warnings in CI logs.

---

## Suggestions

### S1. Add an HTML-fixture-based test harness

`AGENTS.md:34-38` already mandates "saved HTML fixtures or mocked `requests`
responses" — but no fixtures exist. Add `tests/fixtures/` with one saved search
page, one product page, and one reviews page, then write parser tests for
`AmzSear(html=...)`, `AmzProductDetails`, and `AmzReviews` against them. This
single step closes most of H1 and gives the MCP parse tools (L3) realistic
inputs.

### S2. Single-source the version

`3.0.1` is hand-duplicated in `pyproject.toml:3` and `amzsear/__init__.py:3`.
Use hatchling's dynamic version (`[tool.hatch.version] path =
"amzsear/__init__.py"` + `dynamic = ["version"]`) so they can't drift.

### S3. Consider making the MCP server an optional extra

`mcp[cli]>=1.27.1` (`pyproject.toml:27`) pulls a large dependency tree (uvicorn,
httpx, starlette, typer, …) into every `pip install amzsear`, even for users who
only want the scraper/CLI. An `amzsear[mcp]` extra with a lazy import in the
`amzsear-mcp` entry point would keep the base install light. Note
`amzsear/mcp/server.py:253` also instantiates `mcp = create_app()` at import
time — harmless today, but it makes the module import side-effectful.

### S4. Add minimal CI

A single GitHub Actions workflow running `uv sync && uv run python -m unittest
discover -s tests` on 3.10 and latest would catch both regressions and the
supported-floor question (L4). Add ruff for lint while at it, and record the
tooling in `AGENTS.md` per its own instruction (`AGENTS.md:51-52`).

### S5. Clean tracked artifacts

`git rm --cached dist/amzsear-2.0.0.tar.gz dist/amzsear-2.0.1.tar.gz
docs/.DS_Store`, and add `.DS_Store` to `.gitignore`. Also decide whether
`fable-audits/`/`fable-product-audits/` belong in the repo or in `.gitignore`.

### S6. Refresh README + docs/core in one pass

The doc drift (H4, H5, M1-M6, L5, L6) traces to the v3 rewrite not being
reflected in `docs/`. Since the source docstrings are already accurate and
detailed (e.g. `AmzSear.py:114-160`, `AmzProduct.py:216-238`), regenerating the
markdown docs from them — or at least diffing each `docs/core/*.md` against the
corresponding docstring — would fix nearly everything at once.

---

## Verification notes

- Test suite executed offline: `9 tests, OK (0.067s)` — no network access
observed; MCP tests use the SDK's in-memory transport (`mcp.shared.memory`),
availability tests use inline HTML strings. Both files comply with the
no-live-requests rule in `AGENTS.md`.
- Entry points verified: `amzsear.cli.cli:run` (`cli.py:16`) and
`amzsear.mcp.server:main` (`server.py:256`) both exist and match
`pyproject.toml:34-36`.
- Version consistency verified: `pyproject.toml:3` = `uv.lock` (`amzsear` entry)
= `amzsear/__init__.py:3` = 3.0.1.
- `LICENSE.txt` is a clean MIT text matching the `license = "MIT"` SPDX field;
copyright year (2017) is stale but harmless.
