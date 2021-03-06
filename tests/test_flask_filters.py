# -*- encoding: utf-8

import textwrap

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


@pytest.mark.parametrize('md, expected_html', [
    ('Hello world', '<p>Hello world</p>'),
    ("Don't panic", '<p>Don&rsquo;t panic</p>'),

    # Auto-detecting URLs
    (
        'https://example.org',
        '<p><a href="https://example.org">https://example.org</a></p>'
    ),
    (
        'https://example.net is secure; better than http://example.com',
        '<p><a href="https://example.net">https://example.net</a> is secure; '
        'better than <a href="http://example.com">http://example.com</a></p>'
    ),

    # Blockquotes get the correct <p> tags inserted.
    (
        '<blockquote>They said something.</blockquote>',
        '''\
        <blockquote>
        <p>They said something.</p>
        </blockquote>'''
    ),
    (
        '> They said another thing.',
        '''\
        <blockquote>
        <p>They said another thing.</p>
        </blockquote>'''
    ),
    (
        '''\
        > First they said X.
        >
        > Then they said Y.''',
        '''\
        <blockquote>
        <p>First they said X.</p>
        <p>Then they said Y.</p>
        </blockquote>'''
    ),
    (
        '''\
        <blockquote>First they said X.

        Then they said Y.</blockquote>''',
        '''\
        <blockquote>
        <p>First they said X.</p>
        <p>Then they said Y.</p>
        </blockquote>'''),
    (
        '''\
        <blockquote>First they said X.

        Then they said Y.</blockquote>

        Then there was a bit of commentary.

        <blockquote>Later they said Z.

        But really they meant A.</blockquote>''',
        '''\
        <blockquote>
        <p>First they said X.</p>
        <p>Then they said Y.</p>
        </blockquote>
        <p>Then there was a bit of commentary.</p>
        <blockquote>
        <p>Later they said Z.</p>
        <p>But really they meant A.</p>
        </blockquote>'''
    ),
    (
        '''\
        <blockquote>
        Customer: Stinking Bishop?
        Shop Owner: No.
        Customer: Do you have any cheese at all?
        </blockquote>''',
        '''\
        <blockquote>
        <p>Customer: Stinking Bishop?<br />
        Shop Owner: No.<br />
        Customer: Do you have any cheese at all?</p>
        </blockquote>'''
    ),
])
def test_description_markdown(md, expected_html):
    md = textwrap.dedent(md)
    expected_html = textwrap.dedent(expected_html)
    assert filters.description_markdown(md) == expected_html


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
