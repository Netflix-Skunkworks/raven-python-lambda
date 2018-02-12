"""
Raven Python Lambda
===================

A simple decorator providing Sentry exception handling to AWS Lambda functions.
"""
import sys
import os.path

from setuptools import setup, find_packages

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

about = {}
with open(os.path.join(ROOT, "raven_python_lambda", "__about__.py")) as f:
    exec(f.read(), about)


install_requires = [
    'boto3',  # typically already on lambda but required for sqs
    'raven>=6.1.0',
    'psutil>=5.2.2'
]

tests_require = [
    'pytest',
    'moto',
    'coveralls',
    'tox'
]

setup(
    name=about["__title__"],
    version=about["__version__"],
    author=about["__author__"],
    author_email=about["__email__"],
    url=about["__uri__"],
    description=about["__summary__"],
    long_description='See README.md',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    extras_require={
        'tests': tests_require
    },
    keywords=['aws', 'sentry', 'raven', 'lambda']
)

