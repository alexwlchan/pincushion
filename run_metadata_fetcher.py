#!/usr/bin/env python
# -*- encoding: utf-8
"""
Export the metadata from Pinboard and shove it in S3.

Usage:  run_metadata_fetcher.py --bucket=<BUCKET> --username=<USERNAME> --password=<PASSWORD>
        run_metadata_fetcher.py -h | --help
"""

import json
import re

from botocore.exceptions import ClientError
import boto3
import docopt
import requests

from pincushion import bookmarks
from pincushion.services import aws


def get_bookmarks_from_pinboard(username, password):
    """Returns a list of bookmarks from Pinboard."""
    resp = requests.get(
        'https://api.pinboard.in/v1/posts/all',
        params={'format': 'json'},
        auth=(username, password)
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    bucket = args['--bucket']
    username = args['--username']
    password = args['--password']

    # Page through my Pinboard account, and attach the Pinboard IDs.
    sess = requests.Session()
    sess.hooks['response'].append(
        lambda r, *args, **kwargs: r.raise_for_status()
    )

    # Yes, Pinboard sends you into a redirect loop if you're not in a
    # browser.  It's very silly.
    resp = sess.post(
        'https://pinboard.in/auth/',
        data={'username': username, 'password': password},
        allow_redirects=False
    )

    pinboard_metadata = []
    starred = []
    url = f'https://pinboard.in/u:{username}'
    while True:
        print(f'Processing {url}...')
        resp = sess.get(url)

        # Starred data is in a <script> tag:
        #
        #     var starred = ["123","124"];
        #
        starredjs = resp.text.split('var starred = ')[1].split(';')[0].strip('[]')
        stars = [s.strip('"') for s in starredjs.split(',')]
        print(stars)
        starred.extend(stars)

        # Turns out all the bookmark data is declared in a massive <script>
        # tag in the form:
        #
        #   var bmarks={};
        #   bmarks[1234] = {...};
        #   bmarks[1235] = {...};
        #
        # so let's just read that!
        bookmarkjs = resp.text.split('var bmarks={};')[1].split('</script>')[0]

        # I should use a proper JS parser here, but for now simply looking
        # for the start of variables should be enough.
        bookmarks_list = re.split(r';bmarks\[[0-9]+\] = ', bookmarkjs.strip(';'))

        # The first entry is something like '\nbmarks[1234] = {...}', which we
        # can discard.
        bookmarks_list[0] = re.sub(r'^\s*bmarks\[[0-9]+\] = ', '', bookmarks_list[0])

        pinboard_metadata.extend(json.loads(b) for b in bookmarks_list)

        # Now look for the thing with the link to the next page:
        #
        #   <div id="bottom_next_prev">
        #       <a class="next_prev" href="...">earlier</a>
        #
        bottom_next_prev = resp.text.split('<div id="bottom_next_prev">')[1].split('</div>')[0]
        earlier, _ = bottom_next_prev.split('</a>', 1)
        if 'earlier' in earlier:
            url = 'https://pinboard.in' + earlier.split('href="')[1].split('"')[0]
        else:
            break

        print(len(pinboard_metadata))

    client = boto3.client('s3')

    # Deduplicate
    set_of_jsons = set(
        json.dumps(d, sort_keys=True) for d in pinboard_metadata
    )
    metadata = [json.loads(t) for t in set_of_jsons]
    aws.write_json_to_s3(bucket=bucket, key='metadata.json', data=metadata)

    starred = sorted(set(starred))
    aws.write_json_to_s3(bucket=bucket, key='starred.json', data=starred)

    # Now we get the data from the API... and we'll intersperse the Pinboard
    # slugs while we're here.
    new_bookmarks = get_bookmarks_from_pinboard(
        username=username,
        password=password
    )

    try:
        existing_bookmarks = aws.read_json_from_s3(
            bucket=bucket, key='bookmarks.json'
        )
    except ClientError as err:
        if err.response['Error']['Code'] == 'NoSuchKey':
            existing_bookmarks = {}
        else:
            raise

    merged_bookmark_dict = bookmarks.merge(
        cached_data=existing_bookmarks,
        new_api_response=new_bookmarks
    )

    for _, b in merged_bookmark_dict.items():
        matching = [m for m in pinboard_metadata if m['url'] == b['href']]
        # assert len(matching) == 1, matching
        matching = matching[0]
        b['slug'] = matching['slug']
        b['starred'] = matching['id'] in starred

    aws.write_json_to_s3(
        bucket=bucket,
        key='bookmarks.json',
        data=merged_bookmark_dict
    )
