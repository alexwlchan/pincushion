# -*- encoding: utf-8

from hypothesis import given
from hypothesis.strategies import text
import pytest

from pincushion import bookmarks


@pytest.mark.parametrize('url, expected_id', [
    # Leading http://, https:// and www. are all stripped
    ('https://example', 'example'),
    ('http://example', 'example'),
    ('https://www.example', 'example'),
    ('http://www.example', 'example'),

    # Special characters all become dashes
    ('example/foo', 'example-foo'),

    # Characters are coerced to their ASCII equivalents
    ('exámplë', 'example'),

    # Strings are lowercased
    ('ExAmPlE', 'example'),

    # Any non-alphanumerics that are unrecognised special characters
    # are removed
    ('ex@mple', 'exmple'),

    # Spaces become dashes
    ('example foo bar baz', 'example-foo-bar-baz'),

    # Multiple dashes are collapsed
    ('example//foo//bar', 'example-foo-bar'),
])
def test_create_id(url, expected_id):
    assert bookmarks.create_id(url) == expected_id


@given(text())
def test_ids_are_idempotent(url):
    result = bookmarks.create_id(url)
    assert result == bookmarks.create_id(result)


@pytest.mark.parametrize('cached_data, api_response, expected', [
    # Nothing in the new response means the old data is discarded
    ({'example': {}}, [], {}),

    # Nothing in the old data means the new response shines through
    ({},
     [
         {'href': 'example', 'eg': 'example'},
         {'href': 'foo', 'foo': 'bar'}],
     {
         'example': {'href': 'example', 'eg': 'example'},
         'foo': {'href': 'foo', 'foo': 'bar'}}),

    # Fields from the old data are carried across correctly
    (
        {'example': {'_backup': True, 'foo': 'bar'}},
        [{'href': 'example', 'foo': 'NEWFOO'}],
        {'example': {'_backup': True, 'href': 'example', 'foo': 'NEWFOO'}}
    ),
])
def test_merging_bookmarks(cached_data, api_response, expected):
    result = bookmarks.merge(
        cached_data=cached_data,
        new_api_response=api_response
    )
    assert result == expected
