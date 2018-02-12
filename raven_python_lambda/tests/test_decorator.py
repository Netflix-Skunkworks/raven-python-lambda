import threading
from time import sleep
import os

import pytest

from raven_python_lambda import RavenLambdaWrapper


def test_raven_lambda_wrapper():
    @RavenLambdaWrapper()
    def test_func(event, context):
        raise Exception('There was an error.')

    with pytest.raises(Exception):
        test_func({'myEvent': 'event'}, {'myContext': 'context'})


def test_can_override_configuration():
    r = RavenLambdaWrapper(dict(logging=False))

    assert r.config['logging'] is False, 'expected the config option to be overridden'


class FakeContext(object):
    def get_remaining_time_in_millis(self):
        return 300000


def test_only_has_one_running_thread_after_execution_finishes():
    @RavenLambdaWrapper()
    def f(event, context):
        pass

    f({}, FakeContext())

    sleep(0.1)  # A bit iffy. But if we don't wait a bit the threads will not have stopped
    assert threading.active_count() == 1, 'expected all scheduled threads to have been removed'


def test_that_sqs_transport_is_used(sqs, sqs_queue):
    @RavenLambdaWrapper()
    def test_func(event, context):
        raise Exception('There was an error.')

    with pytest.raises(Exception):
        test_func({}, FakeContext())

    # Check that it sent to SQS:
    messages = sqs.receive_message(QueueUrl=sqs_queue)["Messages"]
    assert len(messages) == 1


def test_that_local_environment_is_ignored(monkeypatch):
    keys = ['IS_OFFLINE', 'IS_LOCAL']

    for k in keys:
        monkeypatch.setenv(k, 'yes.')
        wrapper = RavenLambdaWrapper()
        assert not wrapper.config['enabled']
        monkeypatch.delenv(k)


def test_that_remote_environment_is_not_ignored(monkeypatch):
    keys = ['IS_OFFLINE', 'IS_LOCAL']
    def f(event, context):
        pass

    for k in keys:
        try:
            monkeypatch.delenv(k)
        except:
            pass

    wrapper = RavenLambdaWrapper()
    assert wrapper.config['enabled']
    assert wrapper.config['raven_client']
