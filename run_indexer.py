#!/usr/bin/env python
# -*- encoding: utf-8
"""
Grab the metadata saved in S3, and index it into Elasticsearch.

Usage:  run_indexer.py --host=<HOST> --bucket=<BUCKET> [--reindex]
        run_indexer.py -h | --help
"""

import docopt
import tqdm

from pincushion import bookmarks
from pincushion.services import aws, elasticsearch as es


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    bucket = args['--bucket']
    es_host = args['--host'].rstrip('/')
    should_reindex = args['--reindex']
    index_name = 'bookmarks_new' if args['--reindex'] else 'bookmarks'

    s3_bookmarks = aws.read_json_from_s3(bucket=bucket, key='bookmarks.json')

    es_sess = es.ElasticsearchSession(host=es_host)

    # TODO: Would it be worth using the Bulk APIs here?
    print('Indexing into Elasticsearch...')
    import elasticsearch as pyes
    from elasticsearch import helpers
    from elasticsearch.client import IndicesClient

    client = pyes.Elasticsearch(hosts=[es_host])

    # We create ``tags`` as a multi-field, so it can be:
    #
    #   * searched/analysed as free text ("text")
    #   * used for aggregations to build tag clouds ("keyword")
    #
    # It's based on the example in
    # https://www.elastic.co/guide/en/elasticsearch/reference/current/multi-fields.html
    doc_type = 'bookmarks'
    indices_client = IndicesClient(client)
    try:
        indices_client.create(
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
    except pyes.exceptions.RequestError as err:
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


    resp = helpers.bulk(client=client, actions=_actions())

    if resp != (len(s3_bookmarks), []):
        from pprint import pprint
        pprint(resp)
        raise RuntimeError(
            "Errors while indexing documents into Elasticsearch."
        )

    if should_reindex:
        es_host.reindex(src_index=index_name, dst_index='bookmarks')
