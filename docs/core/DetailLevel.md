## Enum Definition

<a name="DetailLevel"></a>

### DetailLevel

`DetailLevel` controls how much network fetching `AmzProduct.fetch_details()`
performs.

| Name    | Value | Requests | Behavior                            |
| ------- | ----- | -------- | ----------------------------------- |
| SEARCH  | 0     | 0        | Keep search-result data only.       |
| BASIC   | 1     | 1        | Fetch product-page details.         |
| REVIEWS | 2     | 2        | Fetch product-page and review data. |

`FULL` is not exposed because Q&A fetching is not implemented.
