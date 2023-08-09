"""

	cache.py

    Cache utility classes

    The LRU_Cache and LFU_Cache classes herein are
	copyright © 2011 by Raymond Hettinger

    cf. http://code.activestate.com/recipes/577970-simplified-lru-cache/
        http://code.activestate.com/recipes/498245-lru-and-lfu-cache-decorators/

    MIT license:

    Permission is hereby granted, free of charge, to any person obtaining a copy of
    this software and associated documentation files (the "Software"), to deal in
    the Software without restriction, including without limitation the rights to use,
    copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
    Software, and to permit persons to whom the Software is furnished to do so,
    subject to the following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
    THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
    IN THE SOFTWARE.

    ---

    The classes have been modified from their original versions,
    which are available from the URLs given above.

"""

from typing import List, Dict, Any, Callable, TypeVar, Generic, cast

from heapq import nsmallest
from operator import itemgetter
import threading
from functools import wraps


LRU_DEFAULT = 1024
LFU_DEFAULT = 512


_K = TypeVar("_K")
_V = TypeVar("_V")


class LRU_Cache(Generic[_V]):
    def __init__(
        self, user_function: Callable[..., _V], maxsize: int = LRU_DEFAULT
    ) -> None:
        # Link layout:     [PREV, NEXT, KEY, RESULT]
        root: List[Any] = [None, None, None, None]
        self.root = root
        self.user_function = user_function
        cache: Dict[Any, List[Any]] = {}
        self.cache = cache

        last = root
        for _ in range(maxsize):
            key = object()
            cache[key] = last[1] = last = [last, root, key, None]
        root[0] = last

    def __call__(self, *key: Any) -> _V:
        cache = self.cache
        root = self.root
        link = cache.get(key)
        if link is not None:
            link_prev, link_next, _, result = link
            link_prev[1] = link_next
            link_next[0] = link_prev
            last = root[0]
            last[1] = root[0] = link
            link[0] = last
            link[1] = root
            return result
        result = self.user_function(*key)
        root[2] = key
        root[3] = result
        oldroot = root
        root = self.root = root[1]
        root[2], oldkey = None, root[2]
        root[3] = None
        del cache[oldkey]
        cache[key] = oldroot
        return result


class Counter(Dict[_K, int], Generic[_K]):
    """Mapping where default values are zero"""

    def __missing__(self, key: _K) -> int:
        return 0


class LFU_Cache(Generic[_K, _V]):

    """Least-frequently-used (LFU) cache for word lookups.
    Based on a pattern by Raymond Hettinger
    """

    def __init__(self, maxsize: int = LFU_DEFAULT) -> None:
        # Mapping of keys to results
        self.cache: Dict[_K, _V] = {}
        # Times each key has been accessed
        self.use_count: Counter[_K] = Counter()
        self.maxsize = maxsize
        self.hits = self.misses = 0
        # The cache may be accessed in parallel by multiple threads
        self.lock = threading.Lock()

    def lookup(self, key: _K, func: Callable[[_K], _V]) -> _V:
        """Lookup a key in the cache, calling func(key)
        to obtain the data if not already there"""
        with self.lock:
            self.use_count[key] += 1
            # Get cache entry or compute if not found
            try:
                result = self.cache[key]
                self.hits += 1
            except KeyError:
                result = func(key)
                self.cache[key] = result
                self.misses += 1

                # Purge the 10% least frequently used cache entries
                if len(self.cache) > self.maxsize:
                    for key, _ in nsmallest(
                        self.maxsize // 10, self.use_count.items(), key=itemgetter(1)
                    ):

                        del self.cache[key], self.use_count[key]

            return result


# Define a type variable to allow MyPy to infer the relationship
# between intermediate types in cached and cached_property
_T = TypeVar("_T")

# Define a unique singleton for use as a sentinel
_NA = object()


def cached(func: Callable[..., _T]) -> Callable[..., _T]:
    """A decorator for caching function calls"""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> _T:
        val = cast(_T, getattr(func, "_cache", _NA))
        if val is _NA:
            val = func(*args, **kwargs)
            setattr(func, "_cache", val)
        return val

    return wrapper


class cached_property(Generic[_T]):

    """A decorator for caching instance properties"""

    def __init__(self, func: Callable[..., _T]) -> None:
        self.__doc__ = getattr(func, "__doc__")
        self.func = func

    def __get__(self, obj: Any, cls: Any) -> _T:
        if obj is None:
            return cast(_T, self)  # Hack to satisfy mypy/Pylance
        # Get the property value and put it into the instance's
        # dict instead of the original function
        val = obj.__dict__[self.func.__name__] = self.func(obj)
        return val
