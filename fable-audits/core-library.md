# Core Library Audit — `amzsear/core/`

**Date:** 2026-06-10 **Scope:** `AmzBase.py`, `AmzProduct.py`,
`AmzProductDetails.py`, `AmzRating.py`, `AmzReviews.py`, `AmzSear.py`,
`consts.py`, `selectors.py`, `core/__init__.py`, `amzsear/__init__.py`
**Method:** Read-only static analysis. No code was modified.

## Summary

The core package is a scraping library wrapping Amazon search/product/review
pages around a dict-like `AmzBase` hierarchy. The overall structure is
reasonable, but the parsing layer is heavily locale-biased (en-US only), several
regexes are broken or match the wrong things, one method
(`AmzSear._set_repr_max_len`) is entirely non-functional, the multi-page search
path crashes on any single page failure despite a dead `None` check that
suggests the author believed otherwise, and the broad
`capture_exception(IndexError)` pattern silently discards partially-parsed
products. Error reporting from `fetch_details` is effectively invisible to
callers (`_fetch_error` is private, undocumented, and overwritten).

| Severity    | Count |
| ----------- | ----- |
| Critical    | 3     |
| High        | 8     |
| Medium      | 12    |
| Low         | 10    |
| Suggestions | 8     |

---

## Critical

### C1. `AmzSear._set_repr_max_len` iterates indexes, not products — method is a no-op

**File:** `amzsear/core/AmzSear.py:108-112`

```python
def _set_repr_max_len(self, val):
    for product in self:                       # __iter__ yields ASIN strings!
        if hasattr(product, 'REPR_MAX_LEN'):   # str has no REPR_MAX_LEN
            product.REPR_MAX_LEN = val         # never executes
```

`AmzSear.__iter__` (line 99-100) yields `self._indexes` (ASIN strings), not
`AmzProduct` objects. The `hasattr` guard silently swallows the type mismatch,
so the method does nothing, ever. The CLI (which calls this to control output
width) is silently broken. Should iterate `self._products` / `self.products()`.

**Impact:** Feature completely non-functional; silent failure.

### C2. Multi-page search aborts on first failed page; dead `is not None` check

**File:** `amzsear/core/AmzSear.py:62-65`, `amzsear/core/__init__.py:75-93`

```python
for u in url:
    elem = fetch_html(build_url(u))
    if elem is not None:           # dead code: fetch_html never returns None
        html_element.append(elem)
```

`fetch_html` either returns an element or **raises `FetchError`** — it never
returns `None`. The guard is dead code and reveals an incorrect mental model:
when fetching e.g. `page=range(1, 6)`, a single 503/captcha on page 3 raises an
uncaught `FetchError` out of the constructor and discards results from pages 1-2
entirely. There is no partial-result handling, no retry, and no per-page error
collection. Given Amazon's aggressive bot throttling, this is the common case,
not the edge case.

**Impact:** Whole searches fail when any one page fails; data already fetched is
lost.

### C3. Rating parsing produces wildly wrong numbers in non-US locales

**File:** `amzsear/core/AmzRating.py:81`, `amzsear/core/AmzRating.py:99-118`

```python
return [float(re.sub(r'[^\d.]', '', x)) for x in re.findall(r'[\d.,-]+', data)]
```

The library exposes 16 regions (`consts.py:5-22`) but number parsing assumes US
formatting:

- German rating text `"4,5 von 5 Sternen"`: `"4,5"` → comma stripped → `45.0`.
`get_numerator()` (min) returns `5.0`, `get_denominator()` (max) returns `45.0`,
`get_perc()` returns `0.11` for a 4.5-star product.
- German count `"1.234"` → `float("1.234")` → `get_count()` returns `1` instead
of 1234.
- The `-` in the find pattern is stripped by the cleanup, so `"1-5"` becomes
`15.0`.

Additionally `get_numerator`/`get_denominator` rely on min/max of _all_ numbers
in the text rather than positional parsing, which silently misbehaves whenever
extra digits appear in the text.

**Impact:** Silently incorrect ratings/percentages/counts for most non-US
regions — worse than failing, because the values look plausible.

---

## High

### H1. Constructor argument hierarchy is inverted relative to documentation

**File:** `amzsear/core/AmzSear.py:44-84`

