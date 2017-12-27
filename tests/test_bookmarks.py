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


@pytest.fixture
def api_bookmark():
    return {
        'href': 'https://example.org',
        'description': 'An example website',
        'extended': '<blockquote>Some text from the website</blockquote>\n\nMy comments on the bookmark',
        'meta': '042fe65d1d6b0780164494256f82ab77',
        'hash': '9378f5989fc04b7805795ee292f34981',
        'time': '2017-12-26T10:15:21Z',
        'shared': 'no',
        'toread': 'no',
        'tags': 'my-first-tag another-tag and-a-final-tag'
    }


class TestTransformBookmark:

    @pytest.mark.parametrize('field_name', ['hash', 'meta', 'shared'])
    def test_private_fields_are_deleted(self, api_bookmark, field_name):
        b = bookmarks.transform_pinboard_bookmark(api_bookmark)
        assert field_name not in b

    def test_title_field_is_renamed(self, api_bookmark):
        b = bookmarks.transform_pinboard_bookmark(api_bookmark)
        assert b['title'] == api_bookmark['description']
        assert b['description'] == api_bookmark['extended']
        assert b['url'] == api_bookmark['href']

    def test_tags_is_treated_as_list(self, api_bookmark):
        b = bookmarks.transform_pinboard_bookmark(api_bookmark)
        assert b['tags'] == ['my-first-tag', 'another-tag', 'and-a-final-tag']

    @pytest.mark.parametrize('toread, expected', [
        ('yes', True),
        ('no', False),
    ])
    def test_toread_is_a_boolean(self, api_bookmark, toread, expected):
        api_bookmark['toread'] = toread
        b = bookmarks.transform_pinboard_bookmark(api_bookmark)
        assert b['toread'] == expected
