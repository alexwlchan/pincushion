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
