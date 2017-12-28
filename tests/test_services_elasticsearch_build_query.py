# -*- encoding: utf-8

import datetime as dt
import time

import betamax
from hypothesis import example, given
from hypothesis.strategies import integers, text
import pytest
import requests

import pincushion.services.elasticsearch as es
from pincushion.services.elasticsearch import build_query


with betamax.Betamax.configure() as config:
    config.cassette_library_dir = 'tests/cassettes'


@example('"')
@example("'")
@given(query_string=text())
def test_query_builder_always_returns_a_result(query_string):
    query = build_query(query_string=query_string)
    assert isinstance(query, dict)


@given(page_size=integers(min_value=0))
def test_build_query_respects_page_size(page_size):
    query = build_query(query_string='fish', page_size=page_size)
    assert query['size'] == page_size


@pytest.mark.parametrize('page, page_size, expected_from', [
    (1, 100, 0),
    (2, 100, 100),
    (13, 37, 444),
])
def test_build_query_sets_from_correctly(page, page_size, expected_from):
    query = build_query(query_string='crab', page=page, page_size=page_size)
    assert query['from'] == expected_from


@pytest.mark.parametrize('query_string, expected_sort_time', [
    ('', True),
    ('\t\t\n', True),
    ('octopus', False),
    ('tags:mantaray', True),
    ('tags:oyster tags:lobster', True),
    ('tags:starfish shark', False)
])
def test_build_query_sets_sort_correctly(query_string, expected_sort_time):
    query = build_query(query_string=query_string)
    if expected_sort_time:
        assert query['sort'] == [{'time': 'desc'}]
    else:
        assert 'sort' not in query


@pytest.mark.parametrize('query_string, expected_simple_qs', [
    ('eel', 'eel'),
    ('tags:salmon trout', 'trout'),
    ('whale tags:halibut seabass', 'whale seabass'),
])
def test_build_query_sets_freetext_search_correctly(
    query_string, expected_simple_qs
):
    query = build_query(query_string=query_string)
    assert (
        query['query']['bool']['must']['simple_query_string']['query'] ==
        expected_simple_qs)


@pytest.mark.parametrize('query_string', [
    (''),
    ('tags:krill'),
    ('tags:plankton tags:mollusc'),
])
def test_all_tag_queries_dont_have_free_text_search(query_string):
    query = build_query(query_string=query_string)
    assert 'must' not in query['query']['bool']


@pytest.mark.parametrize('query_string, tags', [
    ('anemone tags:sea-stars', ['sea-stars']),
    ('tags:barnacle barracuda tags:cod', ['barnacle', 'cod']),
    ('tags:squid tags:herring tags:dab', ['squid', 'herring', 'dab']),
])
def test_tag_queries_set_tag_filters(query_string, tags):
    query = build_query(query_string=query_string)
    assert (
        query['query']['bool']['filter']['terms_set']['tags.raw']['terms'] ==
        tags)


@pytest.mark.parametrize('query_string', [
    '',
    '"humpback whale"',
    '"weird interspected tags:string" but with no actual tags',
])
def test_tag_free_queries_dont_get_filters(query_string):
    query = build_query(query_string=query_string)
    assert 'filter' not in query['query']['bool']


@given(query_string=text())
def test_query_always_has_tag_aggregations(query_string):
    query = build_query(query_string=query_string)
    assert 'aggregations' in query
    assert 'tags' in query['aggregations']


@pytest.fixture()
def es_session():
    sess = requests.Session()
    with betamax.Betamax(sess) as vcr:
        vcr.use_cassette('test_elasticsearch_query', record='once')
        es_sess = es.ElasticsearchSession(
            host='http://localhost:9200/', sess=sess
        )
        es_sess.put_mapping(
            index_name='test_bookmarks',
            properties={
                'tags': {
                    'type': 'text',
                    'fields': {
                        'raw': {'type': 'keyword'}
                    }
                }
            }
        )
        yield es_sess


class TestElasticsearchSession:

    def _put_document(self, es_session, id, document):
        if 'time' not in document:
            document['time'] = dt.datetime.now().isoformat()

        es_session.put_document(
            index_name='test_bookmarks',
            document_type='test_bookmarks',
            id=id,
            document=document,
        )

    def test_looking_up_exclamation_tag(self, es_session):
        """
        I can search for documents with "!fic" as a tag.
        """
        self._put_document(
            es_session=es_session,
            id='exclamation_tag',
            document={'tags': ['!fic']}
        )
        self._put_document(
            es_session=es_session,
            id='noexclamation_tag',
            document={'tags': ['fic']}
        )
        time.sleep(1)

        query = es.build_query(query_string='tags:!fic')

        resp = es_session.http_get(
            '/test_bookmarks/test_bookmarks/_search',
            data=query
        )
        assert resp.json()['hits']['total'] == 1

    def test_looking_up_with_colon(self, es_session):
        """
        I can search for documents with "wc:1k-5k" as a tag.
        """
        self._put_document(
            es_session=es_session,
            id='first_fic',
            document={'tags': ['fic', 'wc:1k-5k', 'gen']}
        )
        self._put_document(
            es_session=es_session,
            id='second_fic',
            document={'tags': ['fic', 'wc:1k-5k', 'rpf']}
        )
        self._put_document(
            es_session=es_session,
            id='not_a_fic',
            document={'tags': ['longreads', 'programming']}
        )
        time.sleep(2)

        query = es.build_query(query_string='tags:wc:1k-5k')

        resp = es_session.http_get(
            '/test_bookmarks/test_bookmarks/_search#1',
            data=query
        )
        assert resp.json()['hits']['total'] == 2
