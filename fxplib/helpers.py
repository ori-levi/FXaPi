import requests

from urllib.parse import urlparse


def url_alive(url):
    try:
        result = urlparse(url)
        if all([result.scheme, result.netloc]):
            return requests.head(url).status_code == 200
        return False
    except:
        return False
