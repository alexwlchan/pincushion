# -*- encoding: utf-8

import pytest
from whoosh import fields
from whoosh.query import Every

from pincushion.search import (
    ResultList, add_tag_to_query, create_index, index_documents
)


@pytest.mark.parametrize('existing_query, new_tag, expected_query', [
    # Adding the tag to a query that doesn't have it
    ('', 'fish', 'tags:fish'),
    ('tags:catfood', 'fish', 'tags:catfood tags:fish'),

    # If there's a tag with the same prefix but a different name, we still
    # add a new tag
    ('tags:fishcake', 'fish', 'tags:fishcake tags:fish'),
    ('tags:fishcake tags:catfood',
     'fish', 'tags:fishcake tags:catfood tags:fish'),

    # If there's an existing tag anywhere in the query, we do nothing
    ('tags:fish', 'fish', 'tags:fish'),
    ('tags:fish tags:catfood', 'fish', 'tags:fish tags:catfood'),
    ('tags:catfood tags:fish', 'fish', 'tags:catfood tags:fish'),
])
def test_add_tag_to_query(existing_query, new_tag, expected_query):
    result = add_tag_to_query(
        existing_query=existing_query,
        new_tag=new_tag
    )
    assert result == expected_query


def test_can_create_index_and_store_documents():
    schema = fields.Schema(id=fields.STORED, text=fields.TEXT)
    index = create_index(schema=schema)

    documents = [
        {'id': 'A', 'text': 'An appelation of antelope'},
        {'id': 'B', 'text': 'Broadcasting before beavers'},
        {'id': 'C', 'text': 'Calling cats in caves'},
    ]

    index_documents(index=index, documents=documents)

    with index.searcher() as searcher:
        r = searcher.search(Every())
        assert len(r) == 3


class TestResultList:

    @pytest.mark.parametrize('page_size, page, expected_start_idx', [
        (10, 1, 1),
        (20, 1, 1),
        (10, 2, 11),
        (20, 2, 21),
        (53, 3, 107),
    ])
    def test_start_idx(self, page_size, page, expected_start_idx):
        rlist = ResultList(
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
        rlist = ResultList(
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
        rlist = ResultList(
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
        rlist = ResultList(
            total_size=total_size,
            page=1,
            page_size=page_size,
            bookmarks=[],
            tags=[]
        )
        assert rlist.total_pages == expected_total_pages
