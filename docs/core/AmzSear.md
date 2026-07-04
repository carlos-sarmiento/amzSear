## Class Definition

<a name="AmzSear"></a>

### AmzSear(_query=None, page=1, region='US', url=None, html=None, html_element=None, products=None_)

`AmzSear` is a collection of [AmzProduct](AmzProduct.md) objects keyed by ASIN.
Use `get()` or `[]` for ASIN lookup, and use `rget()` for 0-based positional
lookup.

#### Constructor

The simplest constructor form performs an Amazon search:

```python
from amzsear import AmzSear

amz = AmzSear("Harry Potter", page=1, region="US")
```

Constructor inputs follow this precedence. Higher entries override lower ones:

```text
(query, [page], [region])
           |
         (url)
           |
         (html)
           |
     (html_element)
           |
       (products)
```

`page`, `url`, `html`, `html_element`, and `products` may be single values or
iterables. Multi-page fetches keep products from successful pages and record
failed page fetches in `fetch_errors`.

##### Optional Args

_query_ (str): A search query to look up on Amazon. _page_ (int or iterable):
Positive page number(s) to search. _region_ (str): Amazon region/country code.
_url_ (str or iterable): Amazon search URL(s). Absolute URLs must be Amazon
URLs. _html_ (str or iterable): Raw Amazon search HTML. _html_element_ (lxml
element or iterable): Parsed Amazon search HTML roots. _products_ (list):
Existing `AmzProduct` objects.

## Class Methods

<a name="get"></a>

### get(_key, default=None, raise_error=False_)

Gets a product by ASIN.

```python
amz = AmzSear("Harry Potter")
product = amz.get("B00728DYLA", raise_error=True)
same_product = amz["B00728DYLA"]
```

#### Args

_key_ (str): ASIN of the product.

##### Optional Args

_default_: Returned when the ASIN is unavailable and `raise_error=False`.
_raise_error_ (bool): Raise `KeyError` when the ASIN is unavailable.

<a name="rget"></a>

### rget(_key, default=None, raise_error=False_)

Gets a product by 0-based result position.

```python
first_product = amz.rget(0)
last_product = amz.rget(-1)
```

#### Args

_key_ (int): Relative result position.

<a name="aget"></a>

### aget(_key, default=None, raise_error=False_)

Gets one or more attributes from every product in product order.

```python
titles = amz.aget("title")
titles_and_urls = amz.aget(["title", "product_url"])
```

Single-key calls return a flat list. Multi-key calls return one tuple per
product.

<a name="items"></a>

### items()

Returns an iterator of `(asin, product)` tuples.

<a name="indexes"></a>

### indexes()

Returns all ASIN keys in result order. `keys()` is an alias.

<a name="products"></a>

### products()

Returns all products in result order. `values()` is an alias.

<a name="to_dataframe"></a>

### to_dataframe(_recursive=True, flatten=False_)

Converts products to a Pandas `DataFrame`. Pandas is optional and must be
installed separately.
