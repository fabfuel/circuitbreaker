"""
Python Circuit Breaker
"""
from setuptools import setup


def readme():
    with open('README.rst') as f:
        return f.read()


setup(
    name='circuitbreaker',
    version='2.0.0',
    url='https://github.com/fabfuel/circuitbreaker',
    download_url='https://github.com/fabfuel/circuitbreaker/archive/1.3.1.tar.gz',
    license='BSD-3-Clause',
    author='Fabian Fuelling',
    author_email='pypi@fabfuel.de',
    description='Python Circuit Breaker pattern implementation',
    long_description=readme(),
    py_modules=['circuitbreaker'],
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
    ],
    options={'bdist_wheel': {'universal': True}}
)
