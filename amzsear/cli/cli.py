import argparse
import json
import sys
import webbrowser

try:
    from amzsear import AmzSear, AmzProduct, DetailLevel, __version__
    from amzsear.core.consts import DEFAULT_REGION, REGION_CODES, PRODUCT_URL
    from amzsear.core import build_base_url, FetchError
except ImportError:
    from .. import AmzSear, AmzProduct, DetailLevel, __version__
    from ..core.consts import DEFAULT_REGION, REGION_CODES, PRODUCT_URL
    from ..core import build_base_url, FetchError


def run(*passed_args):
    """Main entry point for the CLI."""
    parser = get_parser()
    args = parser.parse_args(*passed_args)  # the parser defaults to sys args if nothing passed
    args = vars(args)

    try:
        # Handle product lookup mode
        if args.get('asin'):
            run_product(args)
            return

        # Validate: query is required for search mode
        if not args.get('query'):
            parser.error('query is required (or use --asin ASIN)')

        # Handle search mode
        amz_args = {x: y for x, y in args.items() if x not in ['select', 'verbose', 'json', 'browser', 'asin']}
        out = AmzSear(**amz_args)

        if args['select'] is not None:
            # single item selection - accept ASIN or numeric index
            item_key = args['select']
            if item_key.isdigit():
                # Numeric index - get by position
                prod = out.rget(int(item_key), raise_error=True)
            else:
                # ASIN - get by key
                prod = out[item_key]
            out = AmzSear(products=[prod])
            out._urls = [prod.product_url]

        # handle output
        if args['json']:
            print_json(out, verbose=args['verbose'])
        elif args['verbose']:
            print_verbose(out)
        else:
            print_short(out)

        if args['browser']:
            for url in out._urls:
                webbrowser.open(url)

    except FetchError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyError as e:
        print(f"Error: Key not found - {e}", file=sys.stderr)
        sys.exit(1)
    except IndexError as e:
        print(f"Error: Index out of range - {e}", file=sys.stderr)
        sys.exit(1)


def run_product(args):
    """Handle product lookup by ASIN."""
    asin = args['asin']
    region = args.get('region', DEFAULT_REGION)

    # Create a minimal AmzProduct with just the product_url set
    product = AmzProduct()
    base_url = build_base_url(region)
    product.product_url = PRODUCT_URL % (base_url, asin)
    product._region = region
    product._is_valid = True

    # Fetch BASIC level details
    product.fetch_details(level=DetailLevel.BASIC, region=region)

    # Handle output
    if args['json']:
        print_product_json(product, verbose=args['verbose'])
    elif args['verbose']:
        print_product_verbose(product)
    else:
        print_product_short(product)

    if args['browser']:
        webbrowser.open(product.product_url)



def get_parser():
    """Create and return the argument parser."""
    parser = argparse.ArgumentParser(description='The unofficial Amazon search CLI')

    parser.add_argument('query', type=str, nargs='?', default=None,
        help='The query string to be searched')
    parser.add_argument('-a', '--asin', type=str, default=None,
        help='Fetch product details by ASIN instead of searching')
    parser.add_argument('-p', '--page', type=int,
        help='The page number to be searched (defaults to 1)', default=1)
    parser.add_argument('-s', '--select', type=str,
        help='Select result by ASIN or numeric index (0-based position)', default=None)
    parser.add_argument('-r', '--region', type=str, choices=REGION_CODES,
        default=DEFAULT_REGION, help='The amazon country/region to be searched')

    parser.add_argument('-b', '--browser', action='store_true',
        help='Open the product page in the default browser')

    parser.add_argument('-v', '--verbose', action='store_true',
        help='Show full product details instead of summary')
    parser.add_argument('-j', '--json', action='store_true',
        help='Output in JSON format')

    parser.add_argument('-V', '--version', action='version',
        version=f'amzsear {__version__}',
        help='Show version number and exit')

    return parser


def print_json(cls, verbose=False):
    """Print JSON output. Verbose includes all fields, short includes summary only."""
    if verbose:
        print(json.dumps({k: v.to_dict() for k,v in cls.items()}, indent=2))
    else:
        # Short JSON - just essential fields
        data = {}
        for asin, product in cls.items():
            data[asin] = {
                'title': product.get('title'),
                'prices': product.get('prices'),
                'rating': product.rating.to_dict() if product.rating else None,
                'availability': product.get('availability'),
                'is_available': product.get('is_available'),
                'product_url': product.product_url
            }
        print(json.dumps(data, indent=2))

