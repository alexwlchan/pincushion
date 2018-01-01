# -*- encoding: utf-8

from flask import Flask

from .tagcloud import build_tag_cloud, TagcloudOptions


app = Flask(__name__)


__all__ = [
    'app',
    'build_tag_cloud',
    'TagcloudOptions',
]
