"""
Description     : This module contains helper functions.
Author          : Ori Levi
File Name       : helpers.py
Date            : 05.02.2018
Version         : 0.1
"""

import requests


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
