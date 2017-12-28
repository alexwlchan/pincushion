#!/usr/bin/env python
# -*- encoding: utf-8
"""
Grab the metadata saved in S3, and index it into Elasticsearch.

Usage:  run_indexer.py [--reindex]
        run_indexer.py -h | --help
"""

import random
import string

import docopt
from elasticsearch.exceptions import RequestError as ElasticsearchRequestError
from elasticsearch.helpers import bulk

from pincushion import bookmarks
from pincushion.constants import (
    DOC_TYPE, ES_CLIENT, INDEX_NAME, S3_BOOKMARKS_KEY, S3_BUCKET
)
from pincushion.services import aws


if __name__ == '__main__':
    args = docopt.docopt(__doc__)
    should_reindex = args['--reindex']

    if should_reindex:
        index = 'bookmarks_' + ''.join(
            random.choice(string.ascii_lowercase) for _ in range(5))
    else:
        index = INDEX_NAME

    print('Fetching bookmark data from S3')
    s3_bookmarks = aws.read_json_from_s3(
        bucket=S3_BUCKET,
        key=S3_BOOKMARKS_KEY
    )

    print('Indexing into Elasticsearch...')

    # We create ``tags`` as a multi-field, so it can be:
    #
    #   * searched/analysed as free text ("text")
    #   * used for aggregations to build tag clouds ("keyword")
    #
    try:
        ES_CLIENT.indices.create(
            index=index,
            body={
                'mappings': {
                    DOC_TYPE: {
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
                '_index': index,
                '_type': DOC_TYPE,
                '_id': b_id,
            }
            data.update(bookmarks.transform_pinboard_bookmark(b_data))
            yield data

    resp = bulk(client=ES_CLIENT, actions=_actions())

    if resp != (len(s3_bookmarks), []):
        from pprint import pprint
        pprint(resp)
        raise RuntimeError(
            "Errors while indexing documents into Elasticsearch."
        )

    if should_reindex:
        ES_CLIENT.reindex(body={
            'source': {'index': index},
            'dest': {'index': INDEX_NAME}
        })
        ES_CLIENT.indices.delete(index=index)
