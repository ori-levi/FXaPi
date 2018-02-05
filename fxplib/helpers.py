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
