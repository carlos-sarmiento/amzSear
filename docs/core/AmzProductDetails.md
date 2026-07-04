## Class Definition

<a name="AmzProductDetails"></a>

### AmzProductDetails(_html_element=None_)

`AmzProductDetails` stores information parsed from an Amazon product page.

Attributes:

- _full_title_ (str): Full product title.
- _brand_ (str): Brand or store name.
- _brand_url_ (str): Brand/store URL when present.
- _about_items_ (list): "About this item" bullets.
- _technical_details_ (dict): Technical/specification table values.
- _product_description_ (str): Product description text.
- _image_urls_ (list): Product image URLs.
- _reviews_summary_ (str): Reviews summary text when present.
- _star_distribution_ (dict): Rating distribution by star value.
- _review_count_ (int): Total review/rating count.
- _average_rating_ (float): Average star rating.

The parser accepts localized numeric formats such as `4,5 out of 5 stars` and
`1.234 ratings`.

## Usage

```python
from amzsear import AmzProduct, DetailLevel

product = AmzProduct.from_asin("B00006IFHD")
product.fetch_details(level=DetailLevel.BASIC)
details = product.details
```
