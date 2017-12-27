# -*- encoding: utf-8

import json

import boto3


def read_json_from_s3(bucket, key):
    """Read a JSON file from S3, and return the parsed contents.

    :param bucket: Name of the source S3 bucket.
    :param key: Key to read.

    """
    client = boto3.client('s3')
    obj = client.get_object(Bucket=bucket, Key=key)
    body = obj['Body'].read()
    return json.loads(body)


def upload_json_to_s3(bucket, key, data):
    """Upload data to S3 as a JSON blob.

    :param bucket: Name of the destination S3 bucket.
    :param key: Key to write.
    :param data: Data to JSON-encode and upload.

    """
    client = boto3.client('s3')

    # This data will only be read by machines, so compacting the JSON to
    # save storage and transfer costs makes sense.
    json_string = json.dumps(data, separators=(',',':'), sort_keys=True)

    client.put_object(Bucket=bucket, Key=key, Body=json_string.encode('utf8'))
