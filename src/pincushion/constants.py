# -*- encoding: utf-8

import os

from elasticsearch import Elasticsearch


S3_BUCKET = 'alexwlchan-pincushion'
S3_BOOKMARKS_KEY = 'bookmarks.json'

INDEX_NAME = 'bookmarks'
DOC_TYPE = 'bookmarks'

ES_HOST = (
    os.environ.get('ELASTICSEARCH_HOST', 'http://localhost:9200/').rstrip('/'))
ES_CLIENT = Elasticsearch(hosts=[ES_HOST])
