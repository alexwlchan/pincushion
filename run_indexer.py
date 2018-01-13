#!/usr/bin/env python
# -*- encoding: utf-8
"""
Synchronise Elasticsearch with the metadata kept in S3.
"""

from elasticsearch.exceptions import RequestError as ElasticsearchRequestError
from elasticsearch.helpers import bulk

from pincushion import bookmarks
from pincushion.constants import (
    DOC_TYPE, ES_CLIENT, INDEX_NAME, S3_BOOKMARKS_KEY, S3_BUCKET
)
from pincushion.services import aws


if __name__ == '__main__':
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
            index=INDEX_NAME,
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
                '_index': INDEX_NAME,
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

    print('Cleaning up deleted bookmarks...')
    indexed = ES_CLIENT.search(
        index=INDEX_NAME, _source=False, size=10000
    )
    hits = indexed['hits']['hits']
    indexed_ids = [h['_id'] for h in hits]

    delete_actions = []
    for i in indexed_ids:
        if i not in s3_bookmarks:
            delete_actions.append({
                '_op_type': 'delete',
                '_index': INDEX_NAME,
                '_type': DOC_TYPE,
                '_id': i,
            })

    if delete_actions:
        resp = bulk(client=ES_CLIENT, actions=delete_actions)

        if resp != (len(delete_actions), []):
            from pprint import pprint
            pprint(resp)
            raise RuntimeError(
                "Errors while deleting documents from Elasticsearch."
            )
