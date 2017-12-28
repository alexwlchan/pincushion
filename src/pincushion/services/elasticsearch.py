# -*- encoding: utf-8

import json
import math
import shlex

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

    return ' '.join([existing_query, tag_marker]).strip()


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


def build_query(query_string, page=1, page_size=96):
    """Returns a dict suitable for passing to Elasticsearch."""
    # These parameters can be set irrespective of the query string.
    # Note: 'from' is an offset parameter, and is 0-indexed.
    query = {
        'from': (page - 1) * page_size,
        'size': page_size,
    }

    def _is_tag(token):
        return token.startswith('tags:')

    query_string = query_string.strip()

    # Attempt to split the query string into tokens, but don't try too hard.
    # If it fails, we shouldn't error here --- better for it to error when it
    # hits Elasticsearch, if at all.
    try:
        tokens = shlex.split(query_string)
    except ValueError:
        tokens = [query_string]

    if not query_string or all(_is_tag(t) for t in tokens):
        query['sort'] = [{'time': 'desc'}]

    query['query'] = {'bool': {}}
    conditions = query['query']['bool']

    # If there are any fields which don't get replaced as tag filters,
    # add them with the simple_query_string syntax.
    simple_qs = ' '.join(t for t in tokens if not _is_tag(t))
    if simple_qs:
        conditions['must'] = {
            'simple_query_string': {'query': simple_qs}
        }

    # Any tags get added as explicit "this must match" fields.
    tag_tokens = [t for t in tokens if _is_tag(t)]
    tags = [t.split(':', 1)[-1] for t in tag_tokens]
    if tags:
        conditions['filter'] = {
            'terms_set': {
                'tags.raw': {
                    'terms': tags,

                    # This tells Elasticsearch: every term should match!
                    'minimum_should_match_script': {
                        'source': 'params.num_terms'
                    }
                }
            }
        }

    # We always ask for an aggregation on tags.raw (which is a keyword field,
    # unlike the free-text field we can't aggregate), which is used to display
    # the contextual tag cloud.
    query['aggregations'] = {
        'tags': {
            'terms': {
                'field': 'tags.raw',
                'size': 100
            }
        }
    }

    return query


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

    def http_post(self, url, *args, **kwargs):
        return self._http_call(self.sess.post, url, *args, **kwargs)

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

    def put_document(self, index_name, id, document, document_type=None):
        """Put a document into an Elasticsearch index."""
        if document_type is None:
            document_type = index_name
        self.http_put(f'/{index_name}/{document_type}/{id}', data=document)
