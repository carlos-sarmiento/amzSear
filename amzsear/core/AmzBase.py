from . import requires_valid_data
from .consts import REPR_MAX_LEN_DEFAULT
from .utils import clean_text


class AmzBase:
    """
    The AmzBase class works similarly to the 'dict' class in Python.
    However, keys for the class are predefined in the subclass that
    inherits AmzBase and there is also the potential for validity/invalidity
    to be defined in the object. The keys can also be indexed (as they would
    be for a dict) but can also be accessed as attributes.

    Optional Args:
        Any key value pairs passed to the constructor will be set as
        attributes that can be accessed using an index call or directly
        as an attribute.
    """
    _all_attrs = []  # Subclasses should define their own _all_attrs

    REPR_MAX_LEN = REPR_MAX_LEN_DEFAULT

    def __init__(self, **kws):
        # Initialize instance-level attributes
        self._is_valid = bool(kws)
        # Create instance copy of _all_attrs if subclass defines it as class attr
        if '_all_attrs' not in self.__dict__:
            self._all_attrs = list(self.__class__._all_attrs)
        for k, v in kws.items():
            setattr(self, k, v)
            if k not in self._all_attrs:
                self._all_attrs.append(k)

    def __getitem__(self, key):
        return self.get(key, raise_error=True)

    def __len__(self):
        return sum(1 for _ in self)

    def __bool__(self):
        return self.is_valid()

    def __contains__(self,it):
        return it in self._all_attrs and getattr(self, it, None) is not None and self.is_valid()

    def __iter__(self):
        if not self.is_valid():
            return
        for attr_name in self._all_attrs:
            if getattr(self, attr_name, None) is not None:
                yield attr_name

    def __repr__(self):
        def get_repr():
            out = []

            if len(self) > 0:
                max_k = len(max(list(self), key=lambda x: len(x)))
                str_format = f'{{:{max_k}}}    {{}}'
                for key, value in self.items():
                    #indent newlines (these will usually be for an instance of a class inheriting AmzBase)
                    value = clean_text(repr(value)).replace('\n','\n' + ' '*(max_k + 4)) #length of space
                    out.append(str_format.format(key, value)) 

            #add validity & class to the end
            out.append('<' + ('V' if self else 'Inv') + 'alid ' + self.__class__.__name__ + ' object>') 
            return '\n'.join(out)

        lines = get_repr().split('\n') 
        out_lines = [
            line if len(line) <= self.REPR_MAX_LEN else line[:(self.REPR_MAX_LEN-3)] + '...'
            for line in lines
        ]
        return '\n'.join(out_lines)

    def get(self, key, default=None, raise_error=False):
        """
        Get an element by key if available.

        If the key does not exist an error will be raised if raise_error is True,
        otherwise the default value will be returned.

        Args:
            key (str): The key to be accessed in the AmzBase object.
            default: A default value to return if the key specified does not exist.
            raise_error (bool): True if an error is to be raised, should the key not exist.

        Returns:
            The value of the key or the default value if an error is not raised.
        """
        if key not in self._all_attrs:
            if raise_error:
                raise KeyError(f'The key {repr(key)} is not a known attribute')
            else:
                return default
        if not self.is_valid() or getattr(self, key, None) is None:
            if raise_error:
                raise KeyError(f'The key {repr(key)} is known but has no parsed value')
            return default

        return getattr(self, key)

    @requires_valid_data(default=iter(()))
    def items(self):
        """
        Similar to dict.items, yields tuples of (attribute_name, attribute_value).

        Returns:
            generator: A generator yielding (name, value) tuples.
        """
        for attr_name in self._all_attrs:
            if getattr(self, attr_name, None) is not None:
                yield (attr_name, getattr(self, attr_name))

    @requires_valid_data(default=[])
    def keys(self):
        """
        Similar to dict.keys, returns list of attribute names.

        Returns:
            list: The names of all the attributes in the object.
        """
        return list(x for x in self)

    @requires_valid_data(default=[])
    def values(self):
        """
        Similar to dict.values, returns list of attribute values.

        Returns:
            list: The values of all the attributes in the object.
        """
        return list(y for x, y in self.items())

    def is_valid(self):
        """
        Get the validity of the object, as outlined in each object's constructor.

        Returns:
            bool: True if the object is valid, otherwise False.
        """
        return self._is_valid

    def to_dict(self, recursive=True, flatten=False):
        """
        Convert the object to a dict.

        Optionally recurse into to_dict methods for composite AmzBase objects
        and place these composite elements at the same level when flatten=True.

        Calling dict(cls) will have the same effect as calling
        cls.to_dict(recursive=False, flatten=False).

        Args:
            recursive (bool): If True, any values with a to_dict method will have
                their method called too, otherwise the value will be the object.
            flatten (bool): If True, recursive calls to to_dict will cause values
                to be merged at the top level. Requires recursive=True.

        Returns:
            dict: A dict with attribute names as keys and their values as values.
        """
        d = {}
        if flatten and not recursive:
            raise ValueError('flatten=True requires recursive=True')
        for k, v in self.items():
            if recursive and hasattr(v, 'to_dict'):
                if flatten:
                    for nested_key, nested_value in v.to_dict().items():
                        target_key = nested_key
                        if target_key in d:
                            target_key = f'{k}_{nested_key}'
                        d[target_key] = nested_value
                else:
                    d[k] = v.to_dict()
            else:
                d[k] = v
        return d

    def to_series(self, recursive=True, flatten=False):
        """
        Convert to a Pandas Series.

        Pandas must be installed for this method to be called. Uses the same
        recursive and flattening options as to_dict.

        Args:
            recursive (bool): See to_dict method.
            flatten (bool): See to_dict method.

        Returns:
            pandas.Series: A series with attribute names as keys and their values as values.
        """
        # Only import at this point as amzSear can be used without pandas if desired
        from pandas import Series
        return Series(self.to_dict(recursive=recursive, flatten=flatten))
