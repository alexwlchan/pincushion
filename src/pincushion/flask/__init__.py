# -*- encoding: utf-8

from flask import Flask

from pincushion.flask import filters
from pincushion.flask.tagcloud import build_tag_cloud, TagcloudOptions
from pincushion.services import elasticsearch


app = Flask(__name__)

app.jinja_env.filters['css_hash'] = filters.css_hash
app.jinja_env.filters['custom_tag_sort'] = filters.custom_tag_sort
app.jinja_env.filters['display_query'] = filters.display_query
app.jinja_env.filters['title_markdown'] = filters.title_markdown

app.jinja_env.filters['add_tag_to_query'] = elasticsearch.add_tag_to_query

options = TagcloudOptions(
    size_start=9, size_end=24, colr_start='#999999', colr_end='#bd450b'
)

app.jinja_env.filters['build_tag_cloud'] = lambda t: build_tag_cloud(
    t, options
)

from . import views  # noqa


__all__ = ['app']
