# Defaults
REPR_MAX_LEN_DEFAULT = 90

# URL CODES
REGION_CODES = {
    'AU': '.com.au',
    'AE': '.ae',
    'BR': '.com.br',
    'CA': '.ca',
    'CN': '.cn',
    'DE': '.de',
    'ES': '.es',
    'FR': '.fr',
    'IN': '.in',
    'IT': '.it',
    'JP': '.co.jp',
    'MX': '.com.mx',
    'NL': '.nl',
    'SG': '.com.sg',
    'UK': '.co.uk',
    'US': '.com'
}

DEFAULT_REGION = "US"

# URL Building
BASE_URL = 'https://www.amazon'
SEARCH_URL = '%s/s?k=%s&page=%s'

# Product detail page URLs
PRODUCT_URL = '%s/dp/%s'  # BASE_URL + region, ASIN
REVIEWS_URL = '%s/product-reviews/%s'  # BASE_URL + region, ASIN

# Request headers for all Amazon requests
# Note: Don't include Accept-Encoding to get uncompressed response
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
}
