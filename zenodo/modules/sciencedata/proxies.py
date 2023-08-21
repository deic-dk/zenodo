# -*- coding: utf-8 -*-
#

"""Proxy for current previewer."""

from __future__ import absolute_import, print_function

from flask import current_app
from werkzeug.local import LocalProxy

current_sciencedata = LocalProxy(
    lambda: current_app.extensions['sciencedata'])
