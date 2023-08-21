# -*- coding: utf-8 -*-
#

"""Invenio module that adds ScienceData integration to the platform."""

from __future__ import absolute_import, print_function

from .ext import ScienceData
from .version import __version__

__all__ = ('__version__', 'ScienceData')
