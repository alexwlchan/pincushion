# -*- encoding: utf-8
"""Create statically generated tag clouds in HTML.

Based on https://github.com/addywaddy/jquery.tagcloud.js, ported to Python.

"""

import attr


@attr.s
class _HexColour:
    red = attr.ib()
    green = attr.ib()
    blue = attr.ib()

    @property
    def ashex(self):
        return '#%02x%02x%02x' % (
            int(self.red), int(self.green), int(self.blue))

    def __add__(self, other):
        assert isinstance(other, _HexColour)
        return _HexColour(
            red=(self.red + other.red),
            green=(self.green + other.green),
            blue=(self.blue + other.blue)
        )

    def __mul__(self, other):
        assert isinstance(other, int)
        return _HexColour(
            red=(self.red * other),
            green=(self.green * other),
            blue=(self.blue * other)
        )


def _hex_colour(c):
    c = c.lstrip('#')
    assert len(c) == 6
    red = int(c[0:2], 16)
    green = int(c[2:4], 16)
    blue = int(c[4:6], 16)
    return _HexColour(red=red, green=green, blue=blue)


def _colour_increment(colr_start, colr_end, weight_range):
    return _HexColour(
        red=(colr_start.red - colr_end.red) / weight_range,
        green=(colr_start.green - colr_end.green) / weight_range,
        blue=(colr_start.blue - colr_end.blue) / weight_range,
    )


@attr.s
class TagcloudOptions:
    size_start = attr.ib()
    size_end = attr.ib()

    colr_start = attr.ib(convert=_hex_colour)
    colr_end = attr.ib(convert=_hex_colour)


@attr.s
class TagcloudEntry:
    size = attr.ib()
    colr = attr.ib()


def build_tag_cloud(counter, options):
    weights = counter.values()
    weight_min = min(weights)
    weight_max = max(weights)

    weight_range = weight_max - weight_min
    if weight_range == 0:
        weight_range = 1

    font_incr = (options.size_end - options.size_start) / weight_range
    colr_incr = _colour_increment(
        options.colr_end, options.colr_start, weight_range=weight_range
    )

    result = {}
    for label, weight in counter.items():
        weighting = weight - weight_min
        font_size = options.size_start + font_incr * weighting
        font_colr = options.colr_start + colr_incr * weighting
        result[label] = TagcloudEntry(size=font_size, colr=font_colr.ashex)

    return result
