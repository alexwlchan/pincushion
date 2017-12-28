# -*- encoding: utf-8

from hypothesis import given
from hypothesis.strategies import integers
import pytest

from pincushion.services.elasticsearch import build_query


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
