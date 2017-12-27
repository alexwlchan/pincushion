# -*- encoding: utf-8

import json
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

        self.sess.hooks['response'].append(_check_for_error)

        # Because everything we send Elasticsearch uses JSON, we can set the
        # correct Content-Type globally.  ES6 does strict checking here:
        # https://www.elastic.co/blog/strict-content-type-checking-for-elasticsearch-rest-requests
        self.sess.headers.update({'Content-Type': 'application/json'})

    def _http_call(self, meth, url, *args, **kwargs):
        if 'data' in kwargs:
            kwargs['data'] = json.dumps(kwargs['data'])
        return meth(f'{self.host}{url}', *args, **kwargs)

    def http_get(self, url, *args, **kwargs):
        return self._http_call(self.sess.get, url, *args, **kwargs)

    def http_put(self, url, *args, **kwargs):
        return self._http_call(self.sess.put, url, *args, **kwargs)

    def create_index(self, index_name):
        """Create a new index in the Elasticsearch cluster.

        Does not error if the index already exists.

        """
        # We may get an HTTP 400 if the index already exists; in that case
        # we want to suppress the error sent to stderr.
        def _check_if_index_exists(resp, *args, **kwargs):
            try:
                resp.raise_for_status()
            except requests.exceptions.HTTPError:
                error_type = resp.json()['error']['type']
                if error_type == 'resource_already_exists_exception':
                    pass
                else:
                    _check_for_error(resp, *args, **kwargs)

        return self.http_put(
            f'/{index_name}',
            hooks={'response': _check_if_index_exists}
        )

    def put_mapping(self, index_name, properties):
        """Put a mapping into an Elasticsearch index."""
        # Ref: https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-put-mapping.html

        # Elasticsearch gets upset if you try to PUT a mapping into a
        # non-existent index, so let's ensure it exists.
        self.create_index(index_name)

        self.http_put(
            f'/{index_name}/_mapping/{index_name}',
            data={'properties': properties}
        )