def print_verbose(cls):
    """Print full verbose output without truncation."""
    for asin, product in cls.items():
        print(f"ASIN: {asin}")
        for key, value in product.items():
            if hasattr(value, 'items'):
                # Nested object (like rating) - print its attributes
                print(f"    {key}:")
                for sub_key, sub_value in value.items():
                    print(f"        {sub_key}: {sub_value}")
            elif isinstance(value, dict):
                print(f"    {key}:")
                for dict_key, dict_value in value.items():
                    print(f"        {dict_key}: {dict_value}")
            elif isinstance(value, list):
                print(f"    {key}:")
                for item in value:
                    print(f"        - {item}")
            else:
                print(f"    {key}: {value}")
        print()


def print_short(cls):
    fields = ['ASIN','Title','Prices','Rating','Available']

    rows = [{f:f for f in fields}]
    for index, product in cls.items():
        temp_dict = {}

        temp_dict['ASIN'] = product.get_asin() or index[:10]

        # get price in format '$nn.nn-$mm.mm'
        price_tup = {product.prices[k]:product.get_prices(k) for k in product.prices}
        if len(price_tup) > 0:
            price_tup = (min(price_tup, key=lambda x: price_tup[x]), max(price_tup, key=lambda x: price_tup[x]))
            if price_tup[0] == price_tup[-1]:
                temp_dict['Prices'] = price_tup[0] # one price
            else:
                temp_dict['Prices'] = price_tup[0] + ' - ' + price_tup[-1] # range of prices
        else:
            temp_dict['Prices'] = '------------'
        temp_dict['Title'] = product.get('title','----------')[:50] # limit title length
    
        temp_dict['Rating'] = product.get('rating','-----')
        if temp_dict['Rating'] != '-----':
            temp_dict['Rating'] = temp_dict['Rating'].get_star_repr()

        temp_dict['Available'] = format_availability(product)

        rows.append(temp_dict)

    format_str = []
    for field in fields:
        #get longest in each field into format_str
        format_str.append('{:%d}' % (max(len(x[field]) for x in rows)+ 1))
    format_str = ' '.join(format_str)

    for row in rows:
        print(format_str.format(*[row.get(x,'') for x in fields])) # print in order


def format_availability(product):
    """Format best-effort availability for compact CLI output."""
    is_available = product.get('is_available', default=None)
    if is_available is True:
        return 'Yes'
    if is_available is False:
        return 'No'
    return 'Unknown'


# Product output formatters
def print_product_json(product, verbose=False):
    """Output product details as JSON."""
    data = {'asin': product.get_asin(), 'product_url': product.product_url}

    if product._fetch_error:
        data['error'] = product._fetch_error
    elif product.details:
        if verbose:
            data['details'] = product.details.to_dict()
        else:
            # Short - just essential fields
            details = product.details
            data['title'] = details.full_title
            data['brand'] = details.brand
            data['rating'] = details.average_rating
            data['review_count'] = details.review_count

    print(json.dumps(data, indent=2))


def print_product_verbose(product):
    """Output full product details without truncation."""
    print(f"ASIN: {product.get_asin()}")
    print(f"URL: {product.product_url}")
    print()

    if product._fetch_error:
        print(f"Error: {product._fetch_error}")
    elif product.details:
        details = product.details
        for key, value in details.items():
            if isinstance(value, dict):
                print(f"{key}:")
                for dict_key, dict_value in value.items():
                    print(f"    {dict_key}: {dict_value}")
            elif isinstance(value, list):
                print(f"{key}:")
                for item in value:
                    print(f"    - {item}")
            else:
                print(f"{key}: {value}")
    else:
        print("No details available")


def print_product_short(product):
    """Output product summary."""
    asin = product.get_asin() or 'N/A'
    details = product.details

    print(f"ASIN:   {asin}")

    if product._fetch_error:
        print(f"Error: {product._fetch_error}")
        return

    if details:
        title = details.full_title or 'N/A'
        if len(title) > 70:
            title = title[:67] + '...'
        print(f"Title:  {title}")

        brand = details.brand or 'N/A'
        print(f"Brand:  {brand}")

        if details.average_rating:
            rating_str = f"{details.average_rating:.1f}/5"
            if details.review_count:
                rating_str += f" ({details.review_count:,} reviews)"
            print(f"Rating: {rating_str}")

        if details.about_items:
            print(f"\nAbout this item ({len(details.about_items)} points):")
            for i, item in enumerate(details.about_items[:3], 1):
                text = item[:80] + '...' if len(item) > 80 else item
                print(f"  {i}. {text}")
            if len(details.about_items) > 3:
                print(f"  ... and {len(details.about_items) - 3} more")

        if details.technical_details:
            print(f"\nTechnical details ({len(details.technical_details)} fields)")
    else:
        print("No details available (fetch may have failed)")


if __name__ == '__main__':
    run()
