# -*- encoding: utf-8

import math
import shlex

import attr


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


def build_query(query_string, page=1, page_size=96):
    """Returns a dict suitable for passing to Elasticsearch."""
    # These parameters can be set irrespective of the query string.
    # Note: 'from' is an offset parameter, and is 0-indexed.
    query = {
        'from': (page - 1) * page_size,
        'size': page_size,
    }

    def _is_filter(token):
        return _is_tag(token)

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

    if not query_string or all(_is_filter(t) for t in tokens):
        query['sort'] = [{'time': 'desc'}]

    query['query'] = {'bool': {'filter': []}}
    bool_conditions = query['query']['bool']

    # If there are any fields which don't get replaced as tag filters,
    # add them with the simple_query_string syntax.
    simple_qs = ' '.join(t for t in tokens if not _is_filter(t))
    if simple_qs:
        bool_conditions['must'] = {
            'query_string': {'query': simple_qs}
        }

    # Any tags get added as explicit "this must match" fields.
    tag_tokens = [t for t in tokens if _is_tag(t)]
    tags = [t.split(':', 1)[-1] for t in tag_tokens]
    if tags:
        bool_conditions['filter'].append({
            'terms_set': {
                'tags.raw': {
                    'terms': tags,

                    # This tells Elasticsearch: every term should match!
                    'minimum_should_match_script': {
                        'source': 'params.num_terms'
                    }
                }
            }
        })

    if not bool_conditions['filter']:
        del bool_conditions['filter']

    # We always ask for an aggregation on tags.raw (which is a keyword field,
    # unlike the free-text field we can't aggregate), which is used to display
    # the contextual tag cloud.
    query['aggregations'] = {
        'tags': {
            'terms': {
                'field': 'tags.raw',
                'size': 120
            }
        }
    }

    return query
