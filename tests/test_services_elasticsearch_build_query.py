# -*- encoding: utf-8

from hypothesis import given
from hypothesis.strategies import integers

from pincushion.services.elasticsearch import build_query


@given(page_size=integers(min_value=0))
def test_build_query_respects_page_size(page_size):
    query = build_query(query_string='cheese', page_size=page_size)
    assert query['size'] == page_size
