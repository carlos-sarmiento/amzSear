# CLI Audit — amzSear

**Scope:** `amzsear/cli/cli.py`, `amzsear/cli/__init__.py`, the `amzsear` entry point in `pyproject.toml`, and `docs/cli/README.md`.
**Date:** 2026-06-10. Read-only analysis; no fixes applied.

## Summary

The CLI is small and mostly functional, but has three High-severity issues: the `--select` heuristic misroutes all-numeric ASINs (real ISBN-10 ASINs exist), ASIN-lookup mode exits `0` on fetch failure with the error printed to stdout, and `--browser` in search mode opens the search-results page despite help text and docs promising product pages. There are several silent-argument-ignore UX traps (`query` + `--asin`, `--page`/`--select` in ASIN mode), an invisible empty-result state, doc/behavior mismatches, dead code, and pervasive reliance on private attributes of core objects.

| Severity    | Count |
| ----------- | ----- |
| Critical    |     0 |
| High        |     3 |
| Medium      |     6 |
| Low         |    10 |
| Suggestions |     5 |

The entry point itself is sound: `pyproject.toml:35` (`amzsear = "amzsear.cli.cli:run"`) resolves to `cli.py:16` and works when invoked with no arguments (defaults to `sys.argv`).

---

## High

### H1. `--select` misinterprets all-numeric ASINs as positional indexes
- **Where:** `amzsear/cli/cli.py:39-44`
- `if item_key.isdigit():` routes the value to `out.rget(int(item_key))`, otherwise to ASIN lookup. Amazon book ASINs are ISBN-10s, which are frequently all-numeric (e.g. `0439708184`). For such an ASIN the CLI computes `rget(439708184)` and either raises `IndexError` ("Error: Index out of range - list index out of range") or, for short numeric ASINs that happen to be in range, silently selects the **wrong product**.
- **Impact:** A documented use case (docs/cli/README.md:30, 57 — "Select result by ASIN or numeric index") is broken for an entire class of real ASINs; the wrong-product case is silent data corruption for scripts using `-s ... -j`.
- Note: `isdigit()` also accepts non-ASCII Unicode digits, and `-s -1` (negative index, supported by `rget`) is instead treated as an ASIN and fails with `KeyError`.

### H2. ASIN mode (`--asin`) exits 0 on fetch failure, error goes to stdout
- **Where:** `amzsear/cli/cli.py:84-92, 224-225, 246-247, 272-274`; root cause in `amzsear/core/AmzProduct.py:254-259` (`fetch_details` swallows `FetchError` into `_fetch_error`).
- The `try/except FetchError` in `run()` (cli.py:60-62) never fires for ASIN mode because `fetch_details` catches the exception internally. The CLI then prints `Error: ...` via `print()` (stdout, not stderr) and returns normally → **exit code 0**.
- **Impact:** Inconsistent with search mode (network failure → stderr + exit 1). Scripts checking `$?` see success on network errors, 404s for bad ASINs, etc.; piping stdout captures the error text as if it were data. In `--json` mode the error is embedded in the JSON (acceptable) but the exit code is still 0.

### H3. `--browser` in search mode opens the search page, not product pages
- **Where:** `amzsear/cli/cli.py:56-58, 114-115`; `docs/cli/README.md:32, 71-77`
- Without `--select`, `out._urls` contains the search-results URL(s) (set in `AmzSear.__init__`, core/AmzSear.py:60), so `webbrowser.open` opens the Amazon search page. Both the `-b` help text ("Open the product page in the default browser") and docs Example 4 ("open the product pages in the default browser") promise product pages.
- **Impact:** Doc/behavior mismatch and misleading `--help` output. Behavior only matches documentation when combined with `-s`.

---

## Medium

### M1. `query` plus `--asin` together: query (and `-p`, `-s`) silently ignored
- **Where:** `amzsear/cli/cli.py:24-26, 71-95`
- `amzsear 'Harry Potter' -a B00006IFHD -p 2 -s 0` runs a pure ASIN lookup; the query, page, and select arguments are dropped without any warning or error.
- **Impact:** Confusing UX; users can't tell which mode ran. A `parser.error` on conflicting arguments would be cheap.

### M2. Empty result set produces only a header row, exit 0
- **Where:** `amzsear/cli/cli.py:170-206` (`print_short`), `129-145` (`print_json` prints `{}`)
- When Amazon serves a captcha/robot page with HTTP 200, parsing yields zero products. The short formatter prints a lone `ASIN Title Prices Rating Available` header line; JSON prints `{}`. No message, no non-zero exit.
- **Impact:** The most common real-world failure mode (bot detection) is indistinguishable from "search succeeded with no styling". Users get no hint to retry or change region.

### M3. Region choices are case-sensitive in the CLI but not in the core
- **Where:** `amzsear/cli/cli.py:111-112` vs `amzsear/core/__init__.py:63` (`region.upper()`)
- `amzsear foo -r us` fails argparse validation (`invalid choice: 'us'`) even though the core normalizes case.
- **Impact:** Needless friction; trivially fixed with `type=str.upper`.

### M4. Docs: usage block and option list omit `-V/--version`
- **Where:** `docs/cli/README.md:16-21, 26-34` vs `amzsear/cli/cli.py:122-124`
- The documented usage string and "Optional Args" list don't mention `-V/--version` at all.
- **Impact:** Docs drift; users discover the flag only via `--help`.

