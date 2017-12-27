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
