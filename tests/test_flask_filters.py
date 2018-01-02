# -*- encoding: utf-8

from hypothesis import assume, given
from hypothesis.strategies import lists, text
import pytest

from pincushion.flask import filters


@pytest.mark.parametrize('md, expected_html', [
    ('Hello world!', 'Hello world!'),
    ("Isn't it a lovely day?", 'Isn&rsquo;t it a lovely day?'),
    ('#1 reason to use Python', '#1 reason to use Python'),
])
def test_title_markdown(md, expected_html):
    assert filters.title_markdown(md) == expected_html


def test_multiline_title_markdown_is_error():
    with pytest.raises(ValueError):
        filters.title_markdown('This is a\nmulti-line string\nof Markdown')


@pytest.mark.parametrize('tags, expected_sorted_tags', [
    (['rust'], ['rust']),
    (['politics', 'brexit'], ['brexit', 'politics']),

    # Doing the word count tags properly is a key feature of the new sorting
    # system
    (['fic', 'wc:<1k'], ['fic', 'wc:<1k']),
    (['wc:1k-5k', 'gen', 'wc:<1k'], ['gen', 'wc:<1k', 'wc:1k-5k']),
    (['wc:10k-25k', 'wc:<1k', 'wc:1k-5k', 'wc:5k-10k'],
     ['wc:<1k', 'wc:1k-5k', 'wc:5k-10k', 'wc:10k-25k']),

    # And with HTML-encoded &lt; signs...
    (['fic', 'wc:&lt;1k'], ['fic', 'wc:&lt;1k']),
    (['wc:1k-5k', 'gen', 'wc:&lt;1k'], ['gen', 'wc:&lt;1k', 'wc:1k-5k']),
    (['wc:10k-25k', 'wc:&lt;1k', 'wc:1k-5k', 'wc:5k-10k'],
     ['wc:&lt;1k', 'wc:1k-5k', 'wc:5k-10k', 'wc:10k-25k']),
])
def test_custom_tag_sort(tags, expected_sorted_tags):
    assert filters.custom_tag_sort(tags) == expected_sorted_tags


@given(lists(text()))
def test_custom_tag_sort_ignores_non_wc_tags(tags):
    assume(not any(t.startswith('wc:') for t in tags))
    result = filters.custom_tag_sort(tags)
    assert result == sorted(tags)


@pytest.mark.parametrize('query, expected_display_query', [
    ('Hello world', 'Hello world'),
    ('They said "Hello"', 'They said &quot;Hello&quot;'),
    ('A single quote "', 'A single quote &quot;'),
])
def test_display_query(query, expected_display_query):
    assert filters.display_query(query) == expected_display_query
