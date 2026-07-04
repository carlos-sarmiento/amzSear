import unittest

from lxml import html

from amzsear import AmzProductDetails, AmzReview, AmzReviews


class DetailsReviewsRegressionTest(unittest.TestCase):
    def test_details_parse_dynamic_images_plural_stars_and_local_numbers(self):
        node = html.fromstring("""
        <html>
            <span id="productTitle">Example Product</span>
            <a id="bylineInfo">Visit the Store Labs Store</a>
            <img id="landingImage" data-a-dynamic-image='{"https://example.com/a.jpg":[1000,1000]}' />
            <span id="acrCustomerReviewText">1.234 ratings</span>
            <span id="acrPopover" title="4,5 out of 5 stars"></span>
            <tr class="a-histogram-row"><td>5 stars 85%</td></tr>
        </html>
        """)

        details = AmzProductDetails(node)

        self.assertEqual(details.brand, "Store Labs")
        self.assertEqual(details.image_urls, ["https://example.com/a.jpg"])
        self.assertEqual(details.review_count, 1234)
        self.assertEqual(details.average_rating, 4.5)
        self.assertEqual(details.star_distribution, {5: 85})

    def test_review_absent_verified_and_helpful_are_unknown(self):
        node = html.fromstring("""
        <div data-hook="review">
            <span class="a-profile-name">Jane</span>
            <i data-hook="review-star-rating">5.0 out of 5 stars</i>
            <span data-hook="review-title">5.0 out of 5 stars Useful</span>
            <span data-hook="review-body">Helpful text</span>
        </div>
        """)

        review = AmzReview(node)

        self.assertTrue(review.is_valid())
        self.assertIsNone(review.verified)
        self.assertIsNone(review.helpful_count)

    def test_reviews_page_total_count_selector_marks_valid(self):
        node = html.fromstring("""
        <html>
            <div data-hook="cr-filter-info-review-count">1,234 total ratings</div>
        </html>
        """)

        reviews = AmzReviews(node)

        self.assertTrue(reviews.is_valid())
        self.assertEqual(reviews.total_count, 1234)

    def test_reviews_sign_in_page_exposes_fetch_error(self):
        node = html.fromstring("""
        <html>
            <h1>Sign in</h1>
            <p>Customer reviews</p>
        </html>
        """)

        reviews = AmzReviews(node)

        self.assertTrue(reviews.is_valid())
        self.assertIn("sign-in", reviews.fetch_error)
        self.assertEqual(
            reviews.to_dict(),
            {"fetch_error": "Amazon returned a sign-in page instead of reviews"},
        )


if __name__ == "__main__":
    unittest.main()
