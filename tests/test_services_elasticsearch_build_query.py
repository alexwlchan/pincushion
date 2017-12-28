# -*- encoding: utf-8

from hypothesis import given
from hypothesis.strategies import integers

from pincushion.services.elasticsearch import build_query


@given(size=integers(min_value=0))
def test_build_query_respects_size(size):
    query = build_query(query_string='cheese', size=size)
    assert query['size'] == size
