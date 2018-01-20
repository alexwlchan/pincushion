#!/usr/bin/env python
# -*- encoding: utf-8
"""
Synchronise Elasticsearch with the metadata kept in S3.
"""

from elasticsearch.exceptions import RequestError as ElasticsearchRequestError
from elasticsearch.helpers import bulk
import maya

from pincushion import bookmarks
from pincushion.constants import (
    DOC_TYPE, ES_CLIENT, INDEX_NAME, S3_BOOKMARKS_KEY, S3_BUCKET
)
from pincushion.search import BaseSchema, create_index, index_documents
from pincushion.services import aws


from whoosh.fields import SchemaClass, BOOLEAN, TEXT, KEYWORD


class BookmarkSchema(BaseSchema):
    backup = BOOLEAN(stored=True)
    title = TEXT(stored=True)
    description = TEXT(stored=True)
    url = TEXT(stored=True)
    slug = KEYWORD(stored=True)
    starred = BOOLEAN(stored=True)



if __name__ == '__main__':
    print('Fetching bookmark data from S3')
    # s3_bookmarks = aws.read_json_from_s3(
#         bucket=S3_BUCKET,
#         key=S3_BOOKMARKS_KEY
#     )
    import json
    s3_bookmarks = json.load(open('/Users/alexwlchan/bookmarks.json'))

    print('Indexing into Whoosh...')
    index = create_index(schema=BookmarkSchema())

    def documents():
        for b_id, b_data in s3_bookmarks.items():
            yield {
                'id': b_id,
                'backup': b_data.get('_backup', False),
                'title': b_data['description'],
                'description': b_data['extended'],
                'url': b_data['href'],
                'slug': b_data['slug'],
                'starred': b_data['starred'],
                'tags': b_data['tags'],
                'time': maya.parse(b_data['time']).datetime(),
            }

    index_documents(index=index, documents=documents())
