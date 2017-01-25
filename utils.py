"""Module to put utility functions and classes.
"""
import time


class SimpleCache(object):
    """Very simple cache object.

    Args:
        size (int): default is CACHE_SIZE=100.
        ttl (int): default is CACHE_TTL=30 (seconsds)
    """
    _cache = {}
    CACHE_SIZE = 100
    CACHE_TTL = 30  # seconds

    def __init__(self, size=CACHE_SIZE, ttl=CACHE_TTL):
        self._cache = {}
        self.size = size
        self.ttl = ttl

    def put(self, key, val):
        """Simple cache put implementation.

        It also save the timestamp for cache expiration.

        Args:
            key (str): object key
            val (obj): object to cache
        """
        if len(self._cache) >= self.size:
            self._cache.pop()
        self._cache[key] = (val, time.time())

    def get(self, key, default=None):
        """Simple cache get
        """
        try:
            val, ots = self._cache[key]
            # expiration - if retrieval time is less than TTL, then
            # return same object, else, return None
            if time.time() - ots < self.ttl:
                return val
            # invalidate object as it has expired
            del self._cache[key]
        except KeyError:
            return None
        return None