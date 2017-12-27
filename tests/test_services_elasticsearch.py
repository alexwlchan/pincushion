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
