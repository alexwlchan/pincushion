# -*- encoding: utf-8

import math
import os
import time

import attr

from whoosh.fields import SchemaClass, ID, KEYWORD, DATETIME
from whoosh.index import create_in
from whoosh import writing


class BaseSchema(SchemaClass):
    id = ID(unique=True)
    tags = KEYWORD(stored=True)
    time = DATETIME(stored=True, sortable=True)


def create_index(schema):
    """Create a new in-memory index according to the schema."""
    os.makedirs('_index', exist_ok=True)
    return create_in('_index', schema=schema)


def index_documents(index, documents):
    t = time.time()
    writer = index.writer(limitmb=256, multisegment=True)

    for doc in documents:
        writer.add_document(**doc)

    # We expect to receive a complete set of documents every time.
    # This does some bookkeeping to delete any documents which have been
    # removed since the last index.
    writer.commit(mergetype=writing.CLEAR)

    print(f'Reindexed in {time.time() - t}')


def add_tag_to_query(existing_query, new_tag):
    """Given a query string, add another tag to further filter the query."""
    tag_marker = f'tags:{new_tag}'

    # Look for the tag in the existing query; remember if might be at the end!
    if (
        (tag_marker + ' ' in existing_query) or
        existing_query.endswith(tag_marker)
    ):
        return existing_query

    return ' '.join([existing_query, tag_marker]).strip()


@attr.s
class ResultList:
    """Represents a set of results from the search index.

    This stores some information about the results from the query, and
    some convenience methods about records on the query.

    """
    total_size = attr.ib()
    page = attr.ib()
    page_size = attr.ib()
    bookmarks = attr.ib()
    tags = attr.ib()

    @property
    def start_idx(self):
        return 1 + self.page_size * (self.page - 1)

    @property
    def end_idx(self):
        return min(self.total_size, self.page_size * self.page)

    @property
    def total_pages(self):
        return math.ceil(self.total_size / self.page_size)
