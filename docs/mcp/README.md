# MCP Server

amzSear includes a FastMCP-based Streamable HTTP MCP server using the official
Python MCP SDK. It exposes the package's search, product lookup, review lookup,
region, URL building, and HTML parsing functionality as MCP tools.

## Run Locally

```bash
uv run amzsear-mcp --host 127.0.0.1 --port 8765
```

The MCP endpoint is:

```text
http://127.0.0.1:8765/mcp
```

The server binds to localhost by default and enables the SDK's DNS-rebinding
protection. Use `--path` to change the endpoint path and `--log-level` to
control FastMCP logging. Binding to a non-loopback host requires
`--allow-network`; use that only on trusted networks.

## Tools

The server exposes these tools:

- `search_products`: search Amazon by query, page, region, optional selection,
  and optional detail level. Page lists are capped and deduplicated.
- `get_product`: fetch product data by ASIN with `SEARCH`, `BASIC`, or
  `REVIEWS` detail level.
- `get_reviews`: fetch reviews for an ASIN.
- `list_regions`: return supported Amazon region codes.
- `build_search_url`: build the Amazon search URL amzSear would request.
- `build_product_url`: build an Amazon product URL for an ASIN.
- `parse_search_html`: parse supplied Amazon search-result HTML.
- `parse_product_details_html`: parse supplied Amazon product-page HTML.
- `parse_reviews_html`: parse supplied Amazon review-page HTML.

Tool responses include `structuredContent` and a JSON text content item for
clients that only display text results.

ASIN inputs are validated before URLs are built. HTML parsing tools reject empty
or oversized input and accept documents with XML encoding declarations.
