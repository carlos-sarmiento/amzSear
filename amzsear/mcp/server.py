"""FastMCP server for amzsear."""
import argparse
import logging
from typing import Any, Literal

import anyio
from lxml import html as html_module
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.server import TransportSecuritySettings

try:
    from amzsear import AmzProduct, AmzProductDetails, AmzReviews, AmzSear
    from amzsear.core import FetchError, build_base_url, build_url, fetch_html
    from amzsear.core.consts import DEFAULT_REGION, PRODUCT_URL, REGION_CODES, REVIEWS_URL
    from amzsear.core.selectors import DetailLevel
    from amzsear.core.utils import is_asin, normalize_asin, validate_positive_int
except ImportError:
    from .. import AmzProduct, AmzProductDetails, AmzReviews, AmzSear
    from ..core import FetchError, build_base_url, build_url, fetch_html
    from ..core.consts import DEFAULT_REGION, PRODUCT_URL, REGION_CODES, REVIEWS_URL
    from ..core.selectors import DetailLevel
    from ..core.utils import is_asin, normalize_asin, validate_positive_int


DetailLevelName = Literal["SEARCH", "BASIC", "REVIEWS"]
MAX_SEARCH_PAGES = 5
MAX_DETAIL_FETCHES = 10
MAX_HTML_BYTES = 2_000_000
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def json_safe(value: Any) -> Any:
    """Convert amzsear objects into JSON-serializable values."""
    if hasattr(value, "to_dict"):
        return json_safe(value.to_dict())
    if isinstance(value, dict):
        return dict((str(k), json_safe(v)) for k, v in value.items() if k is not None)
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def product_to_dict(product: AmzProduct) -> dict[str, Any]:
    """Return a stable dict for an AmzProduct."""
    data = product.to_dict()
    data["asin"] = product.get_asin()
    data["product_url"] = product.product_url
    data["fetch_error"] = product.fetch_error
    return json_safe(data)


def details_level(value: DetailLevelName | int | None) -> DetailLevel:
    """Parse a detail-level name or integer."""
    if value is None:
        return DetailLevel.BASIC
    name = str(value).upper()
    if name in DetailLevel.__members__:
        return DetailLevel[name]
    raise ValueError("detail_level must be SEARCH, BASIC, or REVIEWS")


def product_for_asin(asin: str, region: str = DEFAULT_REGION) -> AmzProduct:
    """Create a product shell for an ASIN."""
    return AmzProduct.from_asin(normalize_asin(asin), region=region)


def normalize_pages(page: int | list[int]) -> int | list[int]:
    """Validate, cap, and deduplicate requested search pages."""
    if isinstance(page, int):
        pages = [page]
    else:
        pages = list(page)
    if not pages:
        raise ValueError("page must include at least one positive integer")
    if len(pages) > MAX_SEARCH_PAGES:
        raise ValueError(f"page may contain at most {MAX_SEARCH_PAGES} pages")
    normalized = []
    seen = set()
    for raw_page in pages:
        parsed = validate_positive_int(raw_page, "page")
        if parsed not in seen:
            normalized.append(parsed)
            seen.add(parsed)
    return normalized[0] if len(normalized) == 1 else normalized


def parse_html_root(html: str):
    """Parse bounded HTML input with useful errors."""
    if not html or not html.strip():
        raise ValueError("html must not be empty")
    html_bytes = html.encode("utf-8")
    if len(html_bytes) > MAX_HTML_BYTES:
        raise ValueError(f"html must be at most {MAX_HTML_BYTES} bytes")
    try:
        return html_module.fromstring(html_bytes)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid HTML: {exc}") from exc


