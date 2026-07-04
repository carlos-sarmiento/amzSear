import unittest

from mcp.shared.memory import create_connected_server_and_client_session

from amzsear.mcp.server import (
    build_product_url_impl,
    create_app,
    details_level,
    normalize_pages,
    parse_product_details_html_impl,
    parse_search_html_impl,
    transport_security,
)


class McpToolImplementationTest(unittest.TestCase):
    def test_build_product_url_impl(self):
        self.assertEqual(
            build_product_url_impl("B000123456"),
            {"url": "https://www.amazon.com/dp/B000123456"},
        )

    def test_parse_search_html_impl_uses_existing_parser(self):
        html = """
        <div data-asin="B000123456" data-component-type="s-search-result">
            <div><span><a href="/dp/B000123456"><h2>Example Product</h2></a></span></div>
            <img src="https://example.com/product.jpg">
            <span>Currently unavailable</span>
        </div>
        """

        result = parse_search_html_impl(html)
        product = result["products"][0]

        self.assertEqual(product["asin"], "B000123456")
        self.assertFalse(product["is_available"])

    def test_transport_security_restricts_hosts_and_origins(self):
        settings = transport_security("127.0.0.1")

        self.assertTrue(settings.enable_dns_rebinding_protection)
        self.assertIn("127.0.0.1:*", settings.allowed_hosts)
        self.assertIn("[::1]:*", settings.allowed_hosts)
        self.assertIn("http://127.0.0.1:*", settings.allowed_origins)

    def test_invalid_asin_rejected(self):
        with self.assertRaises(ValueError):
            build_product_url_impl("not-an-asin")

    def test_page_list_is_capped_and_deduplicated(self):
        self.assertEqual(normalize_pages([1, 1, 2]), [1, 2])
        with self.assertRaises(ValueError):
            normalize_pages([1, 2, 3, 4, 5, 6])

    def test_detail_level_rejects_unimplemented_full_level(self):
        with self.assertRaises(ValueError):
            details_level("FULL")

    def test_parse_html_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            parse_product_details_html_impl("")


class FastMcpServerTest(unittest.IsolatedAsyncioTestCase):
    async def test_fastmcp_lists_amzsear_tools(self):
        async with create_connected_server_and_client_session(
            create_app(log_level="ERROR"),
            raise_exceptions=True,
        ) as session:
            response = await session.list_tools()

        names = [tool.name for tool in response.tools]
        self.assertIn("search_products", names)
        self.assertIn("get_product", names)
        self.assertIn("get_reviews", names)
        self.assertIn("list_regions", names)
        self.assertIn("build_search_url", names)
        self.assertIn("build_product_url", names)
        self.assertIn("parse_search_html", names)
        self.assertIn("parse_product_details_html", names)
        self.assertIn("parse_reviews_html", names)

    async def test_fastmcp_tool_call_returns_structured_content(self):
        async with create_connected_server_and_client_session(
            create_app(log_level="ERROR"),
            raise_exceptions=True,
        ) as session:
            response = await session.call_tool(
                "build_product_url",
                {"asin": "B000123456"},
            )

        self.assertEqual(
            response.structuredContent,
            {"url": "https://www.amazon.com/dp/B000123456"},
        )

    async def test_fastmcp_parse_search_html_tool(self):
        html = """
        <div data-asin="B000123456" data-component-type="s-search-result">
            <div><span><a href="/dp/B000123456"><h2>Example Product</h2></a></span></div>
            <img src="https://example.com/product.jpg">
            <span>Currently unavailable</span>
        </div>
        """

        async with create_connected_server_and_client_session(
            create_app(log_level="ERROR"),
            raise_exceptions=True,
        ) as session:
            response = await session.call_tool("parse_search_html", {"html": html})

        product = response.structuredContent["products"][0]
        self.assertEqual(product["asin"], "B000123456")
        self.assertFalse(product["is_available"])


if __name__ == "__main__":
    unittest.main()
