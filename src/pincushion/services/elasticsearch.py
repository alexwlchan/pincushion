# -*- encoding: utf-8


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
