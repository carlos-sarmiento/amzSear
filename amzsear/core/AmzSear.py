from lxml import html as html_module

from . import FetchError, build_url, fetch_html
from .AmzProduct import AmzProduct
from .consts import DEFAULT_REGION
from .utils import validate_positive_int


class AmzSear:
    """
    The AmzSear object is similar to a Python dict, with each item having a
    unique index (ASIN) to reference each AmzProduct.

    The constructor accepts arguments in a hierarchy - higher level arguments
    override lower level ones:

        (query, [page], [region])
                   |
                 (url)
                   |
                (html)
                   |
            (html_element)
                   |
              (products)

    Args:
        query (str): A search query to look up on Amazon.
        page (int or iterable): The page number(s) of the query (defaults to 1).
        region (str): The Amazon region/country to search (defaults to US).
        url (str or iterable): An Amazon search url (not recommended).
        html (str or iterable): The HTML code from an Amazon search page.
        html_element (lxml element or iterable): The lxml root generated from HTML.
        products (list): A list of AmzProducts.

    Note: All arg types can be an iterable of that type. For example,
    page can be an int, list, or range of ints to be searched.
    """

    def __init__(self, query=None, page=1, region=DEFAULT_REGION, url=None, html=None, html_element=None, products=None):
        def get_iter(it):
            if not hasattr(it, '__iter__') or isinstance(it, str) or hasattr(it, 'cssselect'):
                return [it]
            else:
                return it

        self._products = []
        self._indexes = []
        self._urls = []
        self.fetch_errors = []
        products = None

        if query is not None:
            pages = [validate_positive_int(p, "page") for p in get_iter(page)]
            url = [build_url(query=query, page_num=p, region=region) for p in pages]
            products = self._products_from_urls(url, region)
        elif url is not None:
            products = self._products_from_urls(get_iter(url), region)
        elif html is not None:
            html_element = [html_module.fromstring(h) for h in get_iter(html)]
            products = self._products_from_html_elements(html_element, region)
        elif html_element is not None:
            products = self._products_from_html_elements(get_iter(html_element), region)

        if products is not None:
            self._add_products(get_iter(products))

    def __repr__(self):
        out = []
        max_index_len = max([len(repr(index)) + 2 for index in self._indexes] + [12])
        for index, product in self.items():
            temp_repr = (repr(index) + ':').ljust(max_index_len) + repr(product)
            temp_repr = temp_repr.replace('\n','\n' + max_index_len*' ')

            out.append(temp_repr)
        out.append('<' + self.__class__.__name__ + ' object>')
        return '\n'.join(out)


    def __iter__(self):
        return iter(self._indexes)

    def __len__(self):
        return len(self._products)

    def __getitem__(self, key):
        return self.get(key, default=None, raise_error=True)

    def _set_repr_max_len(self, val):
        """Set the maximum repr width length for all products."""
        for product in self._products:
            if hasattr(product, 'REPR_MAX_LEN'):
                product.REPR_MAX_LEN = val

    def get(self, key, default=None, raise_error=False):
        """
        Get the AmzProduct by ASIN.

        Indexing the AmzSear object is equivalent to calling this method
        with raise_error=True.

        Args:
            key (str): The ASIN of the product in the AmzSear object.
            default: The default value if raise_error=False.
            raise_error (bool): If True, raises KeyError if the key is not found.

        Returns:
            The AmzProduct at the key, otherwise the default value.
        """
        key = str(key)
        if key not in self._indexes:
            if raise_error:
                raise KeyError(f'The key {repr(key)} is not a known index')
            else:
                return default

        return self._products[self._indexes.index(key)]

    def rget(self, key, default=None, raise_error=False):
        """
        Relative get - Gets the nth product by position.

        For example, if indexes are ['ABC', 'DEF', 'GHI', 'JKL'],
        calling rget(1) returns the product at 'DEF', and
        rget(-1) returns the product at 'JKL'.

        Args:
            key (int): The relative index of the desired product.
            default: The default value if raise_error=False.
            raise_error (bool): If True, raises IndexError if out of range.

        Returns:
            The AmzProduct at the relative index, otherwise the default value.
        """
        if raise_error:
            return self._products[key]
        else:
            try:
                return self._products[key]
            except IndexError:
                return default

    def aget(self, key, default=None, raise_error=False):
        """
        All get - Gets attribute values from all products.

        Args:
            key (str or list): A single attribute name or a list of attributes.
            default: The default value if attribute is unavailable.
            raise_error (bool): If True, raises ValueError if attribute not found.

        Returns:
            list: List of tuples containing attribute values in product order.
        """
        single_key = not isinstance(key, list)
        if single_key:
            key = [key]

        data = []
        for i, k in enumerate(key):
            data.append([])
            curr_out = data[i]

            for index, prod in self.items():
                try:
                    curr_out.append(prod.get(k, default=default, raise_error=raise_error))
                except KeyError as exc:
                    raise ValueError(f'The key {repr(k)} is not available at index {repr(index)}') from exc

        if single_key:
            return data[0]
        return list(zip(*data, strict=False))

    def items(self):
        """
        Iterate over (index, product) tuples.

        Returns:
            zip: A generator yielding (ASIN, AmzProduct) tuples.
        """
        return zip(self._indexes, self._products, strict=False)

    def indexes(self):
        """
        Get a list of all indexes (ASINs) in the object.

        Returns:
            list: A list of all the ASIN indexes.
        """
        return list(x for x in self)

    def products(self):
        """
        Get a list of all products in the object.

        Returns:
            list: A list of AmzProduct objects.
        """
        return list(y for x, y in self.items())

    keys = indexes
    values = products

    def to_dataframe(self, recursive=True, flatten=False):
        """
        Convert to a Pandas DataFrame.

        Pandas must be installed for this method to be called.

        Args:
            recursive (bool): See AmzBase.to_dict method.
            flatten (bool): See AmzBase.to_dict method.

        Returns:
            pandas.DataFrame: A dataframe with each product in a row,
                indexed by ASIN.
        """
        from pandas import DataFrame
        return DataFrame(
            [y.to_series(recursive=recursive, flatten=flatten) for x, y in self.items()],
            index=self._indexes
        )

    def _products_from_urls(self, urls, region):
        html_elements = []
        self._urls = []
        for raw_url in urls:
            url = build_url(raw_url, region=region)
            self._urls.append(url)
            try:
                html_elements.append(fetch_html(url))
            except FetchError as exc:
                self.fetch_errors.append({'url': url, 'error': str(exc)})
        return self._products_from_html_elements(html_elements, region)

    def _products_from_html_elements(self, html_elements, region):
        products = []
        for html_el in html_elements:
            page_products = html_el.cssselect('div[data-asin][data-component-type="s-search-result"]')
            page_products = [x for x in page_products if x.cssselect('h2')]
            products.extend(AmzProduct(elem, region=region) for elem in page_products)
        return products

    def _add_products(self, products):
        products = [prod for prod in products if prod.is_valid() and prod._index]
        # Deduplicate by ASIN - keep first occurrence only
        for prod in products:
            if prod._index not in self._indexes:
                self._products.append(prod)
                self._indexes.append(prod._index)
