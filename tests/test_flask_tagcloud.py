# -*- encoding: utf-8

from hypothesis import given
from hypothesis.strategies import dictionaries, integers, text

from pincushion.flask import build_tag_cloud, TagcloudOptions


def counters():
    return dictionaries(keys=text(), values=integers(min_value=1))


def font_size():
    return integers(min_value=1, max_value=200)


def hex_colour():
    return text(alphabet='0123456789abcdef', min_size=6, max_size=6)


def test_empty_weights_are_okay():
    options = TagcloudOptions(
        size_start=9,
        size_end=9,
        colr_start='#ffffff',
        colr_end='#ffffff'
    )

    result = build_tag_cloud(counter={}, options=options)
    assert result == {}


@given(size_start=font_size(), size_end=font_size(), counter=counters())
def test_same_start_end_colour_means_always_same_colour(
    size_start, size_end, counter
):
    options = TagcloudOptions(
        size_start=size_start,
        size_end=size_end,
        colr_start='#ffffff',
        colr_end='#ffffff'
    )

    result = build_tag_cloud(counter=counter, options=options)
    assert all(v.colr == '#ffffff' for v in result.values())

    # A little bit of fudge to account for floating-point drift
    size_min = min([size_start, size_end]) - 0.1
    size_max = max([size_start, size_end]) + 0.1
    assert all(size_min <= v.size <= size_max for v in result.values())


@given(colr_start=hex_colour(), colr_end=hex_colour(), counter=counters())
def test_same_start_end_size_means_always_same_size(
    colr_start, colr_end, counter
):
    options = TagcloudOptions(
        size_start=12,
        size_end=12,
        colr_start=colr_start,
        colr_end=colr_end
    )

    result = build_tag_cloud(counter=counter, options=options)
    assert all(v.size == 12 for v in result.values())
