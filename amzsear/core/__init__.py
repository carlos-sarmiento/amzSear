from copy import copy
from functools import wraps
from urllib import parse

import requests
from lxml import html as html_module
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .consts import BASE_URL, DEFAULT_REGION, REGION_CODES, REQUEST_HEADERS, SEARCH_URL
from .utils import is_amazon_url, validate_positive_int


def requires_valid_data(default=None):
    """Decorator for valid data in an object, returns default if not valid."""
    def decorator(f):
        @wraps(f)
        def wrapper(self, *args, **kws):
            if hasattr(self, '_is_valid') and self._is_valid:
                return f(self, *args, **kws)
            else:
                return _default_value(default)
        return wrapper
    return decorator


def _default_value(default):
    """Return a fresh copy for mutable decorator defaults."""
    if isinstance(default, (list, dict, set)):
        return copy(default)
    return default


def capture_exception(error, default=None):
    """Decorator to capture exception and return a default instead."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kws):
            try:
                return f(*args, **kws)
            except error:
                return _default_value(default)
        return wrapper
    return decorator


def build_url(url=None, query='', page_num=1, region=DEFAULT_REGION):
    """Build a URL based on a query."""
    if url is None:
        # Build from query, page_num and region
        base = build_base_url(region)
        page_num = validate_positive_int(page_num, "page_num")
        url = SEARCH_URL % (base, parse.quote(query, safe=''), page_num)

    if url.startswith('/'):
        url = build_base_url(region) + url

    if not is_amazon_url(url):
        raise ValueError(f'{repr(url)} is not an Amazon URL')

    parsed_obj = parse.urlparse(url)
    query_dict = parse.parse_qs(parsed_obj.query)
    parsed_obj = parsed_obj._replace(query=parse.urlencode(query_dict, doseq=True))
    return parsed_obj.geturl()


def build_base_url(region=DEFAULT_REGION):
    """Build base URL based on region."""
    find_region = region.upper()
    if find_region not in REGION_CODES:
        raise ValueError(f'{repr(region)} is not a known Amazon region')

    return BASE_URL + REGION_CODES[find_region]


class FetchError(Exception):
    """Raised when fetching a URL fails."""
    pass


class FetchBlockedError(FetchError):
    """Raised when Amazon returns a captcha, robot check, or login interstitial."""
    pass


def _make_session():
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_SESSION = _make_session()


def _blocked_reason(content):
    text = content.decode("utf-8", errors="ignore").lower()
    if "validatecaptcha" in text or "robot check" in text:
        return "Amazon returned a robot-check/captcha page"
    if "api-services-support@amazon" in text:
        return "Amazon returned an automated-traffic block page"
    if "/ap/signin" in text and "customer reviews" in text:
        return "Amazon returned a sign-in page instead of review data"
    return None


def fetch_html(url, session=None):
    """
    Fetch HTML content from a URL and return parsed lxml element.

    Args:
        url: The URL to fetch

    Returns:
        lxml HTML element

    Raises:
        FetchError: If the fetch fails (network error, 404, etc.)
    """
    session = session or _SESSION
    try:
        response = session.get(url, headers=REQUEST_HEADERS, timeout=30)
        response.raise_for_status()
        reason = _blocked_reason(response.content)
        if reason:
            raise FetchBlockedError(f"{reason}: {url}")
        return html_module.fromstring(response.content)
    except requests.RequestException as e:
        raise FetchError(f"Failed to fetch {url}: {e}") from e
