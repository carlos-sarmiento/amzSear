"""
AmzReview and AmzReviews classes for storing customer review data
fetched from Amazon product review pages.
"""
import re

from .AmzBase import AmzBase
from .utils import clean_text, extract_numbers, parse_int


class AmzReview(AmzBase):
    """
    Represents a single customer review.

    Attributes:
        reviewer (str): Reviewer's display name
        rating (float): Star rating (1-5)
        title (str): Review title
        date (str): Review date
        text (str): Full review text
        verified (bool): Whether this is a verified purchase
        helpful_count (int): Number of people who found this helpful
        images (list): URLs to images attached to review
    """

    reviewer = None
    rating = None
    title = None
    date = None
    text = None
    verified = None
    helpful_count = None
    images = None

    _all_attrs = [
        'reviewer', 'rating', 'title', 'date',
        'text', 'verified', 'helpful_count', 'images'
    ]

    def __init__(self, html_element=None):
        """
        Initialize AmzReview.

        Args:
            html_element: lxml HTML element for a single review (optional)
        """
        super().__init__()
        if html_element is not None:
            self._parse_from_html(html_element)

    def _parse_from_html(self, elem):
        """
        Parse review data from HTML element.

        Args:
            elem: lxml HTML element for a single review
        """
        from .selectors import (
            REVIEW_AUTHOR,
            REVIEW_BODY,
            REVIEW_DATE,
            REVIEW_HELPFUL,
            REVIEW_IMAGES,
            REVIEW_RATING,
            REVIEW_TITLE,
            REVIEW_VERIFIED,
        )

        # Reviewer name
        author_elem = elem.cssselect(REVIEW_AUTHOR)
        if author_elem:
            self.reviewer = clean_text(author_elem[0].text_content())

        # Rating
        rating_elem = elem.cssselect(REVIEW_RATING)
        if rating_elem:
            rating_text = rating_elem[0].text_content()
            values = extract_numbers(rating_text)
            if len(values) >= 2 and int(values[-1]) == 5:
                self.rating = values[0]

        # Title
        title_elem = elem.cssselect(REVIEW_TITLE)
        if title_elem:
            # Title often includes rating text, extract just the title
            title_text = clean_text(title_elem[0].text_content())
            # Remove rating prefix like "5.0 out of 5 stars"
            title_text = re.sub(r'^\d+[.,]?\d*\s*\S*\s*5\s*\S*\s*', '', title_text)
            self.title = clean_text(title_text)

        # Date
        date_elem = elem.cssselect(REVIEW_DATE)
        if date_elem:
            date_text = clean_text(date_elem[0].text_content())
            # Extract date from text like "Reviewed in the United States on December 3, 2024"
            match = re.search(r'on\s+(.+)$', date_text)
            if match:
                self.date = match.group(1).strip()
            else:
                self.date = date_text

        # Review text
        body_elem = elem.cssselect(REVIEW_BODY)
        if body_elem:
            self.text = clean_text(body_elem[0].text_content())

        # Verified purchase
        verified_elem = elem.cssselect(REVIEW_VERIFIED)
        self.verified = True if verified_elem else None

        # Helpful count
        helpful_elem = elem.cssselect(REVIEW_HELPFUL)
        if helpful_elem:
            helpful_text = clean_text(helpful_elem[0].text_content())
            parsed = parse_int(helpful_text)
            if parsed is not None:
                self.helpful_count = parsed
            elif re.search(r'\bone\b', helpful_text, flags=re.IGNORECASE):
                self.helpful_count = 1

        # Review images
        img_elems = elem.cssselect(REVIEW_IMAGES)
        if img_elems:
            self.images = []
            for img in img_elems:
                src = img.get('src')
                if src:
                    self.images.append(src)
            if not self.images:
                self.images = None

        # Mark as valid if we have at least text or title
        if self.text or self.title:
            self._is_valid = True


class AmzReviews(AmzBase):
    """
    Collection of customer reviews for a product.

    Attributes:
        reviews (list): List of AmzReview objects
        total_count (int): Total number of reviews
        feature_ratings (dict): Feature-specific ratings (e.g., {"Sound quality": 4.5})
    """

    reviews = None
    total_count = None
    feature_ratings = None
    fetch_error = None

    _all_attrs = ['reviews', 'total_count', 'feature_ratings', 'fetch_error']

    def __init__(self, html_element=None):
        """
        Initialize AmzReviews.

        Args:
            html_element: lxml HTML element from reviews page (optional)
        """
        super().__init__()
        if html_element is not None:
            self._parse_from_html(html_element)

    def _parse_from_html(self, root):
        """
        Parse reviews from HTML element.

        Args:
            root: lxml HTML root element from reviews page
        """
        from .selectors import REVIEW_COUNT, REVIEW_ITEM, REVIEWS_TOTAL_COUNT

        page_text = clean_text(root.text_content()).lower()
        if '/ap/signin' in page_text or ('sign in' in page_text and 'customer reviews' in page_text):
            self.fetch_error = 'Amazon returned a sign-in page instead of reviews'
            self._is_valid = True
            return

        # Parse individual reviews
        review_elems = root.cssselect(REVIEW_ITEM)
        if review_elems:
            self.reviews = []
            for elem in review_elems:
                review = AmzReview(elem)
                if review.is_valid():
                    self.reviews.append(review)

        if not self.reviews:
            self.reviews = []

        # Total count
        count_elem = root.cssselect(REVIEWS_TOTAL_COUNT) or root.cssselect(REVIEW_COUNT)
        if count_elem:
            self.total_count = parse_int(count_elem[0].text_content())

        # Feature ratings (these are often in a separate widget)
        # Look for feature rating buttons
        feature_buttons = root.cssselect('[data-hook="cr-insights-widget-aspects"] button')
        if feature_buttons:
            self.feature_ratings = {}
            for btn in feature_buttons:
                text = clean_text(btn.text_content())
                # Extract feature and count, e.g., "Sound quality (2K)"
                match = re.match(r'([^(]+)\s*\(([^)]+)\)', text)
                if match:
                    feature = match.group(1).strip()
                    count = match.group(2).strip()
                    self.feature_ratings[feature] = count

        if not self.feature_ratings:
            self.feature_ratings = None

        # Mark as valid if we parsed review data.
        if self.reviews or self.total_count is not None or self.feature_ratings:
            self._is_valid = True

    def __len__(self):
        """Return number of reviews."""
        return len(self.reviews) if self.reviews else 0

    def __iter__(self):
        """Iterate over reviews."""
        return iter(self.reviews) if self.reviews else iter([])
