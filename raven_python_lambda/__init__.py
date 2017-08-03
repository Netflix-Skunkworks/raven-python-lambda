"""
raven_python_lambda.lambda
~~~~~~~~~~~~~~~~~~~~~~~~~~

Raven wrapper for AWS Lambda handlers.

"""
import os
import math
import psutil
import logging
import functools
from threading import Timer

from raven.base import Client
from raven.conf import setup_logging
from raven.utils.conf import convert_options
from raven.transport.http import HTTPTransport
from raven.handlers.logging import SentryHandler

logging.basicConfig()
logger = logging.getLogger(__file__)


def configure_raven_client(config):
    # check for local environment
    is_local_env = os.environ.get('IS_OFFLINE') or os.environ.get('IS_LOCAL')
    if config['filter_local'] and is_local_env:
        logger.warning('Sentry is disabled in local environment')

    defaults = {
        'include_paths': (
            set(config.get('SENTRY_INCLUDE_PATHS', []))
        ),
        'ignore_exceptions': config.get('RAVEN_IGNORE_EXCEPTIONS', []),
        'release': os.environ.get('SENTRY_RELEASE'),
        'environment': 'Local' if is_local_env else os.environ.get('SENTRY_ENVIRONMENT'),
        'tags': {
            'lambda': os.environ.get('AWS_LAMBDA_FUNCTION_NAME'),
            'version': os.environ.get('AWS_LAMBDA_FUNCTION_VERSION'),
            'memory_size': os.environ.get('AWS_LAMBDA_FUNCTION_MEMORY_SIZE'),
            'log_group': os.environ.get('AWS_LAMBDA_LOG_GROUP_NAME'),
            'log_stream': os.environ.get('AWS_LAMBDA_LOG_STREAM_NAME'),
            'service_name': os.environ.get('SERVERLESS_SERVICE'),
            'stage': os.environ.get('SERVERLESS_STAGE'),
            'alias': os.environ.get('SERVERLESS_ALIAS'),
            'region': os.environ.get('SERVERLESS_REGION') or os.environ.get('AWS_REGION')
        },
        'transport': HTTPTransport,
        'dsn': os.environ.get('SENTRY_DSN')
    }

    return Client(
        **convert_options(
            config,
            defaults=defaults
        )
    )