def search_products_impl(
    query: str,
    page: int | list[int] = 1,
    region: str = DEFAULT_REGION,
    select: str | int | None = None,
    detail_level: DetailLevelName = "SEARCH",
) -> dict[str, Any]:
    level = details_level(detail_level)
    page = normalize_pages(page)
    results = AmzSear(query=query, page=page, region=region)
    products = list(results.products())

    if select is not None:
        if is_asin(select):
            products = [results.get(normalize_asin(select), raise_error=True)]
        else:
            try:
                selected_index = int(select)
            except (TypeError, ValueError) as exc:
                raise ValueError("select must be a valid ASIN or numeric index") from exc
            products = [results.rget(selected_index, raise_error=True)]

    if level.value > DetailLevel.SEARCH.value:
        if len(products) > MAX_DETAIL_FETCHES:
            raise ValueError(f"detail fetches are capped at {MAX_DETAIL_FETCHES} products per call")
        for product in products:
            product.fetch_details(level=level, region=region)

    return {
        "query": query,
        "page": page,
        "region": region,
        "count": len(products),
        "fetch_errors": json_safe(results.fetch_errors),
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
    asin = normalize_asin(asin)
    reviews_url = REVIEWS_URL % (build_base_url(region), asin)
    fetch_error = None
    reviews = None
    try:
        reviews = AmzReviews(fetch_html(reviews_url))
        fetch_error = reviews.fetch_error
    except FetchError as exc:
        fetch_error = str(exc)
    return {
        "asin": asin,
        "reviews_url": reviews_url,
        "reviews": json_safe(reviews),
        "fetch_error": fetch_error,
    }


def list_regions_impl() -> dict[str, Any]:
    return {"default": DEFAULT_REGION, "regions": REGION_CODES}


def build_search_url_impl(query: str, page: int = 1, region: str = DEFAULT_REGION) -> dict[str, str]:
    page = validate_positive_int(page, "page")
    return {"url": build_url(query=query, page_num=page, region=region)}


def build_product_url_impl(asin: str, region: str = DEFAULT_REGION) -> dict[str, str]:
    asin = normalize_asin(asin)
    return {"url": PRODUCT_URL % (build_base_url(region), asin)}


def parse_search_html_impl(html: str, region: str = DEFAULT_REGION) -> dict[str, Any]:
    results = AmzSear(html_element=parse_html_root(html), region=region)
    return {
        "region": region,
        "count": len(results),
        "products": [product_to_dict(product) for product in results.products()],
    }


def parse_product_details_html_impl(html: str) -> dict[str, Any]:
    details = AmzProductDetails(parse_html_root(html))
    return json_safe(details)


def parse_reviews_html_impl(html: str) -> dict[str, Any]:
    reviews = AmzReviews(parse_html_root(html))
    return json_safe(reviews)


def transport_security(host: str) -> TransportSecuritySettings:
    """Create DNS-rebinding protection settings for local Streamable HTTP."""
    hostnames = {"localhost", "127.0.0.1"}
    if host in LOOPBACK_HOSTS:
        hostnames.add(host)
    allowed_hosts = sorted(f"{name}:*" for name in hostnames if name)
    allowed_hosts.append("[::1]:*")
    allowed_origins = sorted(
        origin
        for name in hostnames
        if name
        for origin in (f"http://{name}:*", f"https://{name}:*")
    )
    allowed_origins.extend(["http://[::1]:*", "https://[::1]:*"])
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def register_tools(app: FastMCP) -> FastMCP:
    """Register amzsear's public functionality as FastMCP tools."""

    @app.tool()
    async def search_products(
        query: str,
        page: int | list[int] = 1,
        region: str = DEFAULT_REGION,
        select: str | int | None = None,
        detail_level: DetailLevelName = "SEARCH",
    ) -> dict[str, Any]:
        """Search Amazon and return amzsear search-result products."""
        return await anyio.to_thread.run_sync(
            lambda: search_products_impl(query, page, region, select, detail_level)
        )

    @app.tool()
    async def get_product(
        asin: str,
        region: str = DEFAULT_REGION,
        detail_level: DetailLevelName = "BASIC",
    ) -> dict[str, Any]:
        """Fetch product data by ASIN."""
        return await anyio.to_thread.run_sync(lambda: get_product_impl(asin, region, detail_level))

    @app.tool()
    async def get_reviews(asin: str, region: str = DEFAULT_REGION) -> dict[str, Any]:
        """Fetch customer reviews for an ASIN."""
        return await anyio.to_thread.run_sync(lambda: get_reviews_impl(asin, region))

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
    logging.getLogger("mcp.server").setLevel(getattr(logging, log_level.upper(), logging.INFO))
    return register_tools(app)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the amzsear FastMCP server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", default=8765, type=int, help="Port to bind (default: 8765)")
    parser.add_argument("--path", default="/mcp", help="MCP endpoint path (default: /mcp)")
    parser.add_argument("--log-level", default="INFO", help="FastMCP log level (default: INFO)")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow binding to a non-loopback host. Use only on trusted networks.",
    )
    args = parser.parse_args(argv)

    if args.host not in LOOPBACK_HOSTS and not args.allow_network:
        parser.error("--host must be loopback unless --allow-network is set")

    app = create_app(host=args.host, port=args.port, path=args.path, log_level=args.log_level)
    app.run(transport="streamable-http")


if __name__ == "__main__":
    main()
