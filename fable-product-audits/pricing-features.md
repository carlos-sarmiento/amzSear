# Product Feature Audit: Pricing

**Project:** amzSear — personal tool to load Amazon product info for AI-assisted
product choice **Area:** Pricing features **Date:** 2026-06-10

## Summary

Pricing is the weakest of the user's three priorities (availability, pricing,
reviews). Search results yield a raw, unlabeled dict of price strings; the
product-detail page — the page with the richest pricing data (deal price, list
price, coupons, unit price, used offers, shipping) — extracts **no price at
all**. There is no price normalization in JSON output, no deal/list distinction,
no comparison/sorting support, and the only numeric parser silently corrupts
comma-decimal prices for 10 of the 16 supported regions. For the "help me choose
a good product" use case, the AI consuming the MCP output gets raw strings like
`{"0": "$29.99"}` and must guess what each price means.

## Current Capabilities

| Capability                | Where                                               | Notes                                                                                                          |
| ------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Search-card price strings | `AmzProduct._get_from_html` (AmzProduct.py:101-112) | Regex-filters `span[class^="a"]` text; stores raw strings in `prices` dict                                     |
| Price-type keys           | `h3[data-attribute]` selector                       | Selector is stale for modern Amazon markup, so keys are almost always numeric `"0"`, `"1"`, … — type info lost |
| Float conversion (opt-in) | `AmzProduct.get_prices()` (AmzProduct.py:170-200)   | Returns sorted floats; strips commas; **not** used in any JSON/MCP output                                      |
| Price range in CLI table  | `cli.py print_short` (cli.py:180-188)               | Shows min–max string range; display only                                                                       |
| Raw prices in JSON        | `cli.py print_json`, MCP `product_to_dict`          | Passes the raw `prices` dict through verbatim                                                                  |
| 16 regions                | `consts.py REGION_CODES`                            | URL building only — no currency awareness anywhere                                                             |

## Gaps / Weaknesses

### Extraction gaps

1. **Product detail page extracts zero pricing.** `AmzProductDetails`
   (AmzProductDetails.py) has no price field at all, and `selectors.py` has no
   price selectors (`#corePrice_feature_div`, `.a-price`, `#priceblock_*`,
   etc.). The ASIN lookup path (`amzsear --asin`, MCP `get_product`) therefore
   returns title/brand/rating **but no price** — a core question ("how much is
   it?") is unanswerable from the richest data source.
2. **No list price vs deal price distinction.** Amazon search cards show
   strikethrough list prices (`.a-text-price`); these may be captured as an
   extra anonymous dict entry or missed, but are never labeled. Deal detection
   (discount %) is impossible.
3. **No coupon extraction.** "Save 10% with coupon" badges on search cards are
   ignored, though they materially change effective price.
4. **No unit price.** Amazon's "$0.25/count" secondary price is not captured —
   important for comparing consumables.
5. **No shipping/delivery cost or Prime pricing.** "FREE delivery" is only used
   as an availability heuristic (AmzProduct.py:159), never surfaced as a
   shipping-cost signal.
6. **No used/refurbished offer prices.** "More buying choices: $12.50 (3 used &
   new offers)" is not extracted.
7. **Per-format price clarity lost.** Books/media show Kindle/Paperback/Audible
   prices; with the stale `h3[data-attribute]` key selector these collapse into
   anonymous numeric keys, so the AI can't tell which price belongs to which
   format.

### Parsing robustness

8. **Comma-decimal corruption.** `get_prices()` does `re.sub(',', '', x)` then
   `float()`: `"29,99 €"` → `2999.0`. Wrong by 100× for DE, FR, ES, IT, NL, BR,
   and others — 10 of 16 supported regions. Any future price math built on this
   is unsafe outside US/UK/JP.
9. **No currency capture.** The currency symbol/code is never parsed or stored;
   JSON output gives raw strings only, leaving currency inference to the AI
   consumer.
10. **Fragile price-span filter.** The regex filter on `span[class^="a"]` text
    (AmzProduct.py:104-105) can match non-price numerics (e.g., "1,234" counts
    with commas) and depends on Amazon rendering whole prices in a single span;
    no test coverage exists for pricing extraction (zero price assertions in
    `tests/`).

### Missing product features for the AI-choice use case

11. **No normalized numeric price in JSON/MCP output.** The AI gets
    `"prices": {"0": "$29.99"}`. A `price_min`/`price_max`/`currency` float
    triple would make comparison trivial and reliable.
12. **No sorting/filtering by price.** Neither CLI nor MCP supports "show
    results under $50" or price-sorted output; the AI must request everything
    and post-process strings.
13. **No cross-result price comparison aid.** Nothing computes cheapest/median
    across a result set, even though `AmzSear` holds all products.
14. **No price history/tracking across runs.** As a personal tool used
    repeatedly, persisting `(asin, date, price)` locally would enable "is this a
    good price?" — currently every run is amnesiac.
15. **No deal detection.** With list-vs-deal capture (gap 2) a simple
    `discount_percent` field would directly serve "choose a good product."

## Prioritized Recommendations

1. **Extract pricing on the product detail page** (`AmzProductDetails` +
   selectors for `#corePrice_feature_div .a-offscreen`, list price, unit price,
   coupon badge). _Rationale: highest-value fix — the ASIN/detail path currently
   answers everything except the price; pricing is a stated top priority._
2. **Add normalized price fields to JSON/MCP output**: `price_value` (float),
   `currency` (ISO code from region/symbol), `price_min`/`price_max` for ranges.
   _Rationale: the whole point is AI consumption; floats + currency remove
   guesswork and string-parsing errors from every downstream conversation._
3. **Fix locale-aware numeric parsing** in `get_prices()` (detect comma-decimal
   by region or pattern). _Rationale: silent 100× errors in 10 regions poison
   any price-based reasoning._
4. **Label price types**: update the price-key selector for modern search markup
   so Kindle/Paperback/deal/list prices keep meaningful keys; capture
   strikethrough list price as `list_price` and emit `discount_percent`.
   _Rationale: deal detection is a direct "good product" signal; format clarity
   prevents the AI comparing a Kindle price against another product's hardcover
   price._
5. **Capture coupons, unit price, and "more buying choices" (used/new from $X)**
   on search cards. _Rationale: effective price ≠ sticker price; unit price is
   essential for consumables comparison._
6. **Add price filter/sort options** to MCP `search_products` (e.g.,
   `max_price`, `sort="price"`). _Rationale: cuts token waste and lets the AI
   ask targeted questions._
7. **Optional lightweight price history**: append `(asin, timestamp, price)` to
   a local JSONL/SQLite file on each fetch, plus an MCP
   `get_price_history(asin)` tool. _Rationale: "is $39 a good price for this?"
   is the user's exact use case; even a few weeks of personal history beats
   none. Keep it local and simple — no enterprisey infra._
8. **Add pricing extraction tests** with HTML fixtures (US + one comma-decimal
   region). _Rationale: pricing currently has zero test coverage; selector drift
   would break the user's top-priority data silently._
