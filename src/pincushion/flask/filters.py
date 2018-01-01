# -*- encoding: utf-8

import functools
import re

import markdown
from markdown.extensions.smarty import SmartyExtension


def title_markdown(md):
    """Renders a Markdown string as HTML for use in a bookmark title."""
    if len(md.splitlines()) != 1:
        raise ValueError(f"Title must be at most one line; got {md!r}")

    # We don't want titles to render with <h1> or similar tags if they start
    # with a '#', so escape that if necessary.
    if md.startswith('#'):
        md = f'\\{md}'

    res = markdown.markdown(md, extensions=[SmartyExtension()])
    return res.replace('<p>', '').replace('</p>', '')


def cmp(x, y):
    """
    Replacement for built-in function cmp that was removed in Python 3

    Compare the two objects x and y and return an integer according to
    the outcome. The return value is negative if x < y, zero if x == y
    and strictly positive if x > y.
    """
    # Taken from http://portingguide.readthedocs.io/en/latest/comparisons.html
    return (x > y) - (x < y)


WC_TAG_REGEX = re.compile(
    r'^wc:(?:'
    r'(?:<|&lt;)(?P<upper_open>\d+)k'
    r'|'
    r'(?P<lower_closed>\d+)k-\d+k'
    r')$')


def custom_tag_sort(tags):
    """Sorts my tags, but does so in a slightly non-standard way that's
    more pleasing for my use.
    """
    def _comparator(x, y):
        # If we see a word count tag like 'wc:<1k' or 'wc:1k-5k', sort them
        # so they form a neatly ascending set of word counts.
        if x.startswith('wc:') and y.startswith('wc:'):
            match_x = WC_TAG_REGEX.match(x)
            match_y = WC_TAG_REGEX.match(y)
            assert match_x is not None
            assert match_y is not None

            # Here '_interval' is one of 'upper_open' or 'lower_closed', and
            # '_value' is the corresponding integer value.
            x_interval, x_value = list({
                k: int(v)
                for k, v in match_x.groupdict().items()
                if v is not None}.items())[0]
            y_interval, y_value = list({
                k: int(v)
                for k, v in match_y.groupdict().items()
                if v is not None}.items())[0]

            # If they're the same type of interval, it's enough to compare
            # the corresponding values.
            #
            # e.g. X = wc:1k-5k and Y = wc:5k-10k
            if x_interval == y_interval:
                return cmp(x_value, y_value)

            # e.g. X = wc:<1k and Y = wc:1k-5k
            elif x_interval == 'upper_open':
                return cmp(x_value, y_value) or -1

            # e.g. X = 1k-5k and Y = wc:<1k
            elif x_interval == 'lower_closed':
                return cmp(x_value, y_value) or 1

            else:
                assert False  # Unreachable

        return cmp(x, y)

    return sorted(tags, key=functools.cmp_to_key(_comparator))
