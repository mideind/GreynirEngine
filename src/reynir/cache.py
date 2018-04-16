"""

	cache.py

    Cache utility classes

    The LRU_Cache and LFU_Cache classes herein are
	copyright (c) 2011 by Raymond Hettinger

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

from heapq import nsmallest
from operator import itemgetter
import threading
from functools import wraps


LRU_DEFAULT = 1024
LFU_DEFAULT = 512


class LRU_Cache:

    def __init__(self, user_function, maxsize = LRU_DEFAULT):
        # Link layout:     [PREV, NEXT, KEY, RESULT]
        self.root = root = [None, None, None, None]
        self.user_function = user_function
        self.cache = cache = {}

        last = root
        for i in range(maxsize):
            key = object()
            cache[key] = last[1] = last = [last, root, key, None]
        root[0] = last

    def __call__(self, *key):
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
        root[3], oldvalue = None, root[3]
        del cache[oldkey]
        cache[key] = oldroot
        return result


class LFU_Cache:

    """ Least-frequently-used (LFU) cache for word lookups.
        Based on a pattern by Raymond Hettinger
    """

    class Counter(dict):
        """ Mapping where default values are zero """
        def __missing__(self, key):
            return 0

    def __init__(self, maxsize = LFU_DEFAULT):
        self.cache = {}                     # Mapping of keys to results
        self.use_count = self.Counter()     # Times each key has been accessed
        self.maxsize = maxsize
        self.hits = self.misses = 0
        self.lock = threading.Lock()        # The cache may be accessed in parallel by multiple threads

    def lookup(self, key, func):
        """ Lookup a key in the cache, calling func(key) to obtain the data if not already there """
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
                    for key, _ in nsmallest(self.maxsize // 10,
                        self.use_count.items(), key = itemgetter(1)):

                        del self.cache[key], self.use_count[key]

            return result


def cached(func):
    """ A decorator for caching function calls """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not hasattr(func, "_cache"):
            func._cache = func(*args, **kwargs)
        return func._cache
    return wrapper


class cached_property:

    """ A decorator for caching instance properties """

    def __init__(self, func):
        self.__doc__ = getattr(func, "__doc__")
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        # Get the property value and put it into the instance's
        # dict instead of the original function
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value

