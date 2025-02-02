# -*- coding: utf-8 -*-
#
# This file is part of Zenodo.
# Copyright (C) 2016, 2017 CERN.
#
# Zenodo is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Zenodo is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Zenodo; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Persistent identifier minters."""

from __future__ import absolute_import, print_function, unicode_literals

import idutils
from flask import current_app
from invenio_db import db
from invenio_oaiserver.minters import oaiid_minter
from invenio_pidstore.errors import PIDValueError
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_pidstore.providers.recordid import RecordIdProvider

from zenodo.modules.deposit.minters import zenodo_concept_recid_minter


def doi_generator(recid, prefix=None, suffix=None):
    """Generate a DOI."""
    recid = current_app.config['ZENODO_DOIID4RECID'].get(recid, recid)
    return '{prefix}/{suffix}.{recid}'.format(
        prefix=prefix or current_app.config['PIDSTORE_DATACITE_DOI_PREFIX'],
        suffix=suffix or current_app.config['PIDSTORE_DATACITE_DOI_SUFFIX'],
        recid=recid
    )


def is_local_doi(doi):
    """Check if DOI is a locally managed DOI."""
    prefixes = [
        current_app.config['PIDSTORE_DATACITE_DOI_PREFIX']
    ] + current_app.config['ZENODO_LOCAL_DOI_PREFIXES']
    for p in prefixes:
        if doi.startswith('{0}/'.format(p)):
            return True
    return False


def zenodo_record_minter(record_uuid, data):
    """Zenodo record minter.

    Mint, or register if previously minted, the Concept RECID and RECID.
    Mint the Concept DOI and DOI.
    """
    if 'conceptrecid' not in data:
        zenodo_concept_recid_minter(record_uuid, data)

    if 'recid' in data:
        recid = PersistentIdentifier.get('recid', data['recid'])
        recid.assign('rec', record_uuid)
        recid.register()
    else:
        recid = RecordIdProvider.create(
            object_type='rec', object_uuid=record_uuid).pid
        data['recid'] = int(recid.pid_value)

    zenodo_doi_minter(record_uuid, data)
    oaiid_minter(record_uuid, data)

    if 'conceptdoi' not in data:
        zenodo_concept_doi_minter(record_uuid, data)
    return recid


def zenodo_concept_doi_minter(record_uuid, data):
    """Mint Concept DOI.

    .. note::

        Only Zenodo DOIs are allowed to have a Concept DOI and in general have
        versioning applied.
    """
    doi = data.get('doi')
    assert 'conceptrecid' in data

    # Only mint Concept DOI for Zenodo DOIs
    if is_local_doi(doi):
        conceptdoi = data.get('conceptdoi')

        # Create a DOI if no DOI was found.
        if not conceptdoi:
            conceptdoi = doi_generator(data['conceptrecid'])
            data['conceptdoi'] = conceptdoi

        conceptdoi_pid = (PersistentIdentifier.query
                          .filter_by(pid_type='doi', pid_value=conceptdoi)
                          .one_or_none())
        # Create if not already minted from previous versions
        if not conceptdoi_pid:
            return PersistentIdentifier.create(
                'doi',
                conceptdoi,
                pid_provider='datacite',
                object_type='rec',
                object_uuid=record_uuid,
                status=PIDStatus.RESERVED,
            )
        else:
            # Update to point to latest record
            conceptdoi_pid.assign(
                object_type='rec',
                object_uuid=record_uuid,
                overwrite=True,
            )
            return conceptdoi_pid


def zenodo_doi_minter(record_uuid, data):
    """Mint DOI."""
    doi = data.get('doi')
    assert 'recid' in data

    # Create a DOI if no DOI was found.
    if not doi:
        doi = doi_generator(data['recid'])
        data['doi'] = doi

    # Make sure it's a proper DOI
    assert idutils.is_doi(doi)

    # user-provided DOI (external or Zenodo DOI)
    if doi != doi_generator(data['recid']):
        if is_local_doi(doi):
            # User should not provide a custom Zenodo DOI
            # which is not dependent on the recid
            raise PIDValueError('doi', doi)
        else:
            return PersistentIdentifier.create(
                'doi',
                doi,
                object_type='rec',
                object_uuid=record_uuid,
                status=PIDStatus.RESERVED,
            )
    else:  # Zenodo-generated DOI
        return PersistentIdentifier.create(
            'doi',
            doi,
            pid_provider='datacite',
            object_type='rec',
            object_uuid=record_uuid,
            status=PIDStatus.RESERVED,
        )


def zenodo_doi_updater(record_uuid, data):
    """Update the DOI (only external DOIs)."""
    assert 'recid' in data
    doi = data.get('doi')
    assert doi
    assert idutils.is_doi(doi)

    # If the DOI is the same as an already generated one, do nothing
    if doi == doi_generator(data['recid']):
        return
    if is_local_doi(doi):  # Zenodo DOI, but different than recid
        # ERROR, user provided a custom ZENODO DOI!
        raise PIDValueError('doi', doi)

    doi_pid = PersistentIdentifier.get_by_object(
        pid_type='doi', object_type='rec', object_uuid=record_uuid)

    if doi_pid.pid_value != doi:
        with db.session.begin_nested():
            db.session.delete(doi_pid)
            return PersistentIdentifier.create(
                'doi',
                doi,
                object_type='rec',
                object_uuid=record_uuid,
                status=PIDStatus.RESERVED,
            )
