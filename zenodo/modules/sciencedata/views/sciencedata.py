# -*- coding: utf-8 -*-
#

"""ScienceData blueprint for Invenio platform."""

from __future__ import absolute_import

import os
import json
from datetime import datetime

import humanize
import pytz
from dateutil.parser import parse
from flask import Blueprint, abort, current_app, render_template, \
    request, Response, redirect, url_for
from flask_babelex import gettext as _
from flask_breadcrumbs import register_breadcrumb
from flask_login import current_user, login_required
from flask_menu import register_menu
from flask import jsonify
from invenio_db import db
from sqlalchemy.orm.exc import NoResultFound
import urllib
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import requests

from ..api import ScienceDataAPI, ScienceDataRelease
from ..models import Release, ScienceDataObject
from ..errors import AccessError, NoORCIDError, MultipleORCIDAccountsError, NoORCIDAccountError
from ..proxies import current_sciencedata


blueprint = Blueprint(
    'sciencedata',
    __name__,
    static_folder='../static',
    template_folder='../templates',
    url_prefix='/account/settings/sciencedata',
)

def getPreservedObjects():
    """Get list (dictionary) of already preserved paths on ScienceData."""
        # Generate the ScienceData preserved objects view object
    sd_objects = {}
    db_sciencedata_objects = ScienceDataObject.query.filter_by().all()
    for sd_object in db_sciencedata_objects:
        current_app.logger.warn('getting '+format(sd_object))
        sd_objects[str(sd_object.id)] = {'instance': sd_object,
                                         'latest': ScienceDataRelease(sd_object, sd_object.latest_release())}
    return sd_objects.items()

def getScienceDataUser():
    """Get list ScienceData user with an attached ORCID matching the ORCID of the logged-in user, if a such exists."""
    sciencedata = ScienceDataAPI(user_id=current_user.id)
    orcid = sciencedata.orcid
    if orcid == "":
        raise NoORCIDError()
    sciencedata_user = sciencedata.scienceDataUser
    if sciencedata_user == False:
        raise MultipleORCIDAccountsError(orcid=orcid)
    if not sciencedata_user or sciencedata_user == "":
        raise NoORCIDAccountError(orcid=orcid)
    return sciencedata_user

def getScienceDataGroups():
    """Get list of ScienceData groups."""
    sciencedata = ScienceDataAPI(user_id=current_user.id)
    sciencedata_groups = sciencedata.getGroups
    return sciencedata_groups

#
# Template filters
#
@blueprint.app_template_filter('naturaltime')
def naturaltime(val):
    """Get humanized version of time."""
    val = val.replace(tzinfo=pytz.utc) \
        if isinstance(val, datetime) else parse(val)
    now = datetime.utcnow().replace(tzinfo=pytz.utc)
    return humanize.naturaltime(now - val)


@blueprint.app_template_filter('prettyjson')
def prettyjson(val):
    """Get pretty-printed json."""
    return json.dumps(json.loads(val), indent=4)

@blueprint.app_template_filter('release_pid')
def release_pid(release):
    """Get PID of Release record."""
    sd_object = ScienceDataObject.get(release.sciencedata_object_id)
    return ScienceDataRelease(sd_object, release).pid

@blueprint.app_template_filter('basename')
def basename(path):
    """Get basename of path."""
    return os.path.basename(path)

@blueprint.app_template_filter('dirname')
def dirname(path):
    """Get dirname of path."""
    return os.path.dirname(path)

@blueprint.app_template_filter('stripslashes')
def stripslashes(path):
    """Strip slashes from beginning and end of path."""
    return path.strip('/')

@blueprint.app_template_filter('escapequotes')
def escapequotes(text):
    """escape single quotes."""
    return text.replace("'", "\\'")


@blueprint.app_template_filter('urlencode')
def urlencode(text):
    """URL encode str."""
    return urllib.quote_plus(text)


#
# Views
#
@blueprint.route('/', methods=["GET", "POST"])
@login_required
@register_breadcrumb(blueprint, 'breadcrumbs.settings.sciencedata', _('ScienceData'))
@register_menu(
    blueprint, 'settings.sciencedata',
    '<i class="fa fa-sciencedata fa-fw"></i> ScienceData',
    order=10,
    active_when=lambda: request.endpoint.startswith('sciencedata.')
)
def index():
    """Display list of the user's preserved directories and files."""
    sciencedata_user = ""
    message = ""
    try:
        sciencedata_user = getScienceDataUser()
    except NoORCIDAccountError as e:
        pass
    except MultipleORCIDAccountsError as e:
        message = "An ORCID must only be attached to one ScienceData account. "+e.message
    except NoORCIDError as e:
        message = "You need to attach an ORCID to access ScienceData. " + e.message
    # Generate the ScienceData preserved objects view object
    sd_objects = getPreservedObjects()
    sd_groups = getScienceDataGroups()

    return render_template(current_app.config['SCIENCEDATA_TEMPLATE_INDEX'], sciencedata_user=sciencedata_user, sd_objects=sd_objects, sd_groups=sd_groups, message=message)

