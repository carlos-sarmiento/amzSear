## Class Definition

<a name="AmzReview"></a>

### AmzReview(_html_element=None_)

`AmzReview` stores one customer review parsed from an Amazon reviews page.

Attributes:

- _reviewer_ (str): Reviewer display name.
- _rating_ (float): Star rating.
- _title_ (str): Review title.
- _date_ (str): Review date text.
- _text_ (str): Review body text.
- _verified_ (bool): `True` for verified-purchase reviews, or `None` when the
  signal is absent.
- _helpful_count_ (int): Helpful-vote count, or `None` when absent.
- _images_ (list): Review image URLs.

<a name="AmzReviews"></a>

### AmzReviews(_html_element=None_)

`AmzReviews` stores review-page data.

Attributes:

- _reviews_ (list): Parsed `AmzReview` objects.
- _total_count_ (int): Total review/rating count when present.
- _feature_ratings_ (dict): Feature-specific rating counts.
- _fetch_error_ (str): Parser-visible error such as a sign-in interstitial.

## Usage

```python
from amzsear import AmzProduct, DetailLevel

product = AmzProduct.from_asin("B00006IFHD")
product.fetch_details(level=DetailLevel.REVIEWS)
reviews = product.reviews
```
