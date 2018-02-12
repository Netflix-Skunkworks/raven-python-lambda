"""
.. module: raven_python_lambda
    :platform: Unix
    :copyright: (c) 2017 by Netflix Inc., see AUTHORS for more
    :license: Apache, see LICENSE for more details.

.. moduleauthor:: Kevin Glisson <kevgliss>
.. moduleauthor:: Mike Grima <mikegrima> @THISisPLACEHLDR
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

from raven_python_lambda.sqs_transport import SQSTransport

logging.basicConfig()
logger = logging.getLogger(__file__)


def boolval(v):
    return v in ("yes", "true", "t", "1", True, 1)


def configure_raven_client(config):
    defaults = {
        'include_paths': (
            set(config.get('SENTRY_INCLUDE_PATHS', []))
        ),
        'ignore_exceptions': config.get('RAVEN_IGNORE_EXCEPTIONS', []),
        'release': os.environ.get('SENTRY_RELEASE'),
        'environment': 'Local' if config['is_local'] else os.environ.get('SENTRY_ENVIRONMENT'),
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
        'transport': SQSTransport if "sqs_name" in os.environ.get('SENTRY_DSN', "") else HTTPTransport,
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
        self.config = {
            'capture_timeout_warnings': boolval(os.environ.get('SENTRY_CAPTURE_TIMEOUTS', True)),
            'capture_memory_warnings': boolval(os.environ.get('SENTRY_CAPTURE_MEMORY', True)),
            'capture_unhandled_exceptions': boolval(os.environ.get('SENTRY_CAPTURE_UNHANDLED', True)),
            'auto_bread_crumbs': boolval(os.environ.get('SENTRY_AUTO_BREADCRUMBS', True)),
            'capture_errors': boolval(os.environ.get('SENTRY_CAPTURE_ERRORS', True)),
            'filter_local': boolval(os.environ.get('SENTRY_FILTER_LOCAL', True)),
            'is_local': os.environ.get('IS_OFFLINE', False) or os.environ.get('IS_LOCAL', False),
            'logging': boolval(os.environ.get('SENTRY_CAPTURE_LOGS', True)),
            'log_level': int(os.environ.get('SENTRY_LOG_LEVEL', logging.WARNING)),
            'enabled': boolval(os.environ.get('SENTRY_ENABLED', True)),
        }
        self.config.update(config or {})

        # check for local environment
        if self.config['filter_local'] and self.config['is_local']:
            logger.warning('Sentry is disabled in local environment')
            self.config["enabled"] = False
            return

        if self.config.get('raven_client'):
            assert self.config.get('raven_client') and not isinstance(self.config.get('raven_client'), Client)
        else:
            self.config['raven_client'] = configure_raven_client(self.config)

        if self.config['logging'] and self.config['raven_client']:
            handler = SentryHandler(self.config['raven_client'])
            handler.setLevel(self.config['log_level'])
            setup_logging(handler)

    def __call__(self, fn):
        """Wraps our function with the necessary raven context."""
        @functools.wraps(fn)
        def decorated(event, context):
            if not self.config["enabled"]:
                return fn(event, context)

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
            timers = []
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
                timers = install_timers(self.config, context)

                # invoke the original function
                return fn(event, context)
            except Exception as e:
                self.config['raven_client'].captureException()
                raise e
            finally:
                for t in timers:
                    t.cancel()

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
        Timer(.5, memory_warning, (config, context)).start()


def install_timers(config, context):
    """Create the timers as specified by the plugin configuration."""
    timers = []
    if config.get('capture_timeout_warnings'):
        # We schedule the warning at half the maximum execution time and
        # the error a few miliseconds before the actual timeout happens.
        time_remaining = context.get_remaining_time_in_millis() / 1000
        timers.append(Timer(time_remaining / 2, timeout_warning, (config, context)))
        timers.append(Timer(max(time_remaining - .5, 0), timeout_error, [config]))

    if config.get('capture_memory_warnings'):
        # Schedule the memory watch dog interval. Warning will re-schedule itself if necessary.
        timers.append(Timer(.5, memory_warning, (config, context)))

    for t in timers:
        t.start()

    return timers
