# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

setup(
    name="bugwarrior-service-openproject", # Replace with your own username
    version="1.0.0",
    zip_safe=False,

    author="Emir Herrera González",
    author_email="emir.herrera@itam.mx",
    description="A service to pull OpenProject Work Packages into TaskWarrior via BugWarrior",
    long_description="A service to pull OpenProject Work Packages into TaskWarrior via BugWarrior",
    long_description_content_type="text/plain",
    url="https://github.com/emirhg/bugwarrior-openproject-service",
    # packages=['openproject'],
    py_modules=['bugwarriorServiceOpenproject'],
    # py_modules=['openproject'],

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPL-3.0",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
    entry_points="""
    [bugwarrior.service]
    openproject=bugwarriorServiceOpenproject:OpenProjectService
    """,
    # Unsuccesful try to add this package into bugwarrior.services namespace
    # namespace_packages=['bugwarrior.services']
)