The docstring (lines 18-29) says higher-level args **override** lower ones
(`query` > `url` > `html` > `html_element` > `products`). The implementation is
a waterfall of independent `if x is not None` blocks, so a _lower_-level arg
always overwrites the result of a higher-level one: `AmzSear(query='laptop',
html=cached)` fetches the network results for `query`, then throws them away and
parses `html`. The network round-trip for `query`/`url` is still performed and
wasted.

**Impact:** Behavior contradicts documented API; wasted HTTP requests.

### H2. `capture_exception(IndexError, default={})` silently discards partially-valid products

**File:** `amzsear/core/AmzProduct.py:79-128`

`_get_from_html` performs many indexed lookups (`...cssselect('a')...[0]` line
89, `root.cssselect('img[src]')[0]` line 98). Any single `IndexError` — e.g. a
product card without an image — aborts the _entire_ parse and returns `{}`, so a
product with a perfectly good title/URL/price is dropped from results with no
trace. It also masks genuine bugs (any IndexError from helper code is swallowed
too).

**Impact:** Products silently missing from search results; selector regressions
are invisible.

### H3. Price detection regex has false positives and locale false negatives

**File:** `amzsear/core/AmzProduct.py:102-112`

```python
price_text = filter(lambda x: re.match(r'^[^a-z\-]+$', str(x.text)) and
    re.search(r'[.,]', str(x.text)) and re.search(r'\d', str(x.text)), price_text)
```

- **False positives:** any span text with no lowercase letters, containing a
digit and a `.`/`,` qualifies — e.g. dates like `"JUN 1, 2026"`, `"4,5"` rating
fragments, model numbers `"MK.2"` become "prices".
- **False negatives:** currencies without decimal separators fail the mandatory
`[.,]` check — `"￥1500"` (JP) or `"₹1500"` are dropped entirely.
- `price_names = root.cssselect('h3[data-attribute]')` matches pre-2019 Amazon
markup; on current result pages it is empty, so all prices get numeric string
keys (`'0'`, `'1'`, ...), making the documented "price type as key" API
meaningless.
- Positional zip of `price_names[i]` against the _filtered_ `price_text` stream
means even when names exist they can pair with the wrong price.

**Impact:** `prices` dict contains garbage entries and misses real prices by
region.

### H4. `get_prices` crashes or returns wrong values on European price formats

**File:** `amzsear/core/AmzProduct.py:198-200`

```python
prices += [re.sub(',', '', x) for x in re.findall(r'[\d.,]+', self.prices[k])]
return sorted(map(float, prices))
```

`"1.234,56 €"` (DE/ES/IT/FR/BR) → comma stripped → `"1.234.56"` → `float()`
raises `ValueError`. A lone `","` or `"."` also matches `[\d.,]+` and crashes
`float`. US-format `"1,234.56"` works; half the supported regions do not.

**Impact:** Uncaught `ValueError` from a public API method for most EU regions.

### H5. Star-distribution regex cannot match plural "stars"

**File:** `amzsear/core/AmzProductDetails.py:189`

```python
match = re.search(r'(\d)\s*star\s*(\d+)%', text)
```

After `star`, the pattern requires optional whitespace then a digit. Real
histogram row text reads `"5 stars 85%"` / `"5 star s represent 85%..."` — the
trailing `s` of "stars" prevents a match (regex cannot skip it). Only the
singular `"1 star 3%"` row can match. `star_distribution` will at best contain
the 1-star row, typically ends up `None`.

**Impact:** `star_distribution` feature effectively broken.

### H6. `fetch_details` errors are invisible and overwrite each other

**File:** `amzsear/core/AmzProduct.py:254-268`

- `FetchError` is caught and stashed in `self._fetch_error` — a private,
undocumented attribute not in `_all_attrs`, so it never appears in `repr`,
`to_dict`, `items()`. Callers have no documented way to distinguish "no reviews"
from "request failed / blocked by captcha".
- If BASIC fetch fails the method returns early and silently skips the requested
REVIEWS level; if REVIEWS later fails it overwrites any prior error string.
- `region=` mutates `self._region` permanently as a side effect of a fetch call
(line 242-243).

**Impact:** Network/anti-bot failures are indistinguishable from "product has no
data"; API misleads users into trusting `None` fields.

