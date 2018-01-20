# -*- encoding: utf-8

import os

import maya

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
    import time
    t = time.time()
    writer = index.writer(limitmb=256)


    last_modified = maya.MayaDT(index.last_modified()).datetime()
    is_empty = index.is_empty()
    print(last_modified)

    doc_ids = []

    for doc in documents:
        doc_ids.append(doc['id'])

        if is_empty or (doc['time'] >= last_modified):
            writer.update_document(**doc)
    writer.commit()
    print(f'Reindexed in {time.time() - t}')

    # And delete old bookmarks!!
    # mergetype=writing.CLEAR?
