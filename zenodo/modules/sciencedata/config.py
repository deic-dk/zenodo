# -*- coding: utf-8 -*-
#

"""Configuration for ScienceData module."""

SCIENCEDATA_RELEASE_CLASS = 'sciencedata.api:ScienceDataRelease'
"""ScienceDataRelease class to be used for release handling."""

SCIENCEDATA_DEPOSIT_CLASS = 'invenio_deposit.api:Deposit'
"""Deposit class that implements a `publish` method."""

SCIENCEDATA_PID_FETCHER = 'recid'
"""PID Fetcher for Release records."""

SCIENCEDATA_TEMPLATE_INDEX = 'sciencedata/settings/index.html'
"""ScienceData object list template."""

SCIENCEDATA_TEMPLATE_VIEW = 'sciencedata/settings/view.html'
"""ScienceData object detail view template."""

SCIENCEDATA_PRIVATE_URL = 'https://10.2.0.13/'
"""ScienceData object detail view template."""

