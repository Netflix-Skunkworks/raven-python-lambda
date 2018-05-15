# ⚡️ Sentry/Raven SDK Integration For AWS Lambda (python) and Serverless

[![serverless](http://public.serverless.com/badges/v3.svg)](http://www.serverless.com)
[![Build Status](https://travis-ci.org/Netflix-Skunkworks/raven-python-lambda.svg?branch=master)](https://travis-ci.org/Netflix-Skunkworks/raven-python-lambda)
[![Coverage Status](https://coveralls.io/repos/github/Netflix-Skunkworks/raven-python-lambda/badge.svg?branch=master)](https://coveralls.io/github/Netflix-Skunkworks/raven-python-lambda?branch=master)
[![PyPI version](https://badge.fury.io/py/raven-python-lambda.svg)](https://badge.fury.io/py/raven-python-lambda)

## About
This library simplifies integration of Sentry's
[raven-python](https://docs.sentry.io/clients/python/) library with AWS Lambda.
The only supported platforms are Python 2.7 and Python 3.6.

### What is Raven and Sentry?
It's a bit confusing, but _Raven_ is the official name of the error reporting SDK
that will forward errors, exceptions and messages to the _Sentry_ server. For
more details of what Raven and Sentry actually is, refer to the official Sentry documentation: https://docs.sentry.io/.

### Benefits

* Easy to use.
* Integrates with [Serverless Framework](http://www.serverless.com) for
  AWS Lambda (though use of the framework is not required).
* Wraps your Python code with [Sentry](http://getsentry.com) error capturing.
* Forwards any errors returned by your AWS Lambda function to Sentry.
* Warn if your code is about to hit the execution timeout limit.
* Warn if your Lambda function is low on memory.
* Catches and reports unhandled exceptions.
* Serverless, Sentry and as well as this library are all Open Source. Yay! 🎉


## Installation

* Install the `raven-python-lambda` module from pip:
  ```bash
  pip install raven-python-lambda
  ```
* or install the `raven-python-lambda` locally:
  ```bash
  pip install -e .
  ```
* Check out the examples below how to integrate it with your project
  by updating `serverless.yml` as well as your Lambda handler code.


### Use as Standalone Library
If you don't want to add another plugin to Serverless, you can use this
library standalone without additional dependencies (besides `raven` itself).

You will need to extend your `serverless.yml` to include additional
environment variables. The only required environment variable is `SENTRY_DSN`
to set the [DSN url](https://docs.sentry.io/quickstart/#configure-the-dsn)
for your reporting. A full list of available environment variables is
available below.

```yaml
service: my-serverless-project
provider:
  # ...
  environment:
    SENTRY_ENVIRONMENT: ${opt:stage, self:provider.stage} # recommended
    SENTRY_DSN: https://xxxx:yyyy@sentry.io/zzzz # URL provided by Sentry
```

### Use Together With the Serverless Sentry Plugin
The [Serverless Sentry Plugin](https://github.com/arabold/serverless-sentry-plugin)
allows configuration of the library through the `serverless.yml`. This is the
recommended way of using the `serverless-sentry-lib` library.

Instead of manually setting environment variables the plugin determines and
sets them automatically. In the `serverless.yml` simply load the plugin and
set the `dsn` configuration option as follows:

```yaml
service: my-serverless-project
provider:
  # ...
plugins:
  serverless-sentry
custom:
  sentry:
    dsn: https://xxxx:yyyy@sentry.io/zzzz # URL provided by Sentry
```

You can still manually set environment variables on a per-function level to
overwrite the plugin's ones.

### Environment Variables
Logging tags can be controlled through the following environment variables.
You can set them manually in your `serverless.yml` or let them be configured
automatically using the
[Serverless Sentry Plugin](https://github.com/arabold/serverless-sentry-plugin)
during deployment.

| Environment Variable | Description |
|----------------------|-------------|
| `SENTRY_DSN` | Sentry DSN Url |
| `SENTRY_ENVIRONMENT` | Environment (optional, e.g. "dev" or "prod") |
| `SENTRY_RELEASE` | Release number of your project (optional) |
| `SENTRY_AUTO_BREADCRUMBS` | Automatically create breadcrumbs (see Sentry Raven docs, default to `true`) |
| `SENTRY_FILTER_LOCAL` | Don't report errors from local environments (defaults to `true`) |
| `SENTRY_CAPTURE_ERRORS` | Enable capture Lambda errors (defaults to `true`) |
| `SENTRY_CAPTURE_UNHANDLED` | Enable capture unhandled exceptions (defaults to `true`) |
| `SENTRY_CAPTURE_MEMORY` | Enable monitoring memory usage (defaults to `true`) |
| `SENTRY_CAPTURE_TIMEOUTS` | Enable monitoring execution timeouts (defaults to `true`) |
| `SENTRY_CAPTURE_LOGS` | Enable capture log messages (defaults to `true`) |
| `SENTRY_LOG_LEVEL` | Capture logs in sentry starting at this level (defaults to logging.WARNING) |
| `SENTRY_TIMEOUT_THRESHOLD` | Set the percent threshold to trigger timeout warning (defaults to 0.50) |
| `SENTRY_MEMORY_THRESHOLD` | Set the percent threshold to trigger memory usage warning (defaults to 0.75) |

In addition the library checks for the following optional variables and adds
them as custom tags automatically:

| Environment Variable | Sentry Tag | Description |
|----------------------|------------|-------------|
| `SERVERLESS_SERVICE` | service_name |  Serveless service name |
| `SERVERLESS_STAGE` | stage | Serverless stage |
| `SERVERLESS_ALIAS` | alias | Serverless alias, see [Serverless AWS Alias Plugin](https://github.com/hyperbrain/serverless-aws-alias) |
| `SERVERLESS_REGION` | region | Serverless region name |

## Usage
For maximum flexibility this library is implemented as a decorated around your
original AWS Lambda handler code (your `def handler()` or similar). The
`RavenLambdaWrapper` adds error and exception handling, and takes care
of configuring the Raven client automatically.

The `RavenLambdaWrapper` is pre-configured to reasonable defaults and
doesn't need much setup. Simply pass in your configuration.
 Passing in your own `Raven` client is
necessary to ensure that the wrapper uses the same environment as the rest
of your code. In the rare circumstances that this isn't desired, you can
pass in `null` instead.

**Original Lambda Handler Code Before Adding RavenLambdaWrapper**:
```python

def handler(event, context):
    print("Go Serverless! Your function executed successfully")
```

**New Lambda Handler Code With RavenLambdaWrapper For Sentry Reporting**
```python

from raven import Client # Offical `raven` module
from raven_python_lambda import RavenLambdaWrapper

@RavenLambdaWrapper()
def handler(event, context):
    print("Go Serverless! Your function executed successfully")

```

Once your Lambda handler code is wrapped in the `RavenLambdaWrapper`, it will
be extended it with automatic error reporting. Whenever your Lambda handler
sets an error response, the error is forwarded to Sentry with additional
context information.


### Setting Custom Configuration Options
As shown above you can use environment variables to control the Sentry
integration. In some scenarios in which environment variables are not desired
or in which custom logic needs to be executed, you can also pass in
configuration options to the `RavenLambdaWrapper` directly:

* `raven_client` - Your Raven client. Don't forget to set this if you send your
  own custom messages and exceptions to Sentry later in your code.
* `auto_breadcrumbs` - Automatically create breadcrumbs (see Sentry Raven docs,
  defaults to `true`)
* `filter_local` - don't report errors from local environments (defaults to `true`)
* `capture_errors` - capture Lambda errors (defaults to `true`)
* `capture_unhandled_rejections` - capture unhandled exceptions (defaults to `true`)
* `capture_memory_warnings` - monitor memory usage (defaults to `true`)
* `capture_timeout_warnings` - monitor execution timeouts (defaults to `true`)

```python
from raven import Client # Offical `raven` module
from raven_python_lambda import RavenLambdaWrapper

raven_config = {
  'capture_errors': False,
  'capture_unhandled_rejections': True,
  'capture_memory_warnings': True,
  'capture_timeout_warnings': True,
  'raven_client': client
}

@RavenLambdaWrapper(raven_config)
def handler(event, context):
    print("Go Serverless! Your function executed successfully")
```


### Accessing the Raven Client for Capturing Custom Messages and Exceptions
If you want to capture a message or exception from anywhere in your code,
simply use the Raven client as usual. It is a singleton instance and doesn't
need to be configured again:

```python
from raven import Client # Offical `raven` module
client.captureMessage("Hello from Lambda!", level="info ")
```

For further documentation on how to use it to capture your own messages refer to
[docs.getsentry.com](https://docs.getsentry.com/hosted/clients/node/usage/).

### Capturing Unhandled Exceptions
Typically, if your Lambda code throws an unhandled exception somewhere in the
code, the invocation is immediately aborted and the function exits with a
"`Process exited before completing request`". The plugin captures these
unhandled exceptions, forwards them to Sentry and returns the exception like
any regular error generated by your function.

### Local Development
By default the library will not forward errors is if either the `IS_OFFLINE` or `IS_LOCAL` environment variable is set.
If you want to change this behavior set the `filter_local` config option to `False`.

### Detecting Slow Running Code
It's a good practice to specify the function timeout in `serverless.yml` to
be at last twice as large as the _expected maximum execution time_. If you
specify a timeout of 6 seconds (the default), this plugin will warn you if the
function runs for 3 or more seconds. That means it's time to either review your
code for possible performance improvements or increase the timeout value
slightly.

### Low Memory Warnings
The plugin will automatically generate a warning if the memory consumption of
your Lambda function crosses 75% of the allocated memory limit. The
plugin samples the amount of memory used by Python every 500 milliseconds
(using `psutil.Process(os.getpid()).memory_info().rss `), independently of any garbage collection.

Only one low memory warning will be generated per function invocation. You
might want to increase the memory limit step by step until your code runs
without warnings.

### Turn Sentry Reporting On/Off
Obviously Sentry reporting is only enabled if you wrap your code using the
`RavenLambdaWrapper` as shown in the examples above. In addition, error
reporting is only active if the `SENTRY_DSN` environment variable is set.
This is an easy way to enable or disable reporting as a whole or for specific
functions.

In some cases it might be desirable to disable only error reporting itself but
keep the advanced features such as timeout and low memory warnings in place.
This can be achieved via setting the respective options in the
environment variables or the `RavenLambdaWrapper` during initialization:

```python
from raven import Client # Offical `raven` module
from raven_python_lambda import RavenLambdaWrapper

raven_config = {
  'capture_errors': False,  # Don't log error responses from the Lambda ...
  'capture_unhandled_rejections': True,  # keep unhandled exception logging
  'capture_memory_warnings': True,  # memory warnings
  'capture_timeout_warnings': True,  # timeout warnings
  'raven_client': client
}

@RavenLambdaWrapper(raven_config)
def handler(event, context):
    print("Go Serverless! Your function executed successfully")
```

## SQS Proxying

This also supports the ability to forward all Sentry messages to an SQS queue. This is meant to be used in conjunction
with the [raven-sqs-proxy](https://github.com/Netflix-Skunkworks/raven-sqs-proxy) (polls SQS and then passes the message
on to Sentry).

**Why is this useful?**
If you don't have the ability of running AWS Lambda functions within a VPC, then then this plugin is necessary.

Some reasons for why you would not want or need to run a lambda function within VPC are:
- An AWS account doesn't have a useful VPC (special purpose accounts)
- An AWS account doesn't have a VPC that is peered to a VPC where Sentry is running
- Cross-region use cases where Sentry lives in an internal VPC without external connectivity
- **ENI Exhaustion Concerns:** It is possible to exhaust the ENIs within a VPC if you have many, many lambdas running. This can break new deployments within a VPC.

### What is required for SQS ###
For this to work, you will need:
1. An SQS queue
1. A lambda function launched with an IAM role with the following permissions to the SQS queue:
    ```
    sqs:GetQueueUrl
    sqs:SendMessage
    ```
1. A DSN that with the following parameters to the URL:
    ```
    sqs_region - The AWS region name for where the SQS queue resides
    sqs_account - This is the 12 digit AWS account number
    sqs_name - The name of the SQS queue
    ```
    - An example: `https://user:pass@some-sentry-server?sqs_region=us-west-2&sqs_account=111111111111sqs_name=sentry-queue`
1. The proxying service enabled and running. Please review the documentation on the
[raven-sqs-proxy](https://github.com/Netflix-Skunkworks/raven-sqs-proxy) page for details.

## Thanks

Big thanks to arabold and https://github.com/arabold/serverless-sentry-plugin as
they were the inspiration for this work.

## Version History



