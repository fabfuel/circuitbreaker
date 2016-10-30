"""
Python Circuit Breaker
"""
from setuptools import find_packages, setup


def readme():
    with open('README.rst') as f:
        return f.read()

dependencies = []

setup(
    name='circuitbreaker',
    version='1.0.1',
    url='https://github.com/fabfuel/circuitbreaker',
    download_url='https://github.com/fabfuel/circuitbreaker/archive/1.0.0.tar.gz',
    license='BSD',
    author='Fabian Fuelling',
    author_email='pypi@fabfuel.de',
    description='Python Circuit Breaker pattern implementation',
    long_description=readme(),
    py_modules=['circuitbreaker'],
    include_package_data=True,
    zip_safe=False,
    platforms='any',
    install_requires=dependencies,
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Operating System :: MacOS',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ]
)
