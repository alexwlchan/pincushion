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
import unidecode


def create_id(bookmark):
    url = bookmark['href']
    url = re.sub(r'^https?://(www\.)?', '', url)

    # Based on http://www.leancrew.com/all-this/2014/10/asciifying/
    u = re.sub(u'[–—/:;,.]', '-', url)
    a = unidecode.unidecode(u).lower()
    a = re.sub(r'[^a-z0-9 -]', '', a)
    a = a.replace(' ', '-')
    a = re.sub(r'-+', '-', a)

    return a


def get_bookmarks_from_pinboard(username, password):
    """Returns a list of bookmarks from Pinboard."""
    resp = requests.get(
        'https://api.pinboard.in/v1/posts/all',
        params={'format': 'json'},
        auth=(username, password)
    )
    resp.raise_for_status()
    return resp.json()


def merge_bookmarks(existing_bookmarks, new_bookmarks):
    final = {}
    for b in new_bookmarks:
        existing = existing_bookmarks.get(create_id(b), {})
        existing.update(b)
        final[create_id(b)] = b
    return final


def upload_bookmarks_json(bucket, bookmarks):
    client = boto3.client('s3')
    json_string = json.dumps(bookmarks)
    client.put_object(
        Bucket=bucket, Key='bookmarks.json', Body=json_string.encode('utf8')
    )


if __name__ == '__main__':
    args = docopt.docopt(__doc__)

    bucket = args['--bucket']
    username = args['--username']
    password = args['--password']

    new_bookmarks = get_bookmarks_from_pinboard(
        username=username,
        password=password
    )

    client = boto3.client('s3')

    try:
        existing_body = (
            client.get_object(Bucket=bucket, Key='bookmarks.json').read())
    except ClientError as err:
        if err.response['Error']['Code'] == 'NoSuchKey':
            existing_body = b'{}'
        else:
            raise

    existing_bookmarks = json.loads(existing_body)
    merged_bookmark_list = merge_bookmarks(
        existing_bookmarks=existing_bookmarks,
        new_bookmarks=new_bookmarks
    )

    upload_bookmarks_json(bucket, bookmarks=merged_bookmark_list)

    # Then page through my Pinboard account, and attach the Pinboard IDs.
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
    url = f'https://pinboard.in/u:{username}'
    while True:
        print(f'Processing {url}...')
        resp = sess.get(url)

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
        bookmarks = re.split(r';bmarks\[[0-9]+\] = ', bookmarkjs.strip(';'))

        # The first entry is something like '\nbmarks[1234] = {...}', which we
        # can discard.
        bookmarks[0] = re.sub(r'^\s*bmarks\[[0-9]+\] = ', '', bookmarks[0])

        pinboard_metadata.extend(json.loads(b) for b in bookmarks)

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

    json_string = json.dumps(pinboard_metadata)
    client.put_object(
        Bucket=bucket, Key='metadata.json', Body=json_string.encode('utf8')
    )