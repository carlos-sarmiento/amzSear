"""
CSS selectors for parsing Amazon product pages.
These selectors work with lxml/cssselect on raw HTML - no JS execution needed.
"""
from enum import Enum


class DetailLevel(Enum):
    """
    Detail levels for product information fetching.
    Higher levels include all data from lower levels plus additional requests.
    """
    SEARCH = 0      # No extra request (current behavior from search results)
    BASIC = 1       # Product page details (1 request)
    REVIEWS = 2     # + Reviews page (1 additional request)


# Product detail page selectors
PRODUCT_TITLE = '#productTitle'
BRAND_LINK = '#bylineInfo'
FEATURE_BULLETS = '#feature-bullets ul li span'
PRODUCT_DESCRIPTION = '#productDescription'
PRODUCT_DESCRIPTION_ALT = '#productDescription_feature_div'

# Technical details table
TECH_DETAILS_TABLE = '#prodDetails table'
TECH_DETAILS_ROWS = '#prodDetails table tr'
PRODUCT_DETAILS_TABLE = '#productDetails_techSpec_section_1 tr'
PRODUCT_DETAILS_TABLE_ALT = '#productDetails_detailBullets_sections1 tr'

# Images
IMAGE_GALLERY = '#altImages img'
MAIN_IMAGE = '#landingImage'
IMAGE_THUMB_LIST = '#imageBlock img'

# Reviews on product page
REVIEW_COUNT = '#acrCustomerReviewText'
RATING_STARS = '#acrPopover'
STAR_HISTOGRAM = '.a-histogram-row'
CUSTOMER_REVIEWS_SUMMARY = '.cr-insights-widget'
TOP_REVIEWS = '[data-hook="review"]'

# Reviews page selectors
REVIEW_ITEM = '[data-hook="review"]'
REVIEWS_TOTAL_COUNT = '[data-hook="cr-filter-info-review-count"], #filter-info-section'
REVIEW_TITLE = '[data-hook="review-title"]'
REVIEW_RATING = '[data-hook="review-star-rating"]'
REVIEW_DATE = '[data-hook="review-date"]'
REVIEW_BODY = '[data-hook="review-body"]'
REVIEW_AUTHOR = '.a-profile-name'
REVIEW_VERIFIED = '[data-hook="avp-badge"]'
REVIEW_HELPFUL = '[data-hook="helpful-vote-statement"]'
REVIEW_IMAGES = '[data-hook="review-image-tile"]'
