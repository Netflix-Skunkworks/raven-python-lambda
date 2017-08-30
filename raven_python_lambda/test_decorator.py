import threading
from time import sleep

import pytest

from raven_python_lambda import RavenLambdaWrapper


def test_raven_lambda_wrapper():
    from raven_python_lambda import RavenLambdaWrapper

    @RavenLambdaWrapper()
    def test_func(event, context):
        raise Exception('There was an error.')

    with pytest.raises(Exception):
        test_func({'myEvent': 'event'}, {'myContext': 'context'})


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
