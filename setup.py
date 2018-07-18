#!/usr/bin/env python

from setuptools import setup
from distutils.extension import Extension

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
