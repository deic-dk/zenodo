# -*- coding: utf-8 -*-
#
# This file is part of Zenodo.
# Copyright (C) 2015 CERN.
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

"""Record minters."""

from __future__ import absolute_import, print_function, unicode_literals

from zenodo.modules.records.minters import doi_generator


def test_doi_generator(app):
    """Test doi_generator."""
    p = app.config['PIDSTORE_DATACITE_DOI_PREFIX']
    # Check normal generation.
    assert doi_generator(1234, 'zenodo') == '{prefix}/zenodo.1234'.format(prefix=p)
    # Check doi id for recid mapping
    assert doi_generator(7468, 'zenodo') == '{prefix}/zenodo.7448'.format(prefix=p)