class RavenLambdaWrapper(object):
    """
    raven-python wrapper for AWS Lambda.

    By default, the lambda integration will do the following:

    - Capture memory warnings
    - Capture timeout warnings
    - Capture unhandled exceptions
    - Automatically create breadcrumbs

    Usage:

    raven_config = {
         'capture_errors': False,
         'capture_unhandled_rejections': True,
         'capture_memory_warnings': True,
         'capture_timeout_warnings': True
    }

    @RavenLambdaWrapper(raven_config)
    def handler(event, context):
        raise Exception('I will be sent to sentry!')

    """
    def __init__(self, config=None):
        self.config = config

        if not self.config:
            self.config = {}

        config_defaults = {
            'capture_timeout_warnings': os.environ.get('SENTRY_CAPTURE_TIMEOUTS', True),
            'capture_memory_warnings': os.environ.get('SENTRY_CAPTURE_MEMORY', True),
            'capture_unhandled_exceptions': os.environ.get('SENTRY_CAPTURE_UNHANDLED', True),
            'auto_bread_crumbs': os.environ.get('SENTRY_AUTO_BREADCRUMBS', True),
            'capture_errors': os.environ.get('SENTRY_CAPTURE_ERRORS', True),
            'filter_local': os.environ.get('SENTRY_FILTER_LOCAL', True),
            'logging': os.environ.get('SENTRY_CAPTURE_LOGS', True),
        }

        self.config.update(config_defaults)

        if self.config.get('raven_client'):
            assert self.config.get('raven_client') and not isinstance(self.config.get('raven_client'), Client)
        else:
            self.config['raven_client'] = configure_raven_client(self.config)

        if self.config['logging']:
            setup_logging(SentryHandler(self.config['raven_client']))

    def __call__(self, fn):
        """Wraps our function with the necessary raven context."""
        @functools.wraps(fn)
        def decorated(event, context):
            self.context = context

            raven_context = {
                'extra': {
                    'event': event,
                    'context': context,
                },
                'tags': {}
            }

            # Gather identity information from context if possible
            if event.get('requestContext'):
                identity = event['requestContext']['identity']
                if identity:
                    raven_context['user'] = {
                         'id': identity.get('cognitoIdentityId', None),
                         'username': identity.get('user', None),
                         'ip_address': identity.get('sourceIp', None),
                         'cognito_identity_pool_id': identity.get('cognitoIdentityPoolId', None),
                         'cognito_authentication_type': identity.get('cognitoAuthenticationType', None),
                         'user_agent': identity.get('userAgent')
                     }

            # Add additional tags for AWS_PROXY endpoints
            if event.get('requestContext'):
                raven_context['tags'] = {
                    'api_id': event['requestContext']['apiId'],
                    'api_stage': event['requestContext']['stage'],
                    'http_method': event['requestContext']['httpMethod']
                }

            # Add cloudwatch event context
            if event.get('detail'):
                raven_context = {'tags': {}}
                if event.get('userIdentity'):
                    raven_context['tags']['cloudwatch_principal_id'] = event['userIdentity']['principalId']
                if event.get('awsRegion'):
                    raven_context['tags']['cloudwatch_region'] = event['awsRegion']

            # rethrow exception to halt lambda execution
            try:
                if self.config.get('auto_bread_crumbs'):
                    # first breadcrumb is the invocation of the lambda itself
                    breadcrumb = {
                        'message': os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'local'),
                        'category': 'lambda',
                        'level': 'info',
                        'data': {}
                    }

                    if event.get('requestContext'):
                        breadcrumb['data'] = {
                            'http_method': event['requestContext']['httpMethod'],
                            'host': event['headers']['Host'],
                            'path': event['path']
                        }

                    self.config['raven_client'].captureBreadcrumb(**breadcrumb)

                # install our timers
                install_timers(self.config, context)

                # invoke the original function
                fn(event, context)
            except Exception as e:
                self.config['raven_client'].captureException()
                raise e

        return decorated


def timeout_error(config):
    """Captures a timeout error."""
    config['raven_client'].captureMessage('Function Timed Out', level='error')


def timeout_warning(config, context):
    """Captures a timeout warning."""
    config['raven_client'].captureMessage(
        'Function Execution Time Warning',
        level='warning',
        extra={
            'TimeRemainingInMsec': context.get_remaining_time_in_millis()

        }
    )


def memory_warning(config, context):
    """Determines when memory usage is nearing it's max."""
    used = psutil.Process(os.getpid()).memory_info().rss / 1048576
    limit = float(context.memory_limit_in_mb)
    p = used / limit

    if p >= 0.75:
        config['raven_client'].captureMessage(
            'Memory Usage Warning',
            level='warning',
            extra={
                'MemoryLimitInMB': context.memory_limit_in_mb,
                'MemoryUsedInMB': math.floor(used)
            }
        )
    else:
        # nothing to do check back later
        Timer(500, memory_warning, (config, context)).start()


def install_timers(config, context):
    """Create the timers as specified by the plugin configuration."""
    if config.get('capture_timeout_warnings'):
        # We schedule the warning at half the maximum execution time and
        # the error a few miliseconds before the actual timeout happens.
        time_remaining = context.get_remaining_time_in_millis()
        Timer(time_remaining / 2, timeout_warning, (config, context)).start()
        Timer(max(time_remaining - 500, 0), timeout_error, (config)).start()

    if config.get('capture_memory_warnings'):
        # Schedule the memory watch dog interval. Warning will re-schedule itself if necessary.
        Timer(500, memory_warning, (config, context)).start()
