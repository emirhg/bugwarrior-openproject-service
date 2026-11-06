# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name="bugwarrior-service-openproject",
    version="1.0.1",
    zip_safe=False,

    author="Emir Herrera González",
    author_email="emir.herrera@itam.mx",
    description="A service to pull OpenProject Work Packages into TaskWarrior via BugWarrior",
    long_description="A service to pull OpenProject Work Packages into TaskWarrior via BugWarrior",
    long_description_content_type="text/plain",
    url="https://github.com/emirhg/bugwarrior-openproject-service",
    # Installs into the existing bugwarrior.services package (bugwarrior's
    # own __init__.py is not shipped, so it is never overwritten).
    package_dir={"": "src"},
    py_modules=["bugwarrior.services.openproject"],
    install_requires=[
        "isodate",
        "python-dateutil",
        "requests",
        "taskw",
    ],

    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPL-3.0",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.10',
    entry_points="""
    [bugwarrior.service]
    openproject=bugwarrior.services.openproject:OpenProjectService
    """,
)
