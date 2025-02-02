# -*- coding: utf-8 -*-
#

"""Configuration for ScienceData module."""

SCIENCEDATA_RELEASE_CLASS = 'sciencedata.api:ScienceDataRelease'
"""ScienceDataRelease class to be used for release handling."""

SCIENCEDATA_DEPOSIT_CLASS = 'zenodo.modules.deposit.api:ZenodoDeposit'
"""Deposit class that implements a `publish` method."""

SCIENCEDATA_PID_FETCHER = 'recid'
"""PID Fetcher for Release records."""

SCIENCEDATA_TEMPLATE_INDEX = 'sciencedata/settings/index.html'
"""ScienceData object list template."""

SCIENCEDATA_TEMPLATE_VIEW = 'sciencedata/settings/view.html'
"""ScienceData object detail view template."""

SCIENCEDATA_PRIVATE_URL = 'https://10.2.0.13/'
"""ScienceData object detail view template."""

SCIENCEDATA_RECORD_SERIALIZER = 'zenodo.modules.records.serializers.githubjson_v1'
"""Record serializer to use for serialize record metadata. The GitHub module allows a .json file containing plain json."""

SIPSTORE_SCIENCEDATA_AGENT_JSONSCHEMA = 'sipstore/agent-sciencedataclient-v1.0.0.json'
