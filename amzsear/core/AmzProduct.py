import re

from . import FetchError, build_base_url, build_url, fetch_html, requires_valid_data
from .AmzBase import AmzBase
from .AmzProductDetails import AmzProductDetails
from .AmzRating import AmzRating
from .AmzReviews import AmzReviews
from .consts import DEFAULT_REGION, PRODUCT_URL, REVIEWS_URL
from .selectors import DetailLevel
from .utils import (
    clean_text,
    extract_asin,
    is_asin,
    parse_price_values,
)


class AmzProduct(AmzBase):
    """
    The AmzProduct class extends AmzBase and represents a single Amazon product.

    Attributes:
        title (str): The name of the product.
        product_url (str): A url directly to the product's Amazon page.
        image_url (str): A url to the product's default image.
        rating (AmzRating): An AmzRating object.
        prices (dict): A dictionary of prices, with the price type as a key and
            a string for the price value (see get_prices method to get float values).
        availability (str): Best-effort availability text from the search result.
        is_available (bool): Best-effort stock status from the search result.
        extra_attributes (dict): Any extra information that can be extracted
            from the product.
        subtext (list): A list of strings under the title, typically the author's
            name and/or the date of publication.
        details (AmzProductDetails): Detailed product info (populated by fetch_details).
        reviews (AmzReviews): Product reviews (populated by fetch_details).

    This class should usually not be instantiated directly (rather be used in
    an AmzSear object) but can be created by passing an HTML element to
    the constructor. If nothing is passed, an empty AmzProduct object is created.

    Args:
        html_element (lxml.html.HtmlElement): A root for an HTML tree derived from
            an element on an Amazon search page.
        region (str): Amazon region code (default: 'US').
    """
    title = None
    product_url = None
    image_url = None
    rating = None
    prices = None
    availability = None
    is_available = None
    extra_attributes = None
    subtext = None
    details = None  # AmzProductDetails object (populated by fetch_details)
    reviews = None  # AmzReviews object (populated by fetch_details)
    fetch_error = None  # Error message if fetch_details failed
    _fetch_error = None  # Backward-compatible alias for fetch_error

    _all_attrs = ['title','product_url','image_url','rating','prices',
        'availability', 'is_available',
        'extra_attributes', 'subtext', 'details', 'reviews', 'fetch_error']

    @classmethod
    def from_asin(cls, asin, region=DEFAULT_REGION):
        """Create a valid product shell for a known ASIN."""
        raw_asin = asin
        asin = extract_asin(asin)
        if not asin:
            raise ValueError(f'{raw_asin!r} is not a valid ASIN')
        product = cls()
        product._region = region
        product.product_url = PRODUCT_URL % (build_base_url(region), asin)
        product._index = asin
        product._is_valid = True
        return product

    def __init__(self, html_element=None, region=DEFAULT_REGION):
        super().__init__()
        self._region = region
        if html_element is not None:
            html_dict = self._get_from_html(html_element)
            for k, v in html_dict.items():
                setattr(self, k, v)
            if self.title and self.get_asin():
                self._is_valid = True
                # Set _index to ASIN for use as key in AmzSear collection
                self._index = self.get_asin()

    def _get_from_html(self, root):
        """
        Parse product data from HTML element.

        Returns:
            dict: A dict of fields with extracted data.
        """
        d = {}

        title_elem = self._first(root.cssselect('h2'))
        title_link = self._title_link(root, title_elem)
        if title_elem is not None:
            d['title'] = clean_text(title_elem.text_content())

        asin = root.get('data-asin')
        if asin and is_asin(asin):
            d['_index'] = asin.upper()

        if title_link is not None and title_link.get('href'):
            try:
                d['product_url'] = build_url(title_link.get('href'), region=self._region)
            except ValueError:
                pass
        if 'product_url' not in d and d.get('_index'):
            d['product_url'] = PRODUCT_URL % (build_base_url(self._region), d['_index'])

        if 'product_url' in d and '_index' not in d:
            asin = extract_asin(d['product_url'])
            if asin:
                d['_index'] = asin

        d['subtext'] = self._parse_subtext(root)
        if not d['subtext']:
            d.pop('subtext')

        image_url = self._parse_image_url(root)
        if image_url:
            d['image_url'] = image_url

        rating = AmzRating(root)
        if rating:
            d['rating'] = rating

        d['prices'] = self._parse_prices(root)

        availability, is_available = self._get_availability_from_html(root, d['prices'])
        if availability is not None:
            d['availability'] = availability
        if is_available is not None:
            d['is_available'] = is_available

        d['extra_attributes'] = self._parse_extra_attributes(root)

        # clean up before returning
        return dict(map(lambda k: (k, clean_text(d[k]) if isinstance(d[k],str) else d[k]), d))

    def _first(self, values):
        return values[0] if values else None

    def _title_link(self, root, title_elem):
        if title_elem is not None:
            elem = title_elem
            while elem is not None:
                if elem.tag == 'a' and elem.get('href'):
                    return elem
                elem = elem.getparent()
            child_links = title_elem.cssselect('a[href]')
            if child_links:
                return child_links[0]

        product_links = [
            link for link in root.cssselect('a[href]')
            if extract_asin(link.get('href'))
        ]
        return self._first(product_links)

    def _parse_subtext(self, root):
        subtext = []
        title_elem = self._first(root.cssselect('h2'))
        title_text = clean_text(title_elem.text_content()) if title_elem is not None else ''
        for elem in root.cssselect('.a-row.a-size-base.a-color-secondary, .a-row.a-size-base, .a-row.a-spacing-none'):
            text = clean_text(elem.text_content())
            if text and text != title_text:
                subtext.append(text)
        return list(dict.fromkeys(subtext))

    def _parse_image_url(self, root):
        for img in root.cssselect('img[src], img[data-src], img[data-old-hires]'):
            src = img.get('src') or img.get('data-src') or img.get('data-old-hires')
            if src and 'sprite' not in src.lower() and 'transparent' not in src.lower():
                return src
        return None

    def _parse_prices(self, root):
        prices = {}
        price_names = [clean_text(elem.text_content()) for elem in root.cssselect('h3[data-attribute]')]
        candidates = []
        selectors = [
            '.a-price .a-offscreen',
            '.a-price-whole',
            '.a-color-price',
            '[aria-label*="$"]',
            '[aria-label*="€"]',
            '[aria-label*="£"]',
            '[aria-label*="¥"]',
            '[aria-label*="₹"]',
        ]
        for selector in selectors:
            for elem in root.cssselect(selector):
                text = clean_text(elem.get('aria-label') or elem.text_content())
                if text and parse_price_values(text):
                    candidates.append(text)

        for i, text in enumerate(dict.fromkeys(candidates)):
            if i < len(price_names) and price_names[i]:
                key = price_names[i]
            else:
                key = 'price' if i == 0 else f'price_{i + 1}'
            prices[key] = text
        return prices

    def _parse_extra_attributes(self, root):
        extras = {}
        spans = root.cssselect('div[class="a-fixed-left-grid-inner"] > div > span')
        values = [clean_text(x.text_content()) for x in spans]
        values = [value for value in values if value]
        for i in range(0, len(values) - 1, 2):
            key = values[i]
            value = values[i + 1]
            if key and value and key != value:
                extras[key] = value
        return extras

    def _get_availability_from_html(self, root, prices=None):
        """
        Parse best-effort availability from a search result card.

        Amazon search cards do not expose a dedicated stock field. Only
        explicit out-of-stock or in-stock phrases are treated as known.
        """
        text = clean_text(root.text_content())

        unavailable_patterns = [
            r'\bcurrently unavailable\b',
            r'\btemporarily out of stock\b',
            r'\bout of stock\b',
            r'\bno featured offers available\b',
            r'\bcurrently not available\b',
            r'\bnot available\b',
            r'\bdiscontinued\b',
            r'\bsold out\b',
        ]
        for pattern in unavailable_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(0), False

        available_patterns = [
            r'\bonly\s+\d+\s+left\s+in stock\b',
            r'\bin stock\b',
            r'\bavailable to ship\b',
            r'\bships from\b',
            r'\bfree delivery\b',
        ]
        for pattern in available_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(0), True

        return None, None


    @requires_valid_data(default=[])
    def get_prices(self, key=None):
        """
        Get a list of floats from the dictionary of price text.

        A key can be passed to explicitly specify the prices to select.
        If the key is None, all price keys are used.

        Args:
            key (str or list): A key or list of keys in the price dictionary.

        Returns:
            list: Sorted list of floats for the specified prices.

        Raises:
            KeyError: If a specified key is not found in prices.
        """
        keys = []
        if key is None:
            keys = self.prices.keys()
        elif isinstance(key, list):
            keys = key
        else:
            keys = [key]

        prices = []
        for k in keys:
            if k not in self.prices:
                raise KeyError(k)
            prices.extend(parse_price_values(self.prices[k]))

        return sorted(prices)
        
    def get_asin(self):
        """
        Extract the ASIN (Amazon Standard Identification Number) from the product URL.

        Returns:
            str or None: The 10-character ASIN, or None if not found.
        """
        if not self.product_url:
            return None
        return extract_asin(self.product_url)

    def fetch_details(self, level=None, region=None):
        """
        Fetch detailed product information from Amazon.

        This method makes HTTP requests to Amazon to retrieve additional
        product information beyond what's available in search results.

        Args:
            level: DetailLevel enum specifying how much detail to fetch:
                - DetailLevel.SEARCH (0): No request, use existing data
                - DetailLevel.BASIC (1): Fetch product page (title, brand, specs, etc.)
                - DetailLevel.REVIEWS (2): Also fetch reviews page
            region: Amazon region code (e.g., 'US', 'UK', 'DE'). Defaults to US.

        Returns:
            self: Returns self for method chaining

        Example:
            >>> product = search_results.rget(0)
            >>> product.fetch_details(level=DetailLevel.BASIC)
            >>> print(product.details.brand)
        """
        if level is None:
            level = DetailLevel.BASIC

        if region is not None:
            self._region = region

        asin = self.get_asin()
        if not asin:
            self._set_fetch_error('Cannot fetch details without a valid ASIN')
            return self

        base_url = build_base_url(self._region)

        # Level 1: Fetch product page details
        if level.value >= DetailLevel.BASIC.value:
            product_url = PRODUCT_URL % (base_url, asin)
            try:
                html_elem = fetch_html(product_url)
                self.details = AmzProductDetails(html_elem)
            except FetchError as e:
                self._set_fetch_error(str(e))
                return self

        # Level 2: Fetch reviews page
        if level.value >= DetailLevel.REVIEWS.value:
            reviews_url = REVIEWS_URL % (base_url, asin)
            try:
                html_elem = fetch_html(reviews_url)
                self.reviews = AmzReviews(html_elem)
            except FetchError as e:
                self._set_fetch_error(str(e))

        return self

    def _set_fetch_error(self, message):
        self.fetch_error = message
        self._fetch_error = message