### H7. Shared mutable defaults in `requires_valid_data` decorators

**File:** `amzsear/core/AmzBase.py:97,109,119`,
`amzsear/core/AmzProduct.py:169`, `amzsear/core/__init__.py:15-25`

`@requires_valid_data(default=[])` captures **one** list at decoration time,
shared by every invalid instance of the class for the process lifetime. Any
caller doing `product.keys().append(...)` (or otherwise mutating the returned
list) on an invalid object corrupts the default returned to all future callers.
Likewise `default=iter(())` on `items()` (line 97) is a single shared iterator
object — it happens to be harmless only because an exhausted iterator stays
empty, but it is the same anti-pattern and returns the _identical_ object to
every caller.

**Impact:** Latent cross-instance state corruption; classic mutable-default bug.

### H8. `AmzBase.get` / `__contains__` treat known attributes with falsy parse results as unknown keys

**File:** `amzsear/core/AmzBase.py:46-52,74-95`

`__iter__` only yields attributes whose value `is not None`, and `get(...,
raise_error=True)` raises `KeyError("...is not a known attribute")` for any attr
that is currently `None` — even though it _is_ a known, declared attribute that
simply wasn't parsed. `product['rating']` therefore raises a misleading
`KeyError` instead of returning `None`, and `'rating' in product` is `False` for
a real attribute. Also note `get()` ignores `_is_valid` while
`keys()/values()/items()` honor it — an invalid object answers
`obj.get('title')` but returns `[]` for `obj.keys()`.

**Impact:** Confusing, inconsistent dict-like contract; misleading error
messages.

---

## Medium

### M1. Search URL format is legacy and selector set is dated

**File:** `amzsear/core/consts.py:30`, `amzsear/core/AmzProduct.py:89-122`,
`amzsear/core/AmzRating.py:60-61`

`SEARCH_URL` uses the pre-2018 `/s/ref=nb_sb_noss?sf=qz&keywords=...` form
(modern is `/s?k=`); it currently works via redirect but is one server change
from breaking. `h3[data-attribute]` (AmzProduct.py:102), exact-match
`div[class="a-row a-spacing-none"]` (line 92 — exact attribute equality, breaks
if Amazon adds any class), the `getparent().getparent()` DOM walk (line 92), and
`a[href*="customerReviews"]` (AmzRating.py:61) all target old markup
generations.

**Impact:** High scraping fragility; several fields already likely dead on
current pages.

### M2. `extra_attributes` pairing heuristic

**File:** `amzsear/core/AmzProduct.py:120-122`

```python
d['extra_attributes'] = dict(list(zip(extras, extras[1:]))[::2])
```

Assumes spans strictly alternate key/value. One non-paired span shifts the whole
mapping by one, turning values into keys. Odd counts silently drop the last
item. No validation that "keys" look like labels.

**Impact:** Garbage key/value pairs that look authoritative.

### M3. Product validity check is nearly always true

**File:** `amzsear/core/AmzProduct.py:74-77,125`

`_get_from_html` unconditionally sets `d['_index'] = None`, `d['prices'] = {}`,
`d['extra_attributes'] = {...}`, so the returned dict is non-empty in every code
path except the `IndexError` bail-out. The `if len(html_dict) > 0` validity gate
therefore only distinguishes "IndexError happened" from "anything else", not
"useful data was parsed". A card with no title/URL/price would still be marked
valid (it is only excluded from `AmzSear` because `_index` ends up `None`).

**Impact:** `is_valid()` does not mean what it claims.

### M4. `AmzReviews` total count selector is a product-page selector

**File:** `amzsear/core/AmzReviews.py:180,197-202`,
`amzsear/core/selectors.py:38`

`REVIEW_COUNT = '#acrCustomerReviewText'` exists on _product_ pages. The reviews
page (`/product-reviews/ASIN`) puts the count in
`[data-hook="cr-filter-info-review-rating-count"]`, so `total_count` is
effectively never populated from the page `AmzReviews` is designed to parse.
Additionally Amazon has required login for `/product-reviews/` since ~2023, so
the whole REVIEWS level likely receives a sign-in interstitial — there is no
detection of that case (a login page parses to zero reviews, indistinguishable
from "no reviews").

