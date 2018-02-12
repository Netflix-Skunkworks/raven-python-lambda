"""
.. module: raven_python_lambda.sqs_transport
    :platform: Unix
    :copyright: (c) 2017 by Netflix Inc., see AUTHORS for more
    :license: Apache, see LICENSE for more details.

.. moduleauthor:: Mike Grima <mikegrima> @THISisPLACEHLDR
"""
import base64
import json

import boto3
from botocore.exceptions import ClientError

from raven.utils.compat import string_types
from raven.conf import defaults
from raven.transport.base import Transport


class SQSTransport(Transport):
    scheme = ['sqs+https', 'sqs+http']

    def __init__(self, sqs_region, sqs_account, sqs_name,
                 timeout=defaults.TIMEOUT, verify_ssl=True,
                 ca_certs=defaults.CA_BUNDLE):
        # Stuff the docs require:
        if isinstance(timeout, string_types):
            timeout = int(timeout)
        if isinstance(verify_ssl, string_types):
            verify_ssl = bool(int(verify_ssl))

        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.ca_certs = ca_certs
        #####################

        # Stuff SQS requires:
        self.sqs_name = sqs_name
        self.sqs_account = sqs_account
        self.sqs_client = boto3.client("sqs", region_name=sqs_region)
        self.queue_url = None

    def send(self, url, data, headers):
        """
        Sends a request to an SQS queue -- to be later popped off
        later for submission into Sentry.
        Note: This will simply raise any Boto ClientErrors that are encountered.
        """
        if not self.queue_url:
            self.queue_url = self.sqs_client.get_queue_url(QueueName=self.sqs_name,
                                                           QueueOwnerAWSAccountId=self.sqs_account)["QueueUrl"]

        payload = {
            "url": url,
            "headers": headers,
            "data": base64.b64encode(data).decode("utf-8")
        }

        try:
            self.sqs_client.send_message(QueueUrl=self.queue_url,
                                         MessageBody=json.dumps(payload))
        except ClientError as e:
            # TODO break circular dep for logging
            print(data)  # not sure if this is the best way to get messages.
            raise e
