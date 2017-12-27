# -*- encoding: utf-8

import boto3
from moto import mock_s3
import pytest

from pincushion.services import aws


@mock_s3
def test_read_json_from_s3():
    client = boto3.client('s3', region_name='eu-west-1')
    client.create_bucket(
        Bucket='bukkit',
        CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'}
    )
    client.put_object(
        Bucket='bukkit',
        Key='myfile.json',
        Body=b'{"name": "alex", "colour": "red", "birthday": "july"}'
    )

    result = aws.read_json_from_s3(bucket='bukkit', key='myfile.json')
    assert result == {'name': 'alex', 'colour': 'red', 'birthday': 'july'}


@mock_s3
def test_read_json_from_s3_errors_if_invalid_json():
    client = boto3.client('s3', region_name='eu-west-1')
    client.create_bucket(
        Bucket='bukkit',
        CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'}
    )
    client.put_object(
        Bucket='bukkit',
        Key='myfile.xml',
        Body=b'<xml encoding="utf-8"><key1>value1</key1><key2>value2</key2>'
    )

    with pytest.raises(ValueError):
        aws.read_json_from_s3(bucket='bukkit', key='myfile.xml')
