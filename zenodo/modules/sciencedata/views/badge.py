# -*- coding: utf-8 -*-
#

"""DOI Badge Blueprint."""

from __future__ import absolute_import

from flask import Blueprint, abort, redirect, url_for

from ..api import ScienceDataRelease
from ..models import ReleaseStatus, ScienceDataObject

blueprint = Blueprint(
    'sciencedata_badge',
    __name__,
    url_prefix='/badge',
    static_folder='../static',
    template_folder='../templates',
)


def get_pid_of_latest_release_or_404(**kwargs):
    """Return PID of the latest release."""
    sciencedata_object = ScienceDataObject.query.filter_by(**kwargs).first_or_404()
    release = sciencedata_object.latest_release(ReleaseStatus.PUBLISHED)
    if release:
        return ScienceDataRelease(release).pid
    abort(404)


def get_badge_image_url(pid, ext='svg'):
    """Return the badge for a DOI."""
    return url_for('invenio_formatter_badges.badge',
                   title=pid.pid_type, value=pid.pid_value, ext=ext)


def get_doi_url(pid):
    """Return the badge for a DOI."""
    return 'https://doi.org/{pid.pid_value}'.format(pid=pid)


#
# Views
#


@blueprint.route('/<int:user_id>/<path:path>.svg')
def index(user_id, path):
    """Generate a badge for a ScienceData file or folder."""
    pid = get_pid_of_latest_release_or_404(path=path)
    return redirect(get_badge_image_url(pid))



@blueprint.route('/latestdoi/<int:user_id>/<path:path>')
def latest_doi(user_id, path):
    """Redirect to the newest record version."""
    pid = get_pid_of_latest_release_or_404(path=path)
    return redirect(get_doi_url(pid))
