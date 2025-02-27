#!/usr/bin/env python
from setuptools import setup

# This redirects to use pyproject.toml for the metadata
# but helps with editable installs
setup(package_dir={"": "src"})
