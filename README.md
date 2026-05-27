# amzSear

The unofficial Amazon Product CLI & API. Easily search the amazon product directory from the command line without the need for an Amazon API key.

Wondering about about an amazon product listing? Find the amzSear!

__Version 2 has been released!__ See [below](#whats-new) for more info.

```text
$ amzsear 'Harry Potter Books'
```

```text
ASIN        Title                                               Prices             Rating
B01CUKZNM2  Harry Potter Paperback Box Set (Books 1-7)          $21.20 - $52.99    *****
B00728DYLA  Harry Potter and the Sorcerer's Stone               $0.00 - $10.99     *****
B00728DYLY  Harry Potter And The Chamber Of Secrets             $0.00 - $10.99     *****
B00728E75S  Harry Potter And The Goblet Of Fire                 $0.00 - $12.99     *****
B00728DYCU  Harry Potter and the Prisoner of Azkaban            $0.00 - $10.99     *****
B00728E6Z4  Harry Potter And The Order Of The Phoenix           $0.00 - $12.99     *****
B00728DYPE  Harry Potter and the Deathly Hallows (Book 7)       $0.00 - $14.99     *****
B00728E6G8  Harry Potter and the Half-Blood Prince (Book 6)     $0.00 - $12.99     *****
B01LTHVLSC  Harry Potter and the Sorcerer's Stone: The Illustr  $9.23 - $39.99     ****
B01LTHXA3C  Harry Potter Complete Book Series Special Edition   $64.88 - $81.95    *****
B01ELVJPJW  Harry Potter and the Cursed Child, Parts One and T  $3.15 - $12.99     ****
```

![Amazon Comparison Shot](amazon_screenshot.png)

<a name="installation"></a>

## Installation

Can easily be be run on Python version 3 or greater with minimal additional dependencies.

Install the dependencies and main package using pip.

```text
$ pip install amzsear
```

For those wanting to upgrade to version 2, use the command:

```text
$ pip install amzsear --upgrade
```

Note: The [Pandas](https://pandas.pydata.org/) package is not a required dependency for amzSear, however a few methods do use it (see [AmzSear.md](docs/core/AmzSear.md#to_dataframe), [AmzBase.md](docs/core/AmzBase.md#to_series)) if one wants to integrate with Pandas. If this is the case, pandas should be installed separately using:

```text
$ pip install pandas
```

<a name="usage"></a>

### Usage

AmzSear can be used in two ways, from the command line and as a Python package.

#### CLI

The amzSear CLI allows Amazon search queries to be performed directly from the command line. In it's simplest form, the CLI only requires a query.

```text
$ amzsear 'Harry Potter Books'
```

However, additional options can be set to select the page number, item, region or the output format. For example:

```text
$ amzsear 'Harry Potter' -p 2 -s B00728DYLA -j
```

The above query will display the item with ASIN B00728DYLA on page 2 as a JSON object. The `-s` flag accepts both ASIN and numeric index (0-based position).

Search results include a best-effort availability signal. The default CLI output shows an
`Available` column, and JSON output includes `availability` and `is_available` fields.
Results without explicit availability text are reported as unknown.

#### Product Lookup by ASIN

You can also fetch detailed product information directly by ASIN using the `-a/--asin` flag:

```text
$ amzsear -a B00006IFHD
```

```text
ASIN:   B00006IFHD
Title:  Sharpie Permanent Markers Set Quick Drying And Fade Resistant Fine ...
Brand:  Sharpie
Rating: 4.8/5 (43,116 reviews)

About this item (7 points):
  1. Fine-tipped, Detailed Marks: Versatile fine tip allows users to make eye-catchin...
  2. Permanent Ink: Makes a resilient mark on paper, plastic, and metal surfaces
  3. Quick-Drying: Quick-drying feature ensures writing resilience against water and ...
  ... and 4 more

Technical details (21 fields)
```

This fetches the product page and extracts detailed information including brand, full title, bullet points, technical specifications, and review statistics. Use `-v` for verbose output or `-j` for JSON format.

Use `-b/--browser` to open the product page in your default browser:

```text
$ amzsear -a B00006IFHD -b
```

For more examples and for extended usage information see the [CLI Readme](docs/cli/README.md).

#### MCP Server

Run the FastMCP Streamable HTTP server with:

```text
$ amzsear-mcp --host 127.0.0.1 --port 8765
```

The MCP endpoint is `http://127.0.0.1:8765/mcp`. It exposes search, product lookup, review
lookup, URL building, region listing, and HTML parsing tools through the official Python MCP
SDK. See the
[MCP README](docs/mcp/README.md) for the full tool list.

#### API

```python
from amzsear import AmzSear
amz = AmzSear('Harry Potter')
```

In the latest version of amzSear dedicated `AmzSear` and `AmzProduct` classes have been created to allow easier extraction of Amazon product information in a Python program. For example:

```python
>>> from amzsear import AmzSear
>>> amz = AmzSear('Harry Potter', page=2, region='CA')
>>> 
>>> last_item = amz.rget(-1) # retrieves the last item in the amzSear
>>> print(last_item)
title               "[Sponsored]Kids' Travel Guide - London: The fun way to discover Lo..."
product_url         'https://www.amazon.com/gp/slredirect/picassoRedirect.html/ref=pa_s...'
image_url           'https://images-na.ssl-images-amazon.com/images/I/61CatLnbhQL._AC_U...'
rating              ratings_text          '4.6 out of 5 stars'
                    ratings_count_text    '29'
                    <Valid AmzRating object>
prices              {'Perfect Paperback': '$8.37', '1': '$10.90'}
extra_attributes    {}
subtext             ['by Sarah-Jane Williams and FlyingKids']
<Valid AmzProduct object>
>>> 
>>> print(last_item.get_prices()) # retrieves all price values as floats
[8.37, 10.9]
```

For a complete explanation of the intricacies of the amzSear core API, see the [API docs](docs/core/).

<a name="whats-new"></a>

### What's New in Version 2.0

| Feature                                                        | v 1.0 | v 2.0 |
| -------------------------------------------------------------- | ----- | ----- |
| Command line Amazon queries                                    | ✓     | ✓     |
| Command line conversion to JSON                                |       | ✓     |
| Product lookup by ASIN with detailed info                      |       | ✓     |
| Support for US Amazon                                          | ✓     | ✓     |
| Support across __all__ Amazon regions                          |       | ✓     |
| Single page API queries                                        | ✓     | ✓     |
| Multiple page API queries                                      |       | ✓     |
| Dedicated AmzSear class & subclasses                           |       | ✓     |
| Extraction of (title, url, prices & rating)                    | ✓     | ✓     |
| Extraction of (image_url, rating's count, extra text, subtext) |       | ✓     |
| Consistent extraction across Amazon sites                      |       | ✓     |
| Support for API input from query or url or html directly       |       | ✓     |

#### Summary

* Support across all Amazon regions (Australia, India, Spain, UK, US, etc.)
* Dedicated AmzSear class & subclasses
* Better scraping & extraction to retrieve all data
* Additional fields - including image_url, subtitle/subtext, rating's count
* Product lookup by ASIN - fetch detailed product info (brand, specs, bullet points, reviews)
* Simpler usability and clearer command line interface
* JSON export format for programmatic use

A more in depth understanding of the latest features of the CLI can be explored in the [CLI Readme](docs/cli/README.md). A complete breakdown of the core API's extended features can be seen in the core [API docs](docs/core/).

### About

#### Articles

* [OSTechNix](https://www.ostechnix.com/search-amazon-products-command-line/)
* [CrackWare](http://crackware.me/technology/search-amazon-products-from-command-line/)
* [Linux-OS.net](http://linux-os.net/amzsear-busca-productos-en-amazon-desde-la-linea-de-comandos/)
* [MasLinux](http://maslinux.es/buscar-productos-de-amazon-desde-la-linea-de-comandos/)

This library was designed to facilitate the use of Amazon search on the command line whilst also providing a utility to easily scrape basic product information from Amazon (for those without access to Amazon's Product API).
