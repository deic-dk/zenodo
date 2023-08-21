# -*- coding: utf-8 -*-
#

"""Invenio module that adds ScienceData integration to the platform."""

from __future__ import absolute_import, print_function

from flask import current_app
from six import string_types
from sqlalchemy import event
from werkzeug.utils import cached_property, import_string

from . import config


class ScienceData(object):
    """ScienceData extension."""

    def __init__(self, app=None):
        """Extension initialization."""
        if app:
            self.init_app(app)

    @cached_property
    def record_serializer(self):
        """ScienceData Release API class."""
        imp = current_app.config['SCIENCEDATA_RECORD_SERIALIZER']
        if isinstance(imp, string_types):
            return import_string(imp)
        return imp

    def init_app(self, app):
        """Flask application initialization."""
        self.init_config(app)
        app.extensions['sciencedata'] = self

    def init_config(self, app):
        """Initialize configuration."""
        app.config.setdefault(
            'SCIENCEDATA_BASE_TEMPLATE',
            app.config.get('BASE_TEMPLATE',
                           'invenio_github/base.html'))

        app.config.setdefault(
            'SCIENCEDATA_SETTINGS_TEMPLATE',
            app.config.get('SETTINGS_TEMPLATE',
                           'invenio_oauth2server/settings/base.html'))

        for k in dir(config):
            if k.startswith('SCIENCEDATA_'):
                app.config.setdefault(k, getattr(config, k))
