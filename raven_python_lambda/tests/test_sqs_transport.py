"""
.. module: raven_python_lambda.tests.test_decorator
    :platform: Unix
    :copyright: (c) 2017 by Netflix Inc., see AUTHORS for more
    :license: Apache, see LICENSE for more details.

.. moduleauthor:: Mike Grima <mikegrima> @THISisPLACEHLDR
"""
import boto3

from raven_python_lambda.sqs_transport import SQSTransport
from raven.base import Client

# Simplify comparing dicts with primitive values:
from raven.utils import json
import zlib

import base64


def test_sqs_transport(sqs_queue):
    sqs = boto3.client("sqs", region_name="us-east-1")

    c = Client(dsn="mock://some_username:some_password@localhost:8143/1"
                   "?sqs_region=us-east-1&sqs_account=123456789012&sqs_name=sentry-queue",
               transport=SQSTransport)

    data = dict(a=42, b=55, c=list(range(50)))
    expected_message = zlib.decompress(c.encode(data))

    c.send(**data)

    transport = c._transport_cache["mock://some_username:some_password@localhost:8143/1"
                                   "?sqs_region=us-east-1&sqs_account=123456789012"
                                   "&sqs_name=sentry-queue"].get_transport()

    assert transport.sqs_account == "123456789012"
    assert transport.sqs_name == "sentry-queue"
    assert type(transport.sqs_client).__name__ == type(sqs).__name__
    assert transport.queue_url == "https://queue.amazonaws.com/123456789012/sentry-queue"

    # Check SQS for the message that was sent over:
    messages = sqs.receive_message(QueueUrl=transport.queue_url)["Messages"]
    assert len(messages) == 1

    body = json.loads(messages[0]["Body"])

    assert body["url"] == "mock://localhost:8143/api/1/store/"
    assert "sentry_secret=some_password" in body["headers"]["X-Sentry-Auth"]

    decoded_data = base64.b64decode(body["data"])

    assert json.dumps(json.loads(expected_message.decode('utf-8')), sort_keys=True) == \
           json.dumps(c.decode(decoded_data), sort_keys=True)   # noqa
