"""
AmzProductDetails class for storing detailed product information
fetched from Amazon product pages.
"""

from .AmzBase import AmzBase
from .utils import clean_text, dynamic_image_urls, extract_numbers, parse_int


class AmzProductDetails(AmzBase):
    """
    Contains detailed product information fetched from an Amazon product page.

    All fields return None if not available (graceful defaults).

    Attributes:
        full_title (str): Complete product title
        brand (str): Brand/manufacturer name
        brand_url (str): URL to brand's Amazon store
        about_items (list): "About this item" bullet points
        technical_details (dict): Technical specifications table
        product_description (str): Product description text
        image_urls (list): URLs to all product images
        reviews_summary (str): AI-generated reviews summary (if available)
        star_distribution (dict): Rating distribution {5: percentage, 4: percentage, ...}
        review_count (int): Total number of reviews
        average_rating (float): Average star rating
    """

    full_title = None
    brand = None
    brand_url = None
    about_items = None
    technical_details = None
    product_description = None
    image_urls = None
    reviews_summary = None
    star_distribution = None
    review_count = None
    average_rating = None

    _all_attrs = [
        'full_title', 'brand', 'brand_url', 'about_items',
        'technical_details', 'product_description', 'image_urls',
        'reviews_summary', 'star_distribution', 'review_count', 'average_rating'
    ]

    def __init__(self, html_element=None):
        """
        Initialize AmzProductDetails.

        Args:
            html_element: lxml HTML element from product page (optional)
        """
        super().__init__()
        if html_element is not None:
            self._parse_from_html(html_element)

    def _parse_from_html(self, root):
        """
        Parse product details from HTML element.

        Args:
            root: lxml HTML root element
        """
        import re

        from .selectors import (
            BRAND_LINK,
            CUSTOMER_REVIEWS_SUMMARY,
            FEATURE_BULLETS,
            IMAGE_GALLERY,
            IMAGE_THUMB_LIST,
            MAIN_IMAGE,
            PRODUCT_DESCRIPTION,
            PRODUCT_DESCRIPTION_ALT,
            PRODUCT_DETAILS_TABLE,
            PRODUCT_DETAILS_TABLE_ALT,
            PRODUCT_TITLE,
            RATING_STARS,
            REVIEW_COUNT,
            STAR_HISTOGRAM,
            TECH_DETAILS_ROWS,
        )

        # Full title
        title_elem = root.cssselect(PRODUCT_TITLE)
        if title_elem:
            self.full_title = clean_text(title_elem[0].text_content())

        # Brand
        brand_elem = root.cssselect(BRAND_LINK)
        if brand_elem:
            self.brand = clean_text(brand_elem[0].text_content())
            store_match = re.match(r'^Visit the (.+) Store$', self.brand)
            brand_match = re.match(r'^Brand:\s*(.+)$', self.brand)
            if store_match:
                self.brand = store_match.group(1)
            elif brand_match:
                self.brand = brand_match.group(1)
            href = brand_elem[0].get('href')
            if href:
                self.brand_url = href

        # About this item bullet points
        bullet_elems = root.cssselect(FEATURE_BULLETS)
        if bullet_elems:
            self.about_items = []
            for elem in bullet_elems:
                text = clean_text(elem.text_content())
                if text and text not in ['About this item']:
                    self.about_items.append(text)

        # Technical details
        self.technical_details = {}

        # Try multiple selectors for tech details
        for selector in [TECH_DETAILS_ROWS, PRODUCT_DETAILS_TABLE, PRODUCT_DETAILS_TABLE_ALT]:
            rows = root.cssselect(selector)
            if rows:
                for row in rows:
                    cells = row.cssselect('th, td')
                    if len(cells) >= 2:
                        key = clean_text(cells[0].text_content())
                        value = clean_text(cells[1].text_content())
                        # Clean up common artifacts
                        key = re.sub(r'[\u200e\u200f]', '', key).strip()
                        value = re.sub(r'[\u200e\u200f]', '', value).strip()
                        if key and value and key not in self.technical_details:
                            self.technical_details[key] = value

        if not self.technical_details:
            self.technical_details = None

        # Product description
        desc_elem = root.cssselect(PRODUCT_DESCRIPTION)
        if not desc_elem:
            desc_elem = root.cssselect(PRODUCT_DESCRIPTION_ALT)
        if desc_elem:
            self.product_description = clean_text(desc_elem[0].text_content())

        # Image URLs
        self.image_urls = []
        for selector in [IMAGE_GALLERY, IMAGE_THUMB_LIST, MAIN_IMAGE]:
            img_elems = root.cssselect(selector)
            for img in img_elems:
                sources = []
                for attr in ('src', 'data-old-hires'):
                    if img.get(attr):
                        sources.append(img.get(attr))
                sources.extend(dynamic_image_urls(img.get('data-a-dynamic-image')))
                for src in sources:
                    # Skip tiny placeholder images
                    if src and src not in self.image_urls and 'sprite' not in src.lower() and 'transparent' not in src.lower():
                        self.image_urls.append(src)

        if not self.image_urls:
            self.image_urls = None

        # Reviews summary (AI-generated)
        summary_elem = root.cssselect(CUSTOMER_REVIEWS_SUMMARY)
        if summary_elem:
            self.reviews_summary = clean_text(summary_elem[0].text_content())

        # Review count
        count_elem = root.cssselect(REVIEW_COUNT)
        if count_elem:
            self.review_count = parse_int(count_elem[0].text_content())

        # Average rating
        rating_elem = root.cssselect(RATING_STARS)
        if rating_elem:
            rating_text = rating_elem[0].get('title', '') or rating_elem[0].text_content()
            values = extract_numbers(rating_text)
            if len(values) >= 2 and int(values[-1]) == 5:
                self.average_rating = values[0]

        # Star distribution
        histogram = root.cssselect(STAR_HISTOGRAM)
        if histogram:
            self.star_distribution = {}
            for row in histogram:
                text = row.text_content()
                # Match patterns like "5 star 85%" and "5 stars 85%"
                match = re.search(r'(\d)\s*stars?\s*(\d+)%', text, flags=re.IGNORECASE)
                if match:
                    stars = int(match.group(1))
                    percentage = int(match.group(2))
                    self.star_distribution[stars] = percentage

        if not self.star_distribution:
            self.star_distribution = None

        # Mark as valid if we got at least a title
        if self.full_title:
            self._is_valid = True
