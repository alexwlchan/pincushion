# -*- encoding: utf-8

from whoosh.fields import SchemaClass, ID, KEYWORD, DATETIME
from whoosh.filedb.filestore import RamStorage


class BaseSchema(SchemaClass):
    id = ID()
    tags = KEYWORD(stored=True, scorable=True)
    time = DATETIME(stored=True)


def create_index(schema):
    storage = RamStorage()
    return storage.create_index(schema)


def index_documents(index, documents):
    with index.writer() as writer:
        for doc in documents:
            writer.add_document(**doc)

    # And delete old bookmarks!!
