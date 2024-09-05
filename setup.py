import os
import sys
from setuptools import setup, find_packages


version = '0.4.1'


with open('README.md', 'rt') as f:
    long_description = f.read()


with open('requirements.txt', 'rt') as f:
    requirements = tuple(f.read().split())


setup(
    name = 'bandcampsync',
    version = version,
    url = 'https://github.com/meeb/bandcampsync',
    author = 'https://github.com/meeb',
    author_email = 'meeb@meeb.org',
    description = 'A Python module and script to synchronise media purchased on bandcamp.com with a local directory.',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    license = 'BSD',
    include_package_data = True,
    install_requires = requirements,
    packages = find_packages(),
    scripts = [
        'bin/bandcampsync',
        'bin/bandcampsync-service',
    ],
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    keywords = ['bandcampsync', 'bandcamp', 'media', 'sync']
)
