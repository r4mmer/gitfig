from setuptools import find_packages, setup

setup(
    name='gitfig',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'gitpython',
        'PyYaml',
    ],
    author='André Carneiro',
    author_email='acarneiro.dev@gmail.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Information Technology',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3 :: Only',
    ],
)
