import pytest


def test_raven_lambda_wrapper():
    from raven_python_lambda import RavenLambdaWrapper

    @RavenLambdaWrapper()
    def test_func(event, context):
        raise Exception('There was an error.')

    with pytest.raises(Exception):
        test_func({'myEvent': 'event'}, {'myContext': 'context'})
