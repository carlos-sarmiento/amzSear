import unittest
from unittest import mock

from lxml import html

from amzsear import AmzProduct, AmzRating, AmzSear
from amzsear.core import FetchError
from amzsear.core.utils import parse_locale_number


def search_card(asin="B000123456", title="Example Product", body=""):
    return f"""
    <div data-asin="{asin}" data-component-type="s-search-result">
        <div><span><a href="/dp/{asin}"><h2>{title}</h2></a></span></div>
        {body}
    </div>
    """


class CoreRegressionTest(unittest.TestCase):
    def test_locale_number_parser_handles_comma_decimal_and_thousands(self):
        self.assertEqual(parse_locale_number("4,5"), 4.5)
        self.assertEqual(parse_locale_number("1.234"), 1234.0)
        self.assertEqual(parse_locale_number("1.234,56 EUR"), 1234.56)
        self.assertEqual(parse_locale_number("$1,234.56"), 1234.56)

    def test_rating_parses_localized_values(self):
        node = html.fromstring("""
        <div>
            <i class="a-icon-star">4,5 out of 5 stars</i>
            <a href="/product-reviews/B000123456">1.234 ratings</a>
        </div>
        """)

        rating = AmzRating(node)

        self.assertTrue(rating.is_valid())
        self.assertEqual(rating.get_numerator(), 4.5)
        self.assertEqual(rating.get_count(), 1234)
        self.assertEqual(rating.get_star_repr(), "*****")

    def test_product_with_missing_image_is_still_valid(self):
        product = AmzProduct(html.fromstring(search_card()))

        self.assertTrue(product.is_valid())
        self.assertEqual(product.get_asin(), "B000123456")

    def test_product_parses_gp_product_asin_and_eu_price(self):
        node = html.fromstring("""
        <div data-asin="B000123456" data-component-type="s-search-result">
            <h2><a href="/gp/product/B000123456">Example Product</a></h2>
            <span class="a-price"><span class="a-offscreen">1.234,56 EUR</span></span>
        </div>
        """)

        product = AmzProduct(node)

        self.assertEqual(product.get_asin(), "B000123456")
        self.assertEqual(product.get_prices(), [1234.56])

    def test_repr_width_setting_updates_products(self):
        results = AmzSear(html=search_card(title="Long Example Product Title"))

        results._set_repr_max_len(20)

        self.assertEqual(results.rget(0).REPR_MAX_LEN, 20)

    def test_aget_single_key_returns_flat_list(self):
        results = AmzSear(html=search_card(title="Example Product"))

        self.assertEqual(results.aget("title"), ["Example Product"])

    def test_multi_page_fetch_keeps_successful_pages_and_records_errors(self):
        good_page = html.fromstring(search_card())

        def fake_fetch(url):
            if "page=2" in url:
                raise FetchError("blocked")
            return good_page

        with mock.patch("amzsear.core.AmzSear.fetch_html", side_effect=fake_fetch):
            results = AmzSear(query="example", page=[1, 2])

        self.assertEqual(len(results), 1)
        self.assertEqual(len(results.fetch_errors), 1)


if __name__ == "__main__":
    unittest.main()
