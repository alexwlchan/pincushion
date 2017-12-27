# -*- encoding: utf-8

import json

import betamax
import pytest
import requests

from pincushion.services import elasticsearch as es


with betamax.Betamax.configure() as config:
    config.cassette_library_dir = 'tests/cassettes'


@pytest.mark.parametrize('existing_query, new_tag, expected_query', [
    # Adding the tag to a query that doesn't have it
    ('', 'fish', 'tags:fish'),
    ('tags:catfood', 'fish', 'tags:catfood AND tags:fish'),

    # If there's a tag with the same prefix but a different name, we still
    # add a new tag
    ('tags:fishcake', 'fish', 'tags:fishcake AND tags:fish'),
    ('tags:fishcake AND tags:catfood',
     'fish', 'tags:fishcake AND tags:catfood AND tags:fish'),

    # If there's an existing tag anywhere in the query, we do nothing
    ('tags:fish', 'fish', 'tags:fish'),
    ('tags:fish AND tags:catfood', 'fish', 'tags:fish AND tags:catfood'),
    ('tags:catfood AND tags:fish', 'fish', 'tags:catfood AND tags:fish'),
])
def test_add_tag_to_query(existing_query, new_tag, expected_query):
    result = es.add_tag_to_query(
        existing_query=existing_query,
        new_tag=new_tag
    )
    assert result == expected_query


class TestResultList:

    @pytest.mark.parametrize('page_size, page, expected_start_idx', [
        (10, 1, 1),
        (20, 1, 1),
        (10, 2, 11),
        (20, 2, 21),
        (53, 3, 107),
    ])
    def test_start_idx(self, page_size, page, expected_start_idx):
        rlist = es.ResultList(
            total_size=1000,
            page=page,
            page_size=page_size,
            bookmarks=[],
            tags=[]
        )
        assert rlist.start_idx == expected_start_idx

    @pytest.mark.parametrize('page_size, page, expected_end_idx', [
        (10, 1, 10),
        (20, 1, 20),
        (10, 2, 20),
        (20, 2, 40),
        (53, 3, 159),
    ])
    def test_end_idx(self, page_size, page, expected_end_idx):
        rlist = es.ResultList(
            total_size=1000,
            page=page,
            page_size=page_size,
            bookmarks=[],
            tags=[]
        )
        assert rlist.end_idx == expected_end_idx

    @pytest.mark.parametrize('page_size, page, total_size, expected_end_idx', [
        (10, 1, 7, 7),
        (20, 1, 17, 17),
        (10, 2, 14, 14),
        (20, 2, 36, 36),
        (53, 3, 140, 140),
    ])
    def test_end_idx_on_final_page(
        self, page_size, page, total_size, expected_end_idx
    ):
        rlist = es.ResultList(
            total_size=total_size,
            page=page,
            page_size=page_size,
            bookmarks=[],
            tags=[]
        )
        assert rlist.end_idx == expected_end_idx

    @pytest.mark.parametrize('total_size, page_size, expected_total_pages', [
        (100, 10, 10),
        (101, 10, 11),
        (10, 100, 1),
    ])
    def test_total_pages(self, total_size, page_size, expected_total_pages):
        rlist = es.ResultList(
            total_size=total_size,
            page=1,
            page_size=page_size,
            bookmarks=[],
            tags=[]
        )
        assert rlist.total_pages == expected_total_pages


@pytest.fixture()
def es_session():
    sess = requests.Session()
    with betamax.Betamax(sess) as vcr:
        vcr.use_cassette('test_elasticsearch_session', record='new_episodes')
        yield es.ElasticsearchSession(host='http://localhost:9200/', sess=sess)


class TestElasticsearchSession:

    def test_okay_get_is_okay(self, es_session):
        es_session.http_get('/')

    def test_bad_get_is_error(self, es_session):
        with pytest.raises(requests.exceptions.HTTPError):
            es_session.http_get('/doesnotexist')

    def test_bad_get_is_printed_to_stderr(self, es_session, capsys):
        with pytest.raises(requests.exceptions.HTTPError):
            es_session.http_get('/doesnotexist')
        _, err = capsys.readouterr()

        error = json.loads(err)
        assert error['status'] == 404

    def test_creating_index(self, es_session):
        def _list_indices():
            return list(es_session.http_get('/_aliases').json().keys())

        # Check the index created by this test doesn't already exist
        assert 'test_creating_index' not in _list_indices()

        # Then create a new index, and assert it returns a 200 OK
        resp = es_session.create_index('test_creating_index')
        assert resp.status_code == 200

        # Check the index has been created successfully
        assert 'test_creating_index' in _list_indices()

        # Then attempt to create the index again, and check we don't throw
        # any sort of exception
        es_session.create_index('test_creating_index')
