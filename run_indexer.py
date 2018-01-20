#!/usr/bin/env python
# -*- encoding: utf-8
"""
Synchronise Whoosh with the metadata kept in S3.
"""

import maya
from whoosh.fields import BOOLEAN, TEXT, KEYWORD

from pincushion.constants import S3_BOOKMARKS_KEY, S3_BUCKET
from pincushion.search import BaseSchema, create_index, index_documents
from pincushion.services import aws


class BookmarkSchema(BaseSchema):
    backup = BOOLEAN(stored=True)
    title = TEXT(stored=True)
    description = TEXT(stored=True)
    url = TEXT(stored=True)
    slug = KEYWORD(stored=True)
    starred = BOOLEAN(stored=True)


if __name__ == '__main__':
    print('Fetching bookmark data from S3')
    s3_bookmarks = aws.read_json_from_s3(
        bucket=S3_BUCKET,
        key=S3_BOOKMARKS_KEY
    )

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
