#!/usr/bin/env python
# -*- encoding: utf-8
"""
Grab the metadata saved in S3, and index it into Elasticsearch.

Usage:  run_indexer.py --host=<HOST> --bucket=<BUCKET> [--reindex]
        run_indexer.py -h | --help
"""

import json

import docopt
import requests
import tqdm

from pincushion.services import aws


def prepare_bookmarks(bookmarks):
    """Prepare bookmarks for indexing into Elasticsearch."""
    for b_id, b in bookmarks.items():

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
        b['tags_literal'] = b['tags']

        # This gets converted to a proper boolean
        b['toread'] = (b['toread'] == 'yes')

        yield b_id, b


def index_bookmark(host, dst_index, b_id, bookmark):
    resp = requests.put(
        f'{host}/{dst_index}/{dst_index}/{b_id}',
        data=json.dumps(bookmark),
        headers={'Content-Type': 'application/json'}
    )
    try:
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        from pprint import pprint
        pprint(resp.json())
        raise


def reindex(host, src_index, dst_index):
    payload = {
        'source': {
            'index': src_index,
        },
        'dest': {
            'index': dst_index,
        }
    }
    resp = requests.post(f'{host}/_reindex', data=json.dumps(payload))
    resp.raise_for_status()


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    bucket = args['--bucket']
    es_host = args['--host'].rstrip('/')
    should_reindex = args['--reindex']
    index = 'bookmarks_new' if args['--reindex'] else 'bookmarks'

    bookmarks = aws.read_json_from_s3(bucket=bucket, key='bookmarks.json')

    requests.put(
        f'{es_host}/bookmarks',
        data=json.dumps({
            'mappings': {
                'bookmarks': {
                    'properties': {
                        'tags_literal': {
                            'type': 'string',
                            'index': 'not_analyzed',
                            'include_in_all': False,
                        },
                    }
                }
            }

        })
    )

    print('Indexing into Elasticsearch...')
    iterator = tqdm.tqdm(prepare_bookmarks(bookmarks), total=len(bookmarks))
    for b_id, bookmark in iterator:
        index_bookmark(
            host=es_host,
            dst_index=index,
            b_id=b_id,
            bookmark=bookmark
        )

    if should_reindex:
        reindex(host=es_host, src_index=index, dst_index='bookmarks')
