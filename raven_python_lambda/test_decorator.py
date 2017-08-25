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
