## CLI

The amzSear CLI is the main entry point for using the amzSear package. It is
compatible with the current v3 API. Search results are keyed by ASIN, and the
CLI can also fetch a product directly by ASIN.

The CLI, in its basic form, can be used in the following way:

```text
$ amzsear 'Harry Potter Books'
```

<a name="usage"></a>

### Usage

The extended amzSear usage can be seen by typing `amzsear --help`.

```text
usage: amzsear [-h] [-a ASIN] [-p PAGE] [-s SELECT]
               [-r {AU,AE,BR,CA,CN,DE,ES,FR,IN,IT,JP,MX,NL,SG,UK,US}] [-b]
               [-v] [-j] [-V]
               [query]
```

#### Args

_query_: The query string to search Amazon.

##### Optional Args

_-h, --help_: Display extended help & usage information. _-a ASIN, --asin ASIN_:
Fetch product details by ASIN instead of searching. Cannot be combined with a
query, `--page`, or `--select`. _-p PAGE, --page PAGE_: The positive page number
to be searched (defaults to 1). _-s SELECT, --select SELECT_: Select result by
ASIN or numeric index (0-based position). All-numeric 10-character ASINs are
treated as ASINs, not positions. If no selection is specified, the entire page's
products will be displayed. _-r STR, --region STR_: The amazon country/region
to be searched (defaults to US). Region input is case-insensitive. For a list of
countries to country code see the [region table](../regions.md). _-b,
--browser_: Open result product pages in the default browser. _-v, --verbose_:
Show full product details instead of summary. _-j, --json_: Output in JSON
format. Can be combined with -v for verbose JSON. _-V, --version_: Show version
number and exit.

<a name="examples"></a>

##### Examples

###### Example 1

```text
$ amzsear 'Harry Potter' -p 1

	OR

$ amzsear 'Harry Potter' --page 1
```

In the above example, the first page of results for the query `Harry Potter`
will be displayed. The query `amzsear 'Harry Potter'` would have the same result
as the default page number is 1.

###### Example 2

```text
$ amzsear 'Harry Potter' -s 0

	OR

$ amzsear 'Harry Potter' -s B00728DYLA
```

This example will display the first result (index 0) or the result with ASIN
B00728DYLA. The `-s` flag accepts both numeric index (0-based) and ASIN.

###### Example 3

```text
$ amzsear 'Harry Potter' -r ES

	OR

$ amzsear 'Harry Potter' --region ES
```

Example 3 will display all results for `Harry Potter` from the Spanish Amazon
website.

###### Example 4

```text
$ amzsear 'Harry Potter' -b

	OR

$ amzsear 'Harry Potter' --browser
```

This example will display the search results and open the product pages in the
default browser. By default, the browser is not opened.

###### Example 5

```text
$ amzsear 'Harry Potter' -p 2 -s B00728DYLA -j
```

In this example a JSON object of the result with ASIN B00728DYLA on page 2 is
displayed.

###### Example 6

```text
$ amzsear -a B00006IFHD
```

This example fetches detailed product information directly by ASIN, bypassing
search. Returns brand, title, specs, bullet points, and review statistics.