@blueprint.route('/sciencedataobject/<path:path>', methods=["GET", 'POST'])
@login_required
@register_breadcrumb(blueprint, 'breadcrumbs.settings.sciencedata.sd_object',
                     _('Asset'))
def sciencedataobject(path):
    """Display selected preserved object."""
    group = request.args['group']
    user_id = current_user.id
    sd_objects = getPreservedObjects()
    sd_object = next((sd_object for sd_object_id, sd_object in sd_objects
                  if sd_object['instance'].user_id == user_id and sd_object['instance'].path == '/'+path.lstrip('/') and sd_object['instance'].group == group), {})
    if not sd_object:
        sdo = next(sd_object for sd_object_id, sd_object in sd_objects)
        current_app.logger.warn('not found '+format(sdo['instance'].user_id)+':'+path+':'+format(sdo['instance'].path)+':'+group+':'+format(sdo['instance'].group))
        abort(404)
    sd_object_instance = sd_object['instance']
    current_app.logger.warn('found '+format(sd_object_instance.user_id)+':'+path+':'+format(sd_object_instance.path)+':'+group+':'+format(sd_object_instance.group))
    releases = [
        ScienceDataRelease(sd_object['instance'], r) for r in (
            sd_object_instance.releases.order_by(db.desc(Release.created)).all()
            if sd_object_instance.id else []
        )
    ]
    return render_template(
        current_app.config['SCIENCEDATA_TEMPLATE_VIEW'],
        sd_object=sd_object_instance,
        sd_object_info=sd_object,
        releases=releases,
        user_id=int(user_id),
        path='/'+path.lstrip('/'),
        group=group,
        serializer=current_sciencedata.record_serializer,
    )

@blueprint.route('/sciencedataobject_by_id/<string:sciencedata_object_id>', methods=["GET", 'POST'])
@login_required
@register_breadcrumb(blueprint, 'breadcrumbs.settings.sciencedata.sd_object',
                     _('Asset'))
def sciencedataobject_by_id(sciencedata_object_id):
    """Display selected preserved object."""
    user_id = current_user.id
    sd_objects = getPreservedObjects()
    sd_object = next((sd_object for sd_object_id, sd_object in sd_objects
                  if sd_object['instance'].user_id == user_id and sd_object_id == sciencedata_object_id), {})
    if not sd_object:
        sdo = next(sd_object for sd_object_id, sd_object in sd_objects)
        current_app.logger.warn('not found '+':'+format(sdo['instance'].id)+':'+sciencedata_object_id+':')
        abort(404)
    sd_object_instance = sd_object['instance']
    releases = [
        ScienceDataRelease(sd_object['instance'], r) for r in (
            sd_object_instance.releases.order_by(db.desc(Release.created)).all()
            if sd_object_instance.id else []
        )
    ]
    return render_template(
        current_app.config['SCIENCEDATA_TEMPLATE_VIEW'],
        sd_object=sd_object_instance,
        sd_object_info=sd_object,
        releases=releases,
        user_id=int(user_id),
        path=sd_object['instance'].path,
        group=sd_object['instance'].group,
        serializer=current_sciencedata.record_serializer,
    )

@blueprint.route('/add', methods=["GET", "POST"])
@login_required
def add_sciencedata_object_url():
    """Create entry for path in DB."""
    path = request.args['path']
    name = request.args['name']
    kind = request.args['kind']
    group = request.args['group']
    current_app.logger.warn('creating '+request.method+' '+format(current_user.id)+':'+format(path)+':'+format(name)+':'+format(kind)+':'+format(group))
    sd_object = ScienceDataObject.enable(current_user.id, path, name, kind, group)
    db.session.commit()
    return render_template(
        current_app.config['SCIENCEDATA_TEMPLATE_VIEW'],
        sd_object=sd_object,
        xhr=True,
        releases=[],
        serializer=current_sciencedata.record_serializer,
    )

