#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'twistedlilypad>=1.0.5',
    'txMongo>=16.3.0'
]

test_requirements = [
    # TODO: put package test requirements here
]

setup(
    name='playtimetracker',
    version='0.0.1',
    description="Python daemon which handles closing all time tracking sessions provided by [PlaytimeTracker Plugin](https://github.com/flaminscotsman/PlayTimeTracker).",
    long_description=readme + '\n\n' + history,
    author="Alasdair Scott",
    author_email='ali@flaminscotsman.co.uk',
    url='https://github.com/flamin_scotsman/playtimetracker',
    packages=[
        'playtimetracker',
    ],
    package_dir={'playtimetracker':
                 'playtimetracker'},
    entry_points={
        'console_scripts': [
            'playtimetracker=playtimetracker.tracker:main',
            'playtimepoller=playtimetracker.poller:main'
        ]
    },
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='playtimetracker',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
    ],
    test_suite='tests',
    tests_require=test_requirements
)
