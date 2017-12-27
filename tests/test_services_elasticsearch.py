# -*- encoding: utf-8

import pytest

from pincushion.services import elasticsearch as es


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
