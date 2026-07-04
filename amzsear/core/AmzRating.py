from . import capture_exception, requires_valid_data
from .AmzBase import AmzBase
from .utils import extract_numbers, round_half_up


class AmzRating(AmzBase):
    """
    The AmzRating class extends AmzBase and provides rating information.

    Attributes:
        ratings_text (str): The star rating (e.g. "4.5 out of 5 stars").
        ratings_count_text (str): The number of votes (e.g. "100").

    This class should usually not be instantiated directly (rather be used as
    part of an AmzProduct element) but can be created by passing an HTML element
    to the constructor. If nothing is passed, an empty AmzRating object is created.

    Args:
        html_element (lxml.html.HtmlElement): A root for an HTML tree derived from
            an element on an Amazon search page.
    """
    ratings_text = None
    ratings_count_text = None
    _all_attrs = ['ratings_text', 'ratings_count_text']

    def __init__(self, html_element=None):
        """
        Constructor takes an lxml Element and extracts (if possible)
        the first ratings text and ratings count text.
        """
        super().__init__()
        if html_element is not None:
            (ratings_text, ratings_count_text) = self._get_from_html(html_element)

            # Values are only set if there are 2 ratings_text floats (the text should
            #  be of the form "N out of N stars") and one ratings_count float (the text
            #  should be of the form "N").

            if (len(self._extract_all_values(ratings_text)) == 2 and 
              len(self._extract_all_values(ratings_count_text)) == 1):

                self.ratings_text = ratings_text
                self.ratings_count_text = ratings_count_text
                self._is_valid = True


    @capture_exception(IndexError, ('', ''))
    def _get_from_html(self, root):
        """
        Extract ratings text and count from the lxml element.

        Returns:
            tuple: Tuple of (ratings_text, ratings_count_text) as strings.
        """
        ratings_text = root.cssselect('i[class*="star"]')[0].text_content()
        ratings_count_text = root.cssselect(
            'a[href*="customerReviews"], a[href*="product-reviews"]'
        )[0].text_content()
        return (ratings_text, ratings_count_text)

    def _extract_all_values(self, data=None):
        """
        Extract any numbers from some text.

        Example: _extract_all_values("4.5 out of 5 stars") == [4.5, 5.0]

        Args:
            data (str): The string to extract from. If not provided,
                uses the ratings_text attribute.

        Returns:
            list: List of floats for any numbers in the text.
        """
        if data is None:
            data = self.ratings_text
        if not data:
            return []
        return extract_numbers(data)

    @requires_valid_data(default=0.0)
    def get_perc(self):
        """
        Get a percentage value of the rating.

        0% represents a 0/5 star rating and 100% represents a 5/5 star rating.

        Returns:
            float: The star percentage (0.0 to 1.0).
        """
        denominator = self.get_denominator()
        if denominator == 0:
            return 0.0
        return self.get_numerator() / denominator

    @requires_valid_data(default=0.0)
    def get_numerator(self):
        """
        Get the average star rating value (usually between 0 and 5).

        Returns:
            float: The numerator of the star rating.
        """
        values = self._extract_all_values()
        return sorted(values)[0] if values else 0.0

    @requires_valid_data(default=0.0)
    def get_denominator(self):
        """
        Get the maximum star rating value (usually 5).

        Returns:
            float: The denominator of the star rating.
        """
        values = self._extract_all_values()
        return sorted(values)[-1] if values else 0.0

    @requires_valid_data(default=0)
    def get_count(self):
        """
        Get the total number of ratings.

        Returns:
            int: The number of ratings.
        """
        values = self._extract_all_values(self.ratings_count_text)
        return int(values[0]) if values else 0

    @requires_valid_data(default='')
    def get_star_repr(self, star_repr='*'):
        """
        Get a visual representation of the star rating, rounding to the nearest star.

        Args:
            star_repr (str): A character used to represent a star (default: '*').

        Returns:
            str: A representation of the star rating (e.g., '****' for 4 stars).
        """
        return star_repr * round_half_up(self.get_numerator())
