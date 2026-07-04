"""amzSear - The unofficial Amazon search CLI & Python API."""

__version__ = '3.0.1'

from .core.AmzProduct import AmzProduct
from .core.AmzProductDetails import AmzProductDetails
from .core.AmzRating import AmzRating
from .core.AmzReviews import AmzReview, AmzReviews
from .core.AmzSear import AmzSear
from .core.selectors import DetailLevel

__all__ = [
    '__version__',
    'AmzSear',
    'AmzProduct',
    'AmzProductDetails',
    'AmzRating',
    'AmzReviews',
    'AmzReview',
    'DetailLevel',
]