**Impact:** `total_count` dead; review fetching silently returns empty on
logged-out requests.

### M5. `data-a-dynamic-image` JSON blob appended as an image "URL"

**File:** `amzsear/core/AmzProductDetails.py:151`

```python
src = img.get('src') or img.get('data-old-hires') or img.get('data-a-dynamic-image')
```

`data-a-dynamic-image` contains a JSON dictionary
(`{"https://...jpg":[500,500],...}`), not a URL. When it's the fallback, the raw
JSON string lands in `image_urls`. Thumbnail `src` URLs are also low-resolution
variants (`_AC_US40_`); no upscaling or dedup of size variants of the same
image.

**Impact:** Malformed entries in `image_urls`.

### M6. Technical-details selectors merged across all tables without precedence

**File:** `amzsear/core/AmzProductDetails.py:122-134`

The loop runs all three selectors and merges every row into one dict.
`TECH_DETAILS_ROWS` (`#prodDetails table tr`) is a superset of the other
ID-based selectors on many pages, so rows are parsed twice; colliding keys from
different tables (e.g. "Customer Reviews" appears in both tech-spec and
additional-info tables) silently overwrite each other with last-wins ordering.

**Impact:** Duplicate work; nondeterministic-feeling key collisions.

### M7. Query string injected into URL path unescaped for `/`

**File:** `amzsear/core/__init__.py:46`

`parse.quote(query)` defaults to `safe='/'`, so a query containing `/` (or an
attacker-influenced query string like `foo/../../gp/...`) alters the URL _path_
rather than being encoded as a literal keyword. `page_num` is interpolated with
`%s` and never validated — a string page like `"1&foo=bar"` injects query
parameters. Not exploitable beyond Amazon's own domain (host is fixed by
`build_base_url`), but it breaks searches containing slashes and allows
parameter smuggling.

**Impact:** Broken searches for legitimate queries containing `/`; URL parameter
injection from untrusted query/page inputs (relevant for the MCP server
wrapper).

### M8. `AmzSear(url=...)` fetches arbitrary user-supplied URLs (SSRF-shaped surface)

**File:** `amzsear/core/AmzSear.py:58-65`, `amzsear/core/__init__.py:41-58`

`build_url` only prefixes the Amazon base when the URL starts with `/`; any
absolute URL is fetched verbatim by `fetch_html` with redirects followed. Fine
for a local CLI, but the core API is also exposed through the MCP server — if a
calling layer passes through a model/user-controlled `url`, this becomes an SSRF
primitive (internal hosts, link-local metadata endpoints). There is no scheme or
host allowlist.

**Impact:** Depends on embedding context; worth a host check (`*.amazon.<tld>`)
in `fetch_html` or `build_url`.

### M9. `aget` `raise_error`/`default` are dead for all declared attributes

**File:** `amzsear/core/AmzSear.py:162-190`

Every `AmzProduct` attribute exists as a _class_ attribute defaulting to `None`
(AmzProduct.py:50-61), so `hasattr(prod, k)` is `True` for every declared name
on every product. `raise_error=True` can only fire for a typo'd key, and
`default` is never substituted for missing data — callers get `None` instead of
their default. Also the return shape (`list of tuples` even for a single key) is
awkward: `aget('title')` returns `[('A',), ('B',)]` rather than `['A', 'B']`.

**Impact:** Documented parameters don't do what they say.

### M10. `AmzSear.__repr__` truncates the index separator

**File:** `amzsear/core/AmzSear.py:88-92`

`repr(index)` of a 10-char ASIN is 12 chars (with quotes); `+ ':'` makes 13; the
slice `temp_repr[:max_index_len]` with `max_index_len = 12` cuts off the colon
and the closing quote, producing output like `'B0ABCDEFGHTitle...`. The comment
"ASIN is 10 chars + padding" miscounts the quotes added by `repr`.

**Impact:** Cosmetic but always-wrong output formatting.

### M11. `helpful_count`/`verified` conflate "absent" with real values; regex misses "person"

**File:** `amzsear/core/AmzReviews.py:112-127`

`helpful_count` defaults to `0` when the element is missing or the text is in a
non-English locale, conflating "nobody found this helpful" with "couldn't
parse". The regex `r'([\d,]+)\s*people?\s*found'` only matches "people"/"peopl"
— the `'One person'` special case catches English singular, but localized
strings all collapse to 0. `verified` is set to `False` when the badge is
absent, which is also the value when parsing fails. Other fields use `None` for
"unknown" — inconsistent.

