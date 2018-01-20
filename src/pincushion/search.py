# -*- encoding: utf-8

import os
import time

import maya

from whoosh.fields import SchemaClass, ID, KEYWORD, DATETIME
from whoosh.index import create_in
from whoosh import writing


class BaseSchema(SchemaClass):
    id = ID(unique=True)
    tags = KEYWORD(stored=True, scorable=True)
    time = DATETIME(stored=True)


def create_index(schema):
    os.makedirs('_index', exist_ok=True)
    return create_in('_index', schema=schema)


def index_documents(index, documents):
    t = time.time()
    writer = index.writer(limitmb=128, procs=4, multisegment=True)

    for doc in documents:
        writer.add_document(**doc)

    writer.commit(mergetype=writing.CLEAR)
    print(f'Reindexed in {time.time() - t}')

    # And delete old bookmarks!!
    # mergetype=writing.CLEAR?
