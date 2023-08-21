# -*- coding: utf-8 -*-

"""ScienceData bundles for user interface."""

from flask_assets import Bundle
from invenio_assets import NpmBundle

js = NpmBundle(
    Bundle(
        'js/sciencedata/init.js',
        filters='requirejs',
    ),
    depends=('js/sciencedata/*.js'),
    filters='jsmin',
    output='gen/sciencedata.%(version)s.js',
)
"""Default Javascript bundle."""

css = NpmBundle(
    Bundle(
        'scss/sciencedata/sciencedata.scss',
        filters='scss',
    ),
    filters='cleancss',
    depends=('scss/sciencedata/*.scss'),
    output='gen/sciencedata.%(version)s.css',
)
"""Default CSS bundle."""
