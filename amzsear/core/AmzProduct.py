import re

try:
    from amzsear.core.AmzBase import AmzBase
    from amzsear.core import requires_valid_data, capture_exception, build_url, build_base_url, fetch_html, FetchError
    from amzsear.core.AmzRating import AmzRating
    from amzsear.core.AmzProductDetails import AmzProductDetails
    from amzsear.core.AmzReviews import AmzReviews
    from amzsear.core.selectors import DetailLevel
    from amzsear.core.consts import PRODUCT_URL, REVIEWS_URL, QA_URL, DEFAULT_REGION
except ImportError:
    from .AmzBase import AmzBase
    from . import requires_valid_data, capture_exception, build_url, build_base_url, fetch_html, FetchError
    from .AmzRating import AmzRating
    from .AmzProductDetails import AmzProductDetails
    from .AmzReviews import AmzReviews
    from .selectors import DetailLevel
    from .consts import PRODUCT_URL, REVIEWS_URL, QA_URL, DEFAULT_REGION


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
    _fetch_error = None  # Error message if fetch_details failed

    _all_attrs = ['title','product_url','image_url','rating','prices',
        'availability', 'is_available',
        'extra_attributes', 'subtext', 'details', 'reviews']

    def __init__(self, html_element=None, region=DEFAULT_REGION):
        super().__init__()
        self._region = region
        if html_element is not None:
            html_dict = self._get_from_html(html_element)
            for k, v in html_dict.items():
                setattr(self, k, v)
            if len(html_dict) > 0:
                self._is_valid = True
                # Set _index to ASIN for use as key in AmzSear collection
                self._index = self.get_asin()

    @capture_exception(IndexError, default={})
    def _get_from_html(self, root):
        """
        Parse product data from HTML element.

        Returns:
            dict: A dict of fields with extracted data.
        """
        d = {}

        title_root = [x for x in root.cssselect('a') if len(x.cssselect('h2')) > 0][0]
        d['title'] = ''.join([x.text_content() for x in title_root.cssselect('h2')])
        d['product_url'] = build_url(title_root.get('href'), region=self._region)
        for elem in title_root.getparent().getparent().cssselect('div[class="a-row a-spacing-none"]'):
            temp_subtext = ''.join([x.text_content() for x in elem.cssselect('span[class*="a-size-small"]')])
            if len(temp_subtext) > 0:
                d['subtext'] = d.get('subtext',[]) + [temp_subtext]


        d['image_url'] = root.cssselect('img[src]')[0].get('src')
        d['rating'] = AmzRating(root) or None

        d['prices'] = {}
        price_names = root.cssselect('h3[data-attribute]')
        price_text = root.cssselect('span[class^="a"]')
        price_text = filter(lambda x: re.match(r'^[^a-z\-]+$', str(x.text)) and
            re.search(r'[.,]', str(x.text)) and re.search(r'\d', str(x.text)), price_text)

        for i, el in enumerate(price_text):
            if i >= len(price_names):
                price_key = str(len(d['prices']))  # defaults to a number if no name for price type
            else:
                price_key = price_names[i].text
            d['prices'][price_key] = el.text

        availability, is_available = self._get_availability_from_html(root, d['prices'])
        if availability is not None:
            d['availability'] = availability
        if is_available is not None:
            d['is_available'] = is_available

        extras = root.cssselect('div[class="a-fixed-left-grid-inner"] > div > span')
        extras = [re.sub(r'\s+', ' ', x.text_content().strip()) for x in extras]
        d['extra_attributes'] = dict(list(zip(extras,extras[1:]))[::2])

        # _index is the ASIN, used as key in AmzSear collection
        d['_index'] = None  # Will be set from product_url after extraction

        # clean up before returning
        return dict(map(lambda k: (k, d[k].strip() if isinstance(d[k],str) else d[k]), d)) 

    def _get_availability_from_html(self, root, prices=None):
        """
        Parse best-effort availability from a search result card.

        Amazon search cards do not expose a dedicated stock field. Only
        explicit out-of-stock or in-stock phrases are treated as known.
        """
        text = re.sub(r'\s+', ' ', root.text_content()).strip()

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
            prices += [re.sub(',', '', x) for x in re.findall(r'[\d.,]+', self.prices[k])]

        return sorted(map(float, prices))
        
    def get_asin(self):
        """
        Extract the ASIN (Amazon Standard Identification Number) from the product URL.

        Returns:
            str or None: The 10-character ASIN, or None if not found.
        """
        if not self.product_url:
            return None
        result = re.search(r'(?:/|%2F)dp(?:/|%2F)([A-Z0-9]{10})', self.product_url)
        if result is not None:
            result = result.group(1)
        return result

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
                - DetailLevel.FULL (3): Also fetch Q&A page
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
            return self

        base_url = build_base_url(self._region)

        # Level 1: Fetch product page details
        if level.value >= DetailLevel.BASIC.value:
            product_url = PRODUCT_URL % (base_url, asin)
            try:
                html_elem = fetch_html(product_url)
                self.details = AmzProductDetails(html_elem)
            except FetchError as e:
                self._fetch_error = str(e)
                return self

        # Level 2: Fetch reviews page
        if level.value >= DetailLevel.REVIEWS.value:
            reviews_url = REVIEWS_URL % (base_url, asin)
            try:
                html_elem = fetch_html(reviews_url)
                self.reviews = AmzReviews(html_elem)
            except FetchError as e:
                self._fetch_error = str(e)

        # Level 3: Q&A would be fetched here (not implemented yet)
        # if level.value >= DetailLevel.FULL.value:
        #     qa_url = QA_URL % (base_url, asin)
        #     ...

        return self
