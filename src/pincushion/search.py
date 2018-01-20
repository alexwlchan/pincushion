# -*- encoding: utf-8

import os

from whoosh.fields import SchemaClass, ID, KEYWORD, DATETIME
from whoosh.index import create_in


class BaseSchema(SchemaClass):
    id = ID(unique=True)
    tags = KEYWORD(stored=True, scorable=True)
    time = DATETIME(stored=True)


def create_index(schema):
    os.makedirs('_index', exist_ok=True)
    return create_in('_index', schema=schema)


def index_documents(index, documents):
    writer = index.writer()
    for doc in documents:
        writer.add_document(**doc)
    writer.commit()

    # And delete old bookmarks!!