**Impact:** Silently wrong zero/False values for non-English pages.

### M12. No HTTP session reuse, retries, or inter-request delay

**File:** `amzsear/core/__init__.py:88-93`,
`amzsear/core/AmzProduct.py:252-268`, `amzsear/core/AmzSear.py:62-65`

Every `fetch_html` call is a cold `requests.get` — new TCP+TLS handshake per
page. Multi-page searches and `fetch_details(level=REVIEWS)` (2 sequential
requests) get no connection pooling, no retry/backoff, no jitter. The static,
ancient-ish Firefox 128 UA (`consts.py:40`) combined with rapid sequential hits
is the classic captcha trigger profile.

**Impact:** Performance and a materially higher block rate.

---

## Low

### L1. Dual `try: absolute / except ImportError: relative` import pattern everywhere

**Files:** every module (`AmzBase.py:1-6`, `AmzProduct.py:3-18`,
`AmzSear.py:3-10`, `AmzReviews.py:7-10,60-71,179-182`,
`AmzProductDetails.py:6-9,70-89`, `core/__init__.py:7-12`,
`amzsear/__init__.py:5-16`)

The package always installs as `amzsear`, so the relative fallback is dead in
practice; worse, the pattern can produce two distinct module objects (different
`isinstance` identities for `FetchError`/`AmzBase`) if both paths are ever
importable. In `AmzReviews._parse_from_html` and
`AmzProductDetails._parse_from_html` the imports are additionally re-executed
_inside the method on every parse call_.

**Impact:** Noise, minor per-call overhead, latent identity bugs.

### L2. `to_dict(flatten=True)` silently ignores documented `recursive` requirement and can drop keys

**File:** `amzsear/core/AmzBase.py:138-166`

The docstring says flatten "Requires recursive=True" but nothing enforces it
(`flatten=True, recursive=False` silently behaves as non-flatten). When
flattening, `{**d, **v.to_dict()}` lets a nested object's keys (e.g.
`AmzReview.title`, `AmzProductDetails.review_count`) silently overwrite
same-named parent keys (`AmzProduct.title`).

**Impact:** Silent data loss in flattened exports /
`to_dataframe(flatten=True)`.

### L3. `AmzBase.__repr__` pads using longest _declared_ attr, not longest present attr

**File:** `amzsear/core/AmzBase.py:58-60`

