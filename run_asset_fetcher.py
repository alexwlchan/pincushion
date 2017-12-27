#!/usr/bin/env python
# -*- encoding: utf-8
"""
Use the S3 metadata, and back up assets into S3.

Usage:  run_asset_fetcher.py --bucket=<BUCKET> --username=<USERNAME> --password=<PASSWORD>
        run_asset_fetcher.py -h | --help
"""

import os
import subprocess
import tempfile

import docopt

from pincushion import bookmarks as pin_bookmarks
from pincushion.services import aws


def wget(*cmd, **kwargs):
    subprocess.check(['wget'] + list(cmd), **kwargs)


def cprint(s):
    print('\033[92m*** ' + s + '\033[0m')


args = docopt.docopt(__doc__)
bucket = args['--bucket']
username = args['--username']
password = args['--password']

bookmarks = aws.read_json_from_s3(bucket=bucket, key='bookmarks.json')
metadata = aws.read_json_from_s3(bucket=bucket, key='metadata.json')

# Create the wget cookies file
subprocess.check_call([
    'wget',
    '--save-cookies', 'cookies.txt',
    '--keep-session-cookies',
    '--post-data', f'username={username}&password={password}',
    '--delete-after', 'https://pinboard.in/auth/'
])

try:
    for b_id, bookmark in bookmarks.items():
        matching = [m for m in metadata if m['url'] == bookmark['href']]
        cprint(f'Should I back up {bookmark["href"]}?')

        if bookmark.get('_backup', False):
            cprint(f'Skipping backup for {bookmark["href"]}, already exists!')
            continue

        # Check wget can download the page at all
        try:
            subprocess.check_call(
                ['wget', bookmark['href']],
                cwd=tempfile.mkdtemp(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT
            )
        except subprocess.CalledProcessError:
            cprint('Page is inaccessible to wget; skipping')
            continue

        outdir = tempfile.mkdtemp()
        proc = subprocess.Popen([
            'wget',
            '--adjust-extension',
            '--span-hosts',
            '--no-verbose',
            '--convert-links',
            '--page-requisites',
            '--no-directories',
            '--load-cookies', os.path.join(os.path.abspath(os.curdir), 'cookies.txt'),
            '--output-file', '-',
            bookmark["href"]
        ], cwd=outdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, _ = proc.communicate()

        # First line will be someting like
        #
        #    2017-12-27 00:20:14 URL:https://example.org [101/101] -> "example.html" [1]
        #
        # We want that filename, and we want to rename it to index.html.
        try:
            filename = stdout.decode('utf8').splitlines()[0].split('->')[-1].strip().split()[0].strip('"')
        except UnicodeDecodeError as err:
            print(err)
            continue

        try:
            os.rename(
                src=os.path.join(outdir, filename),
                dst=os.path.join(outdir, 'index.html')
            )
        except FileNotFoundError as err:
            print(err)
            print(stdout)
            continue

        # I never care about robots.txt, but wget always fetches it.
        try:
            os.unlink(os.path.join(outdir, 'robots.txt'))
        except FileNotFoundError:
            pass

        try:
            subprocess.check_call([
                'aws', 's3', 'cp',
                '--recursive', '--acl', 'public-read', outdir,
                f's3://{bucket}/{b_id}'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            cprint(f'Error uploading to S3?')
            continue

        bookmark['_backup'] = True
except KeyboardInterrupt:
    pass


new_bookmarks = aws.read_json_from_s3(bucket=bucket, key='bookmarks.json')

merged_bookmark_list = pin_bookmarks.merge(
    cached_data=bookmarks,
    new_api_response=list(new_bookmarks.values())
)

aws.write_json_to_s3(
    bucket=bucket,
    key='bookmarks.json',
    data=merged_bookmark_list
)
