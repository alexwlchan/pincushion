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
