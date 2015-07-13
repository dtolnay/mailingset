import sys
from setuptools import setup

# requires configparser for Python 2.x
if sys.version_info[0] < 3:
    python2_requires = ['configparser']
else:
    python2_requires = []

setup(name='mailingset',
      version='0.1.0-dev',
      description='A mail server that supports set operations on mailing lists.',
      keywords='union intersection difference',
      url='https://github.com/dtolnay/mailingset',
      license='MIT / X / Expat License',
      packages=['mailingset'],
      install_requires=[
                        'twisted',
                        'zope.interface'
                       ] + python2_requires,
      test_suite='tests',
      tests_require=['nose']
      )
