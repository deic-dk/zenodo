# -*- coding: utf-8 -*-
#

"""Various utility functions."""

import json
import yaml

from datetime import datetime
from operator import itemgetter

import dateutil.parser
import pytz
import requests
import six
from flask import current_app
from werkzeug.utils import import_string

def utcnow():
    """UTC timestamp (with timezone)."""
    return datetime.now(tz=pytz.utc)


def iso_utcnow():
    """UTC ISO8601 formatted timestamp."""
    return utcnow().isoformat()


def parse_timestamp(x):
    """Parse ISO8601 formatted timestamp."""
    dt = dateutil.parser.parse(x)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.utc)
    return dt

def get_owner(sd, owner):
    """Get owner of object."""
    try:
        u = sd.user(owner)
        name = u.name or u.login
        company = u.company or ''
        return [dict(name=name, affiliation=company)]
    except Exception:
        return None

def obj_or_import_string(value, default=None):
    """Import string or return object.

    :params value: Import path or class object to instantiate.
    :params default: Default object to return if the import fails.
    :returns: The imported object.
    """
    if isinstance(value, six.string_types):
        return import_string(value)
    elif value:
        return value
    return default
