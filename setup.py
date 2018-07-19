#!/usr/bin/env python

from __future__ import print_function
from setuptools import setup
from distutils.extension import Extension

import sys

if sys.version_info < (3,4):
    print('Python 3.4 is required', file=sys.stderr)
    sys.exit(1)

setup(
    name='vtfls',
    version='0.0.1',
    description='Inspect ASCII VTF files',
    maintainer='Eivind Fonn',
    maintainer_email='eivind.fonn@sintef.no',
    packages=['vtfls'],
    install_requires=['click'],
    entry_points={
        'console_scripts': [
            'vtfls=vtfls.__main__:main'
        ],
    },
)
