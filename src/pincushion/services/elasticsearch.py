# -*- encoding: utf-8

import math

import attr
import requests


def add_tag_to_query(existing_query, new_tag):
    """Given a query in Elasticsearch's query string syntax, add another tag
    to further filter the query.

    https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html

    """
    tag_marker = f'tags:{new_tag}'

    # Look for the tag in the existing query; remember if might be at the end!
    if (
        (tag_marker + ' ' in existing_query) or
        existing_query.endswith(tag_marker)
    ):
        return existing_query

    if existing_query:
        return existing_query + ' AND ' + tag_marker
    else:
        return tag_marker


@attr.s
class ResultList:
    """Represents a set of results from Elasticsearch.

    This stores some information about the results from the query, and
    some convenience methods about records on the query.

    """
    total_size = attr.ib()
    page = attr.ib()
    page_size = attr.ib()
    bookmarks = attr.ib()
    tags = attr.ib()

    @property
    def start_idx(self):
        return 1 + self.page_size * (self.page - 1)

    @property
    def end_idx(self):
        return min(self.total_size, self.page_size * self.page)

    @property
    def total_pages(self):
        return math.ceil(self.total_size / self.page_size)


@attr.s
class ElasticsearchSession:
    """Represents an Elasticsearch session.

    This presents a convenient wrapper around Elasticsearch queries.

    """
    host = attr.ib()
    sess = attr.ib(default=attr.Factory(requests.Session))

    def __attrs_post_init__(self):
        # Strip trailing slashes from the Elasticsearch host for consistency.
        self.host = self.host.rstrip('/')

        def _check_for_error(resp, *args, **kwargs):
            # Elasticsearch requests always return JSON, so if a request
            # returns an error, print the response to console before
            # erroring out.
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError:
                import json
                import sys
                print(
                    json.dumps(resp.json(), indent=2, sort_keys=True),
                    file=sys.stderr)
                raise

        self.sess.hooks['response'].append(_check_for_error)

        # Because everything we send Elasticsearch uses JSON, we can set the
        # correct Content-Type globally.  ES6 does strict checking here:
        # https://www.elastic.co/blog/strict-content-type-checking-for-elasticsearch-rest-requests
        self.sess.headers.update({'Content-Type': 'application/json'})

    def http_get(self, url, *args, **kwargs):
        return self.sess.get(f'{self.host}{url}', *args, **kwargs)

    def http_put(self, url, *args, **kwargs):
        return self.sess.put(f'{self.host}{url}', *args, **kwargs)
