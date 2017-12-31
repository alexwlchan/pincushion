# -*- encoding: utf-8

import markdown
from markdown.extensions.smarty import SmartyExtension


def title_markdown(md):
    """Renders a Markdown string as HTML for use in a bookmark title."""
    if len(md.splitlines()) != 1:
        raise ValueError(f"Title must be at most one line; got {md!r}")

    # We don't want titles to render with <h1> or similar tags if they start
    # with a '#', so escape that if necessary.
    if md.startswith('#'):
        md = f'\\{md}'

    res = markdown.markdown(md, extensions=[SmartyExtension()])
    return res.replace('<p>', '').replace('</p>', '')
