#!/usr/bin/env python
# -*- encoding: utf-8

import os

import requests


def get_bookmarks_from_pinboard(auth_token):
    """Returns a list of bookmarks from Pinboard."""
    resp = requests.get(
        'https://api.pinboard.in/v1/posts/all',
        params={
            'auth_token': auth_token,
            'format': 'json',
        }
    )
    resp.raise_for_status()
    return resp.json()


def prepare_bookmarks(bookmarks):
    """Prepare bookmarks for indexing into Elasticsearch."""
    for b in bookmarks:

        # These fields are only used by Pinboard internally, and don't
        # need to go to Elasticsearch.
        del b['hash']
        del b['meta']
        del b['shared']

        # These keys get renamed into a more sensible scheme; I think the
        # Pinboard API uses these names for compatibility with the old
        # Delicious stuff, but I don't need that!
        b['title'] = b.pop('description')
        b['description'] = b.pop('extended')
        b['url'] = b.pop('href')

        # Tags are stored as a flat list in Pinboard; turn them into a
        # proper list before we index into Elasticsearch.
        b['tags'] = b['tags'].split()

        yield b


if __name__ == '__main__':
    resp = get_bookmarks_from_pinboard(os.environ['PINBOARD_AUTH_TOKEN'])
    from pprint import pprint
    pprint(list(prepare_bookmarks(resp)))