`max(self._all_attrs, ...)` measures all declared names even when only
short-named attrs are set; with zero set attrs but `len(self) > 0` impossible,
fine — but `%`-style width formatting via `'{:%d} {}' % max_k` is fragile and `%
(max_k)` is a 1-tuple-without-comma accident waiting to happen (works only
because it's an int).

**Impact:** Cosmetic / maintainability.

### L4. `AmzBase.__contains__` and `__len__` are O(n) list-builds

**File:** `amzsear/core/AmzBase.py:40-47`; `amzsear/core/AmzSear.py:129-136`

`it in list(self)` materializes a list per membership check. Similarly
`AmzSear.get` does `key not in self._indexes` then `self._indexes.index(key)` —
two O(n) scans per lookup where a dict `{asin: product}` is the natural
structure.

**Impact:** Minor performance; only matters for large result sets.

### L5. `get_star_repr` uses banker's rounding

**File:** `amzsear/core/AmzRating.py:142`

`round(4.5)` is `4` in Python 3, so a 4.5-star product renders four stars while
a 3.5-star product renders four as well (`round(3.5)` is `4`). Inconsistent
visual rounding.

**Impact:** Cosmetic.

### L6. Brand cleanup mangles brands containing "Store"

**File:** `amzsear/core/AmzProductDetails.py:101-104`

`.replace(' Store', '')` removes the substring anywhere, so "Visit the Container
Store Store" → "Visit the Container" is wrong-ish; also `replace('Visit the ',
'')` operates anywhere in the string, not just the prefix despite the
`startswith` guard. Locale variants ("Besuche den X-Store") are unhandled.

**Impact:** Occasionally mangled brand names.

### L7. `get_asin` misses `/gp/product/` URLs

**File:** `amzsear/core/AmzProduct.py:211`

The regex only accepts `/dp/` (plain or `%2F`-encoded). Amazon also emits
`/gp/product/ASIN` links and `/dp/product/` variants; products linked that way
get `_index = None` and are silently excluded by `AmzSear.__init__` (line 79).

**Impact:** Occasional silent product drops.

### L8. `QA_URL`, `QUERY_BUILD_DICT`, `DetailLevel.FULL`, and Q&A selectors are dead code

**File:** `amzsear/core/consts.py:28,35`, `amzsear/core/selectors.py:16,56-58`,
`amzsear/core/AmzProduct.py:270-273`

`DetailLevel.FULL` is publicly exported and documented in `fetch_details` but
its implementation is commented out; `QA_*` selectors and `QA_URL` are unused;
`QUERY_BUILD_DICT` is an empty dict whose only effect is a no-op `update`. The
generic Q&A selectors (`.a-fixed-left-grid`, `.a-spacing-base`,
`.a-declarative`) would match half the page anyway.

**Impact:** API promises a level that does nothing extra; dead constants.

### L9. `lxml_html_clean` is a declared dependency but never imported by core

**File:** `pyproject.toml` vs `amzsear/core/*`

No core module uses html cleaning. Either it's needed by lxml's `html` import
chain in newer versions (defensive pin) or it's a stale dependency; worth a
comment either way.

**Impact:** Dependency hygiene.

### L10. Scraped text is propagated unsanitized (terminal escape injection)

**File:** `amzsear/core/AmzProduct.py:90`, `amzsear/core/AmzBase.py:54-72`

`text_content()` output (titles, subtext, review bodies) flows into `__repr__`
and the CLI without stripping control characters. A malicious listing title
containing ANSI escape sequences would be emitted raw to the user's terminal.
Newlines are handled; `\x1b` etc. are not.

**Impact:** Low-probability but real terminal-injection vector for a scraper.

---

## Suggestions

### S1. Replace parallel lists with a dict in `AmzSear`

`_products`/`_indexes` parallel lists (`AmzSear.py:51-53`) with `.index()`
lookups should be an insertion-ordered `dict[str, AmzProduct]`; simplifies
`get`, `items`, dedup, and `__contains__`.

### S2. Move network I/O out of constructors

`AmzSear.__init__` performing HTTP fetches makes the object impossible to
construct lazily, hard to test, and forces exception handling around a
constructor. A `AmzSear.from_query(...)` / `.from_html(...)` classmethod family
would keep the documented hierarchy honest (fixes H1 structurally).

### S3. Centralize and version the selectors

`selectors.py` covers detail/review pages but `AmzProduct`/`AmzRating` hard-code
their own search-card selectors inline (`AmzProduct.py:89-120`,
`AmzRating.py:60-61`). Moving all selectors into `selectors.py` makes markup
churn a one-file fix and makes the dated ones (M1) visible.

### S4. Add a locale-aware number parser

One helper that handles `1,234.56` / `1.234,56` / `1 234,56` / no-decimal
currencies, used by `AmzRating`, `get_prices`, review counts. Fixes C3/H4 family
at the root.

### S5. Use a `requests.Session` with retry/backoff in `fetch_html`

Session reuse + `urllib3.Retry` (and an optional politeness delay) addresses M12
and reduces captcha rate; also makes the 30s timeout (`core/__init__.py:89`)
configurable.

### S6. Detect anti-bot/login interstitials in `fetch_html`

Check for captcha markers (`form[action="/errors/validateCaptcha"]`) and sign-in
redirects, raising a distinct `FetchError` subclass so "blocked" is
distinguishable from "empty page" (addresses the silent-empty failure modes in
C2/M4/H6).

### S7. Make fetch errors first-class

Replace `_fetch_error` with a public `fetch_error` attribute (or raise by
default, with `errors='ignore'` opt-in), and collect per-page errors in
`AmzSear` instead of aborting.

### S8. Narrow `capture_exception` scope

Wrap only the truly optional lookups in try/except (or use `cssselect(...)[:1]`
patterns) so one missing sub-element doesn't void a whole product (H2), and let
unexpected exceptions surface.

---

_Audit performed read-only; no source files were modified._