### M5. Docs: "typing `amzsear` without any additional arguments" no longer shows extended usage
- **Where:** `docs/cli/README.md:14` vs `amzsear/cli/cli.py:29-30`
- Bare `amzsear` now triggers `parser.error('query is required (or use --asin ASIN)')`: short usage + error on stderr, exit code 2 — not the "extended amzSear usage" the docs describe (that requires `-h`).
- **Impact:** Doc/behavior mismatch.

### M6. No ASIN format validation
- **Where:** `amzsear/cli/cli.py:73-79`
- `--asin` accepts any string and interpolates it into `PRODUCT_URL % (base_url, asin)`. `--asin 'foo/bar?x=1'` builds a nonsense URL and produces a confusing fetch error (or, combined with H2, a "successful" exit 0). ASINs have a strict shape (`[A-Z0-9]{10}`).
- **Impact:** Bad error messages for typos; an early `parser.error` would be clearer.

---

## Low

### L1. Dead code: `isinstance(value, dict)` branch unreachable in `print_verbose`
- **Where:** `amzsear/cli/cli.py:152-160`
- The first branch `hasattr(value, 'items')` is true for plain dicts too, so the `isinstance(value, dict)` branch at line 157 can never execute. (Output happens to be identical, so it's harmless dead code.)

### L2. Errors printed to stdout in product formatters
- **Where:** `amzsear/cli/cli.py:247, 273`
- `print(f"Error: {product._fetch_error}")` should go to `sys.stderr` for consistency with `run()`'s handlers (cli.py:61-67). Related to H2.

### L3. CLI pokes private attributes of core objects
- **Where:** `amzsear/cli/cli.py:46 (out._urls), 57 (out._urls), 80-81 (product._region, product._is_valid), 224, 246, 272 (product._fetch_error)`
- The CLI hand-assembles a "valid" `AmzProduct` and rewrites `AmzSear._urls`. Any core refactor breaks the CLI silently. The fetch-error channel (`_fetch_error`) is an undocumented private contract.

### L4. Denylist filtering of args passed to `AmzSear` is fragile
- **Where:** `amzsear/cli/cli.py:33`
- `{x: y for x, y in args.items() if x not in ['select', 'verbose', 'json', 'browser', 'asin']}` — any new CLI flag that isn't added to this list leaks into `AmzSear(**amz_args)` as an unexpected kwarg (`TypeError`). An allowlist (`query`, `page`, `region`) would be robust.

### L5. `run(*passed_args)` signature is error-prone
- **Where:** `amzsear/cli/cli.py:16-19`
- `run(['query'])` works, but `run('query')` makes argparse iterate the string character-by-character, and `run('a', 'b')` passes `'b'` as the `namespace` argument of `parse_args` and crashes. A plain `run(argv=None)` would be conventional.

### L6. Dead fallback: `args.get('region', DEFAULT_REGION)`
- **Where:** `amzsear/cli/cli.py:74`
- `region` always exists in the namespace (argparse default), so the fallback is unreachable.

### L7. No `--page` validation
- **Where:** `amzsear/cli/cli.py:107-108`
- `-p 0` and negative pages are accepted and interpolated straight into the search URL. Docs say "defaults to 1" but never define valid range.

### L8. No `BrokenPipeError` / `KeyboardInterrupt` handling
- **Where:** `amzsear/cli/cli.py:16-68`
- `amzsear foo | head -1` can dump a `BrokenPipeError` traceback; Ctrl-C during the (up to 30 s) fetch prints a raw traceback instead of a clean exit.

### L9. `print_product_short` hides a 0.0 rating
- **Where:** `amzsear/cli/cli.py:285`
- `if details.average_rating:` is falsy for a legitimate `0.0`, omitting the Rating line. Edge case; `is not None` would be exact.

### L10. Docs nits
- **Where:** `docs/cli/README.md:3, 29`
- Line 3: link `[original version](../../legacy/v1)` is broken — no `legacy/` directory exists in the repo. Same line has a grammar slip ("and backwards has been maintained").
- Line 29 documents `-p NUM, --page NUM` while actual metavar is `PAGE` (`-p PAGE`); trivially inconsistent with `--help`.

---

## Suggestions

### S1. Redundant/unhelpful `IndexError` message
`amzsear/cli/cli.py:66-67` prints `Error: Index out of range - list index out of range`. Catch it at the select site and say something actionable, e.g. `select index 12 out of range (16 results, 0-15)`.

### S2. Expose detail level in ASIN mode
`run_product` hardcodes `DetailLevel.BASIC` (`cli.py:84`) even though the core supports `REVIEWS`/`FULL`. A `--level` flag (or `--reviews`) would surface existing API capability; docs Example 6 says the lookup "returns ... review statistics", which only partially holds at BASIC level.

### S3. Distinguish the header row in `print_short`
`cli.py:173` prints the header as just another row with no separator; with `--json` available this is fine for humans but a `---` underline or stderr header would help readability and make stdout cleanly parseable.

### S4. JSON short product output gives no failure signal when details are missing
`print_product_json` (`cli.py:220-237`): when fetch "succeeded" but parsing produced an invalid/empty `details`, output is just `{"asin": ..., "product_url": ...}` — indistinguishable from a deliberate minimal answer. Text mode says "No details available"; JSON should carry an equivalent flag.

### S5. No CLI test coverage
`tests/` contains only `test_product_availability.py` and `test_mcp_server.py`. `get_parser()`/`run()` are easily testable with `run(['query', '-j'])`-style invocations and HTML fixtures; H1, H2, and M1 would all have been caught by basic tests.
