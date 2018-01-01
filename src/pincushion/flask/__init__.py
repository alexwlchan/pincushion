# -*- encoding: utf-8

from flask import Flask

from . import filters
from .tagcloud import build_tag_cloud, TagcloudOptions


app = Flask(__name__)

app.jinja_env.filters['css_hash'] = filters.css_hash
app.jinja_env.filters['display_query'] = filters.display_query

from . import views  # noqa


__all__ = [
    'app',
    'build_tag_cloud',
    'TagcloudOptions',
]
