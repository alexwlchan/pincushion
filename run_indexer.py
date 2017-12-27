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

    # We create ``tags`` as a multi-field, so it can be:
    #
    #   * searched/analysed as free text ("text")
    #   * used for aggregations to build tag clouds ("keyword")
    #
    # It's based on the example in
    # https://www.elastic.co/guide/en/elasticsearch/reference/current/multi-fields.html
    es_sess.put_mapping(
        index_name='bookmarks',
        properties={
            'tags': {
                'type': 'text',
                'fields': {
                    'raw': {'type': 'keyword'}
                }
            }
        }
    )

    print('Indexing into Elasticsearch...')
    for b_id, b_data in tqdm.tqdm(s3_bookmarks.items()):
        es_sess.put_document(
            index_name=index_name,
            id=b_id,
            document=bookmarks.transform_pinboard_bookmark(b_data)
        )

    if should_reindex:
        es_host.reindex(src_index=index_name, dst_index='bookmarks')
