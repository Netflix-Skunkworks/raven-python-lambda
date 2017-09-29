"""
.. module: raven_python_lambda.tests.conftest
    :platform: Unix
    :copyright: (c) 2017 by Netflix Inc., see AUTHORS for more
    :license: Apache, see LICENSE for more details.

.. moduleauthor:: Mike Grima <mikegrima> @THISisPLACEHLDR
"""

from moto import mock_sqs
import boto3
import pytest
import os


class DsnEnvVar:
    def __init__(self):
        self.old_dsn = os.environ.get("SENTRY_DSN")

    def __enter__(self):
        os.environ["SENTRY_DSN"] = "https://asdfasdfds:Lasdfasdfadfs@somesentry.com/project" \
                                   "?sqs_name=sentry-queue&sqs_region=us-east-1&sqs_account=123456789012"

    def __exit__(self, *args):
        if self.old_dsn:
            os.environ["SENTRY_DSN"] = self.old_dsn
        else:
            del os.environ["SENTRY_DSN"]


@pytest.fixture(scope="function")
def sqs():
    with mock_sqs():
        yield boto3.client("sqs", region_name="us-east-1")


@pytest.fixture(scope="function")
def sqs_queue(sqs):
    with DsnEnvVar():
        sqs.create_queue(QueueName="sentry-queue")
        yield sqs.get_queue_url(QueueName="sentry-queue",
                                QueueOwnerAWSAccountId="123456789012")["QueueUrl"]
