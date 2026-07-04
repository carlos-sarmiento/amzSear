import unittest

from lxml import html

from amzsear import AmzProduct


def product_from_card(body):
    card = f"""
    <div data-asin="B000123456" data-component-type="s-search-result">
        <div>
            <span>
                <a href="/dp/B000123456"><h2>Example Product</h2></a>
            </span>
        </div>
        <img src="https://example.com/product.jpg">
        {body}
    </div>
    """
    return AmzProduct(html.fromstring(card))


class ProductAvailabilityTest(unittest.TestCase):
    def test_currently_unavailable_marks_product_unavailable(self):
        product = product_from_card("<span>Currently unavailable</span>")

        self.assertEqual(product.availability.lower(), "currently unavailable")
        self.assertFalse(product.is_available)

    def test_delivery_text_marks_product_available(self):
        product = product_from_card("<span>FREE delivery Tue, May 19</span>")

        self.assertEqual(product.availability.lower(), "free delivery")
        self.assertTrue(product.is_available)

    def test_unavailable_patterns(self):
        cases = [
            "Temporarily out of stock",
            "Out of stock",
            "No featured offers available",
            "Currently not available",
            "Discontinued",
            "Sold out",
        ]
        for text in cases:
            with self.subTest(text=text):
                product = product_from_card(f"<span>{text}</span>")
                self.assertFalse(product.is_available)

    def test_available_patterns(self):
        cases = [
            "Only 2 left in stock",
            "In stock",
            "Available to ship",
            "Ships from Amazon",
        ]
        for text in cases:
            with self.subTest(text=text):
                product = product_from_card(f"<span>{text}</span>")
                self.assertTrue(product.is_available)

    def test_price_only_availability_is_unknown(self):
        product = product_from_card('<span class="a-price-whole">$12.99</span>')

        self.assertIsNone(product.availability)
        self.assertIsNone(product.is_available)


if __name__ == "__main__":
    unittest.main()
