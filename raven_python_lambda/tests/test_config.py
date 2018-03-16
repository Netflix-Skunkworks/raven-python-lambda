import os
import logging
from raven_python_lambda import RavenLambdaWrapper


class FreshEnvironmentVariables:
    def __init__(self, values={}):
        self.intended_values = values

    def __enter__(self):
        self.old_environment_data = os.environ.copy()
        os.environ.clear()
        os.environ.update(self.intended_values)

    def __exit__(self, *args):
        os.environ.update(self.old_environment_data)


def test_config_defaults():
    with FreshEnvironmentVariables():
        wrapper = RavenLambdaWrapper()

        assert wrapper.config['capture_timeout_warnings'] == True
        assert wrapper.config['capture_memory_warnings'] == True
        assert wrapper.config['capture_unhandled_exceptions'] == True
        assert wrapper.config['auto_bread_crumbs'] == True
        assert wrapper.config['capture_errors'] == True
        assert wrapper.config['filter_local'] == True
        assert wrapper.config['is_local'] == False
        assert wrapper.config['logging'] == True
        assert wrapper.config['log_level'] == logging.WARNING
        assert wrapper.config['enabled'] == True

        raven_client = wrapper.config['raven_client']
        assert raven_client.include_paths == set()
        assert raven_client.ignore_exceptions == set()
        assert raven_client.release == None
        assert raven_client.environment == None

        client_tags = raven_client.tags
        assert client_tags['lambda'] == None
        assert client_tags['version'] == None
        assert client_tags['memory_size'] == None
        assert client_tags['log_group'] == None
        assert client_tags['log_stream'] == None
        assert client_tags['service_name'] == None
        assert client_tags['stage'] == None
        assert client_tags['alias'] == None
        assert client_tags['region'] == None


def test_log_level_config():
    with FreshEnvironmentVariables({'SENTRY_LOG_LEVEL': 'ERROR'}):
        wrapper = RavenLambdaWrapper()
        assert wrapper.config['log_level'] == logging.ERROR
    with FreshEnvironmentVariables({'SENTRY_LOG_LEVEL': '50'}):
        wrapper = RavenLambdaWrapper()
        assert wrapper.config['log_level'] == logging.CRITICAL