@blueprint.route('/create_version', methods=["GET", "POST"])
@login_required
def create_version():
    """Create new deposit or new version of deposit."""
    path = request.args['path']
    group = request.args['group']
    user_id = current_user.id
    sd_objects = getPreservedObjects()
    sdo = next((sd_object for sd_object_id, sd_object in sd_objects
                  if sd_object['instance'].user_id == user_id and sd_object['instance'].path == path and sd_object['instance'].group == group), {})
    if not sdo:
        sdo = next(sd_object for sd_object_id, sd_object in sd_objects)
        current_app.logger.warn('not found '+':'+format(sdo['instance'].path)+':'+format(path)+':'+format(sdo['instance'].group)+':'+format(group)+':'+format(sdo['instance'].user_id)+':'+format(user_id))
        abort(404)
    new_version = 1
    if sdo['latest'] is not None:
        latest_version = int(sdo['latest'].version)
        if latest_version:
            new_version = latest_version+1
    current_app.logger.warn('creating '+request.method+' '+format(user_id)+':'+format(path)+':'+format(group)+':'+format(new_version))
    sd_release = Release.create(sdo['instance'], str(new_version))
    sciencedata_release = ScienceDataRelease(sdo['instance'], sd_release)
    sciencedata_release.publish()
    db.session.commit()
    return jsonify({"status": "success"})

@blueprint.route('/remove_object', methods=["GET", "POST"])
@login_required
def remove_object():
    """"Remove entry for path in DB."""
    sciencedata_object_id = request.args['sciencedata_object_id']
    user_id = current_user.id
    sd_objects = getPreservedObjects()
    sd_object = next((sd_object for sd_object_id, sd_object in sd_objects
                  if sd_object['instance'].user_id == user_id and sd_object_id == sciencedata_object_id), {})
    if not sd_object:
        sdo = next(sd_object for sd_object_id, sd_object in sd_objects)
        current_app.logger.warn('not found '+':'+format(sdo['instance'].id)+':'+sciencedata_object_id+':')
        abort(404)
    releases = [
        r for r in (
            sd_object['instance'].releases.order_by(db.desc(Release.created)).all()
            if sd_object['instance'].id else []
        )
    ]
    for r in releases:
        Release.delete(r)
    ScienceDataObject.delete(sd_object['instance'])
    db.session.commit()
    return ""

sciencedata_username = ""

@blueprint.route('/sciencedata_proxy/<path:path>', methods=["GET", "POST"])
@blueprint.route('/sciencedata_proxy/', methods=["GET", "POST"])
@blueprint.route('/sciencedata_proxy', methods=["GET", "POST"])
@login_required
def sciencedata_proxy(path="/"):
    """Fetches the specified ScienceData path and serves it to the client."""
    global sciencedata_username
    current_app.logger.warn('fetching '+request.method+' '+format(path))
    if not sciencedata_username:
        sciencedata_username = getScienceDataUser()
    sciencedata_private_ip = urlparse(current_app.config['SCIENCEDATA_PRIVATE_URL']).hostname
    headers = dict(request.headers)
    headers['Host'] = str(sciencedata_private_ip)
    r = requests.request(request.method, current_app.config['SCIENCEDATA_PRIVATE_URL']+path, params=request.args, stream=True, headers=headers, allow_redirects=False, verify=False, auth=(sciencedata_username, ''))
    current_app.logger.warn('status '+format(r.status_code))
    if r.status_code == 307:
        redirect_url = r.headers['location']
        current_app.logger.warn('now trying '+format(redirect_url))
        sciencedata_private_ip = urlparse(redirect_url).hostname
        headers['Host'] = str(sciencedata_private_ip)
        r = requests.request(request.method, redirect_url, params=request.args, stream=True, headers=headers, allow_redirects=False, verify=False, auth=(sciencedata_username, ''))
    #headers = dict(r.raw.headers)
    ret_content = r.content.replace('href="', 'href="/account/settings/sciencedata/sciencedata_proxy').replace('src="', 'src="/account/settings/sciencedata/sciencedata_proxy')
    current_app.logger.debug('got '+format(ret_content))
    out = Response(ret_content)
    return out


#
# Badge views
#
@blueprint.route('/badge/<path:doi>.svg')
def badge(doi, ext='svg'):
    """Generate a badge for a ScienceData file or folder."""
    #pid = get_pid_of_latest_release_or_404(user_id=user_id, path=path, group=group)
    doi = doi.replace('-', '/')
    url = url_for('invenio_formatter_badges.badge', title='doi', value=doi, ext=ext)
    return redirect(url)

@blueprint.route('/doi/<path:doi>')
def doi(pid):
    """Redirect to the newest record version."""
    #pid = get_pid_of_latest_release_or_404(user_id=user_id, path=path, group=group)
    doi = doi.replace('-', '/')
    return redirect('https://doi.org/{doi}'.format(doi=pid))

