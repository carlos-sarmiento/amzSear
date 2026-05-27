"""FastMCP server for amzsear."""
import argparse
from typing import Any, Literal

from lxml import html as html_module
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

try:
    from amzsear import AmzProduct, AmzProductDetails, AmzReviews, AmzSear, __version__
    from amzsear.core import build_base_url, build_url
    from amzsear.core.consts import DEFAULT_REGION, PRODUCT_URL, REGION_CODES, REVIEWS_URL
    from amzsear.core.selectors import DetailLevel
except ImportError:
    from .. import AmzProduct, AmzProductDetails, AmzReviews, AmzSear, __version__
    from ..core import build_base_url, build_url
    from ..core.consts import DEFAULT_REGION, PRODUCT_URL, REGION_CODES, REVIEWS_URL
    from ..core.selectors import DetailLevel


DetailLevelName = Literal["SEARCH", "BASIC", "REVIEWS", "FULL"]


def json_safe(value: Any) -> Any:
    """Convert amzsear objects into JSON-serializable values."""
    if hasattr(value, "to_dict"):
        return json_safe(value.to_dict())
    if isinstance(value, dict):
        return dict((k, json_safe(v)) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def product_to_dict(product: AmzProduct) -> dict[str, Any]:
    """Return a stable dict for an AmzProduct."""
    data = product.to_dict()
    data["asin"] = product.get_asin()
    data["product_url"] = product.product_url
    if product._fetch_error:
        data["fetch_error"] = product._fetch_error
    return json_safe(data)


def details_level(value: DetailLevelName | int | None) -> DetailLevel:
    """Parse a detail-level name or integer."""
    if value is None:
        return DetailLevel.BASIC
    if isinstance(value, int):
        for level in DetailLevel:
            if level.value == value:
                return level
    name = str(value).upper()
    if name in DetailLevel.__members__:
        return DetailLevel[name]
    raise ValueError("detail_level must be SEARCH, BASIC, REVIEWS, FULL, or 0-3")


def product_for_asin(asin: str, region: str = DEFAULT_REGION) -> AmzProduct:
    """Create a product shell for an ASIN."""
    product = AmzProduct()
    product.product_url = PRODUCT_URL % (build_base_url(region), asin)
    product._region = region
    product._is_valid = True
    return product


def search_products_impl(
    query: str,
    page: int | list[int] = 1,
    region: str = DEFAULT_REGION,
    select: str | int | None = None,
    detail_level: DetailLevelName = "SEARCH",
) -> dict[str, Any]:
    level = details_level(detail_level)
    results = AmzSear(query=query, page=page, region=region)
    products = list(results.products())

    if select is not None:
        if isinstance(select, int) or str(select).isdigit():
            products = [results.rget(int(select), raise_error=True)]
        else:
            products = [results.get(str(select), raise_error=True)]

    if level.value > DetailLevel.SEARCH.value:
        for product in products:
            product.fetch_details(level=level, region=region)

    return {
        "query": query,
        "page": page,
        "region": region,
        "count": len(products),
        "products": [product_to_dict(product) for product in products],
    }


def get_product_impl(
    asin: str,
    region: str = DEFAULT_REGION,
    detail_level: DetailLevelName = "BASIC",
) -> dict[str, Any]:
    level = details_level(detail_level)
    product = product_for_asin(asin, region=region)
    if level.value > DetailLevel.SEARCH.value:
        product.fetch_details(level=level, region=region)
    return product_to_dict(product)


def get_reviews_impl(asin: str, region: str = DEFAULT_REGION) -> dict[str, Any]:
    product = product_for_asin(asin, region=region)
    product.fetch_details(level=DetailLevel.REVIEWS, region=region)
    return {
        "asin": asin,
        "reviews_url": REVIEWS_URL % (build_base_url(region), asin),
        "reviews": json_safe(product.reviews),
        "fetch_error": product._fetch_error,
    }


def list_regions_impl() -> dict[str, Any]:
    return {"default": DEFAULT_REGION, "regions": REGION_CODES}


def build_search_url_impl(query: str, page: int = 1, region: str = DEFAULT_REGION) -> dict[str, str]:
    return {"url": build_url(query=query, page_num=page, region=region)}


def build_product_url_impl(asin: str, region: str = DEFAULT_REGION) -> dict[str, str]:
    return {"url": PRODUCT_URL % (build_base_url(region), asin)}


def parse_search_html_impl(html: str, region: str = DEFAULT_REGION) -> dict[str, Any]:
    results = AmzSear(html=html, region=region)
    return {
        "region": region,
        "count": len(results),
        "products": [product_to_dict(product) for product in results.products()],
    }


def parse_product_details_html_impl(html: str) -> dict[str, Any]:
    details = AmzProductDetails(html_module.fromstring(html))
    return json_safe(details)


def parse_reviews_html_impl(html: str) -> dict[str, Any]:
    reviews = AmzReviews(html_module.fromstring(html))
    return json_safe(reviews)


def transport_security(host: str) -> TransportSecuritySettings:
    """Create DNS-rebinding protection settings for local Streamable HTTP."""
    hostnames = {"localhost", "127.0.0.1", "::1", host}
    if host == "0.0.0.0":
        hostnames.update({"localhost", "127.0.0.1"})
    allowed_hosts = sorted("%s:*" % name for name in hostnames if name)
    allowed_origins = sorted(
        origin
        for name in hostnames
        if name
        for origin in ("http://%s:*" % name, "https://%s:*" % name)
    )
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def register_tools(app: FastMCP) -> FastMCP:
    """Register amzsear's public functionality as FastMCP tools."""

    @app.tool()
    def search_products(
        query: str,
        page: int | list[int] = 1,
        region: str = DEFAULT_REGION,
        select: str | int | None = None,
        detail_level: DetailLevelName = "SEARCH",
    ) -> dict[str, Any]:
        """Search Amazon and return amzsear search-result products."""
        return search_products_impl(query, page, region, select, detail_level)

    @app.tool()
    def get_product(
        asin: str,
        region: str = DEFAULT_REGION,
        detail_level: DetailLevelName = "BASIC",
    ) -> dict[str, Any]:
        """Fetch product data by ASIN."""
        return get_product_impl(asin, region, detail_level)

    @app.tool()
    def get_reviews(asin: str, region: str = DEFAULT_REGION) -> dict[str, Any]:
        """Fetch customer reviews for an ASIN."""
        return get_reviews_impl(asin, region)

    @app.tool()
    def list_regions() -> dict[str, Any]:
        """List supported Amazon region codes."""
        return list_regions_impl()

    @app.tool()
    def build_search_url(query: str, page: int = 1, region: str = DEFAULT_REGION) -> dict[str, str]:
        """Build the Amazon search URL used by amzsear."""
        return build_search_url_impl(query, page, region)

    @app.tool()
    def build_product_url(asin: str, region: str = DEFAULT_REGION) -> dict[str, str]:
        """Build an Amazon product URL for an ASIN."""
        return build_product_url_impl(asin, region)

    @app.tool()
    def parse_search_html(html: str, region: str = DEFAULT_REGION) -> dict[str, Any]:
        """Parse Amazon search-result HTML without fetching a URL."""
        return parse_search_html_impl(html, region)

    @app.tool()
    def parse_product_details_html(html: str) -> dict[str, Any]:
        """Parse Amazon product-page HTML without fetching a URL."""
        return parse_product_details_html_impl(html)

    @app.tool()
    def parse_reviews_html(html: str) -> dict[str, Any]:
        """Parse Amazon reviews-page HTML without fetching a URL."""
        return parse_reviews_html_impl(html)

    return app


def create_app(
    host: str = "127.0.0.1",
    port: int = 8765,
    path: str = "/mcp",
    log_level: str = "INFO",
) -> FastMCP:
    """Create the FastMCP application."""
    app = FastMCP(
        "amzsear",
        instructions="Search Amazon products and fetch product details through amzsear.",
        host=host,
        port=port,
        streamable_http_path=path,
        stateless_http=True,
        json_response=True,
        log_level=log_level,
        transport_security=transport_security(host),
    )
    return register_tools(app)


mcp = create_app()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the amzsear FastMCP server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", default=8765, type=int, help="Port to bind (default: 8765)")
    parser.add_argument("--path", default="/mcp", help="MCP endpoint path (default: /mcp)")
    parser.add_argument("--log-level", default="INFO", help="FastMCP log level (default: INFO)")
    args = parser.parse_args(argv)

    app = create_app(host=args.host, port=args.port, path=args.path, log_level=args.log_level)
    app.run(transport="streamable-http")


if __name__ == "__main__":
    main()
