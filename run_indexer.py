#!/usr/bin/env python
# -*- encoding: utf-8
"""
Grab the metadata saved in S3, and index it into Elasticsearch.

Usage:  run_indexer.py --host=<HOST> --bucket=<BUCKET> [--reindex]
        run_indexer.py -h | --help
"""

import docopt
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError as ElasticsearchRequestError
from elasticsearch.helpers import bulk

from pincushion import bookmarks
from pincushion.services import aws


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    bucket = args['--bucket']
    es_host = args['--host'].rstrip('/')
    should_reindex = args['--reindex']
    index_name = 'bookmarks_new' if args['--reindex'] else 'bookmarks'

    print('Fetching bookmark data from S3')
    s3_bookmarks = aws.read_json_from_s3(bucket=bucket, key='bookmarks.json')

    print('Indexing into Elasticsearch...')
    client = Elasticsearch(hosts=[es_host])

    # We create ``tags`` as a multi-field, so it can be:
    #
    #   * searched/analysed as free text ("text")
    #   * used for aggregations to build tag clouds ("keyword")
    #
    doc_type = 'bookmarks'
    try:
        client.indices.create(
            index=index_name,
            body={
                'mappings': {
                    doc_type: {
                        'properties': {
                            'tags': {
                                'type': 'text',
                                'fields': {
                                    'raw': {'type': 'keyword'}
                                }
                            }
                        }
                    }
                }
            }
        )
    except ElasticsearchRequestError as err:
        if err.info['error']['type'] == 'resource_already_exists_exception':
            pass
        else:
            raise

    def _actions():
        for b_id, b_data in s3_bookmarks.items():
            data = {
                '_op_type': 'index',
                '_index': index_name,
                '_type': 'bookmarks',
                '_id': b_id,
            }
            data.update(bookmarks.transform_pinboard_bookmark(b_data))
            yield data

    resp = bulk(client=client, actions=_actions())

    if resp != (len(s3_bookmarks), []):
        from pprint import pprint
        pprint(resp)
        raise RuntimeError(
            "Errors while indexing documents into Elasticsearch."
        )

    if should_reindex:
        client.reindex(body={
            'source': {'index': index_name},
            'dest': {'index': 'bookmarks'}
        })
        client.indices.delete(index=index_name)
