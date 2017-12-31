# -*- encoding: utf-8

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
