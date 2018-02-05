"""
Description     : This module contains helper functions.
Author          : Ori Levi
File Name       : helpers.py
Date            : 05.02.2018
Version         : 0.1
"""

import requests
from urllib.parse import urlsplit, urlunsplit


def url_alive(url):
    """
    Check if url is alive or not
    :type url: str
    :rtype: bool
    """
    try:
        result = requests.get(url)
        result.raise_for_status()
        return result.status_code == 200
    except requests.HTTPError:
        return False


def url_path_join(*parts):
    """Normalize url parts and join them with a slash.
    :rtype: str"""

    def first(sequence, default=''):
        return next((x for x in sequence if x), default)

    schemes, netlocs, paths, queries, fragments = \
        zip(*(urlsplit(part) for part in parts))
    scheme = first(schemes)
    netloc = first(netlocs)
    path = '/'.join(x.strip('/') for x in paths if x)
    query = first(queries)
    fragment = first(fragments)
    return urlunsplit((scheme, netloc, path, query, fragment))


