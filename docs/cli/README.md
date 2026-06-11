## CLI

The amzSear CLI is the main entry point for using the amzSear package. It is
similar to the [original version](../../legacy/v1) and backwards has been
maintained where possible. However some features had to be changed consequently
some CLI commands had to be changed, as discussed
[below](#comparison-to-version-1).

The CLI, in it's basic form can still be used in the following way:

```
$ amzsear 'Harry Potter Books'
```

<a name="usage"></a>

### Usage

The extended amzSear usage can be seen by typing `amzsear` without any
additional arguments.

```
usage: amzsear [-h] [-a ASIN] [-p PAGE] [-s SELECT]
               [-r {AU,AE,BR,CA,CN,DE,ES,FR,IN,IT,JP,MX,NL,SG,UK,US}] [-b]
               [-v] [-j]
               [query]
```

#### Args

_query_: The query string to search Amazon.

##### Optional Args

_-h, --help_: Display extended help & usage information. _-a ASIN, --asin ASIN_:
Fetch product details by ASIN instead of searching. _-p NUM, --page NUM_: The
page number to be searched (defaults to 1). _-s SELECT, --select SELECT_: Select
result by ASIN or numeric index (0-based position). If no selection is
specified, the entire page's products will be displayed. _-r STR, --region STR_:
The amazon country/region to be searched (defaults to US). For a list of
countries to country code see the [region table](../regions.md). _-b,
--browser_: Open the product page in the default browser. _-v, --verbose_: Show
full product details instead of summary. _-j, --json_: Output in JSON format.
Can be combined with -v for verbose JSON.

<a name="examples"></a>

##### Examples

###### Example 1

```
$ amzsear 'Harry Potter' -p 1

	OR

$ amzsear 'Harry Potter' --page 1
```

In the above example, the first page of results for the query `Harry Potter`
will be displayed. The query `amzsear 'Harry Potter'` would have the same result
as the default page number is 1.

###### Example 2

```
$ amzsear 'Harry Potter' -s 0

	OR

$ amzsear 'Harry Potter' -s B00728DYLA
```

This example will display the first result (index 0) or the result with ASIN
B00728DYLA. The `-s` flag accepts both numeric index (0-based) and ASIN.

###### Example 3

```
$ amzsear 'Harry Potter' -r ES

	OR
    
$ amzsear 'Harry Potter' --region ES
```

Example 3 will display all results from the `Harry Potter` searching the Spanish
Amazon website.

###### Example 4

```
$ amzsear 'Harry Potter' -b

	OR

$ amzsear 'Harry Potter' --browser
```

This example will display the search results and open the product pages in the
default browser. By default, the browser is not opened.

###### Example 5

```
$ amzsear 'Harry Potter' -p 2 -s B00728DYLA -j
```

In this example a JSON object of the result with ASIN B00728DYLA on page 2 is
displayed.

###### Example 6

```
$ amzsear -a B00006IFHD
```

This example fetches detailed product information directly by ASIN, bypassing
search. Returns brand, title, specs, bullet points, and review statistics.
