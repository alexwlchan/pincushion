# -*- encoding: utf-8

import re

from unidecode import unidecode


def create_id(url):
    # Strip https://, http:// and www. prefixes
    url = re.sub(r'^https?://(www\.)?', '', url)

    # Based on http://www.leancrew.com/all-this/2014/10/asciifying/
    u = re.sub(u'[–—/:;,.]', '-', url)
    a = unidecode(u)
    a = a.lower()
    a = re.sub(r'[^a-z0-9 -]', '', a)
    a = a.replace(' ', '-')
    a = re.sub(r'-+', '-', a)

    return a


def merge(cached_data, new_api_response):
    """Merge data from ``cached_data`` into ``new_api_response``.

    Here ``cached_data`` is a cached set of data held in S3, of the form:

        {<id>: <bookmark_metadata>, ...}

    while ``new_api_response`` is a response from the /posts/all method
    on the Pinboard API, which returns a list of the form:

        [<bookmark_metadata>, ...]

    Because the data in S3 is augmented with extra fields (e.g. about backups),
    this function copies data from ``cached_data`` into the corresponding
    entries on the API response, and returns the result.

    """
    result = {}

    for bookmark in new_api_response:
        existing = cached_data.get(create_id(bookmark['href']), {})
        existing.update(bookmark)
        result[create_id(bookmark['href'])] = existing

    return result
