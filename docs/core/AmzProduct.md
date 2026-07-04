## Class Definition

<a name="AmzProduct"></a>

### AmzProduct(_html_element=None, region='US'_)

`AmzProduct` extends [AmzBase](AmzBase.md#AmzBase) and represents one Amazon
search-result product.

Attributes:

- _title_ (str): Product title.
- _product_url_ (str): Canonical product page URL.
- _image_url_ (str): Main image URL when available.
- _rating_ ([AmzRating](AmzRating.md)): Rating object.
- _prices_ (dict): Price label to original price text.
- _availability_ (str): Best-effort availability phrase from search results.
- _is_available_ (bool): `True`, `False`, or `None` when unknown.
- _extra_attributes_ (dict): Additional card attributes.
- _subtext_ (list): Secondary text under the title.
- _details_ ([AmzProductDetails](AmzProductDetails.md)): Product page details
  populated by `fetch_details()`.
- _reviews_ ([AmzReviews](AmzReviews.md)): Review page data populated by
  `fetch_details(level=DetailLevel.REVIEWS)`.
- _fetch_error_ (str): Error text from failed detail/review fetches. The legacy
  `_fetch_error` alias is still populated for compatibility.

#### Constructors

```python
from amzsear import AmzProduct

product = AmzProduct(html_element)
product = AmzProduct.from_asin("B00006IFHD", region="US")
```

`from_asin()` creates a valid product shell for direct product-page fetches and
validates that the ASIN is exactly 10 alphanumeric characters.

## Class Methods

<a name="get_asin"></a>

### get_asin()

Extracts the ASIN from `product_url`. Both `/dp/ASIN` and `/gp/product/ASIN`
URLs are supported.

<a name="get_prices"></a>

### get_prices(_key=None_)

Gets price values as floats. The parser accepts US and European separator
styles, such as `$1,234.56` and `1.234,56 EUR`.

#### Optional Args

_key_ (str or list): Price key or keys from `prices`. If omitted, all prices
are parsed.

<a name="fetch_details"></a>

### fetch_details(_level=None, region=None_)

Fetches additional product data from Amazon and stores it on the product.

```python
from amzsear import DetailLevel

product.fetch_details(level=DetailLevel.BASIC)
product.fetch_details(level=DetailLevel.REVIEWS)
```

`DetailLevel.BASIC` fetches the product page and populates `details`.
`DetailLevel.REVIEWS` also fetches the reviews page and populates `reviews`.
Failures are stored in `fetch_error`.

<a name="base-methods"></a>

### Inherited Methods

`get()`, `items()`, `keys()`, `values()`, `is_valid()`, `to_dict()`, and
`to_series()` are inherited from [AmzBase](AmzBase.md).
