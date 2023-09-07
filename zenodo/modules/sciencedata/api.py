# -*- coding: utf-8 -*-
#

"""Invenio module that adds ScienceData integration to the platform."""

import json
import datetime
import re
import os
import uuid
import urllib

from flask import current_app
from flask_login import current_user

from invenio_db import db
from invenio_files_rest.models import ObjectVersion
from invenio_oauthclient.models import RemoteAccount
from invenio_accounts.models import User
from invenio_userprofiles.models import UserProfile
from invenio_pidstore.proxies import current_pidstore
from invenio_records.api import Record
from invenio_indexer.api import RecordIndexer
from invenio_pidrelations.contrib.versioning import PIDVersioning
from invenio_pidstore.models import PersistentIdentifier

import requests
from six import string_types
from werkzeug.utils import cached_property, import_string

from zenodo.modules.deposit.api import ZenodoDeposit
from zenodo.modules.deposit.tasks import datacite_register
from zenodo.modules.records.api import ZenodoRecord

from .models import Release
from .models import ReleaseStatus

from ..deposit.loaders import legacyjson_v1_translator
from ..jsonschemas.utils import current_jsonschemas

class ScienceDataAPI(object):
    """Wrapper for ScienceData API."""

    def __init__(self, user_id=None):
        """Create a ScienceData API object."""
        user_id = user_id or current_user.get_id()
        self.user_id = int(user_id)

    @cached_property
    def orcid(self):
        """Get our ORCID string"""
        orcid_app_key = current_app.config['ORCID_APP_CREDENTIALS']['consumer_key']
        accounts = RemoteAccount.query.filter_by(user_id=self.user_id).all()
        for a in accounts:
            if a.client_id == orcid_app_key:
                current_app.logger.warn('extra_data '+format(a.extra_data))
                orcid = a.extra_data['orcid']
                return orcid
                """Return ORCID string of logged-in user, if present."""
        return ""

    @cached_property
    def scienceDataUser(self):
        """Get ID string of ScienceData account with ORCID enabled and matching 'orcid'"""
        orcid = self.orcid
        headers = {'Accept': 'application/json'}
        r = requests.get(current_app.config.get('SCIENCEDATA_PRIVATE_URL')+'/apps/user_orcid/ws/get_user_from_orcid.php?orcid='+orcid, headers=headers, verify=False)
        sciencedata_user = r.text.replace('"', '')
        current_app.logger.warn('sciencedata_user: '+sciencedata_user)
        return sciencedata_user

    @cached_property
    def getGroups(self):
        """Get groups the current user is member of"""
        sciencedata_userid = self.scienceDataUser
        if not sciencedata_userid:
            return []
        headers = {'Accept': 'application/json'}
        r = requests.get(current_app.config.get('SCIENCEDATA_PRIVATE_URL')+'/apps/user_group_admin/ws/getUserGroups.php?onlyOwned=no&userid='+sciencedata_userid, headers=headers, verify=False)
        try:
            groupsData = r.json()
        except ValueError as e:
            groupsData = []
        groups = [group['gid'] for group in groupsData]
        return groups

    @cached_property
    def scienceDataPrivateHomeURL(self):
        """Get the https://10.2.0.x/ URL of the home server of the current user"""
        masterPrivateURL = current_app.config['SCIENCEDATA_PRIVATE_URL']
        sciencedata_username = self.scienceDataUser
        r = requests.request('GET', masterPrivateURL.rstrip('/')+'/files/', allow_redirects=False, verify=False, auth=(sciencedata_username, ''))
        current_app.logger.warn('status '+format(r.status_code))
        if r.status_code == 307:
            filesLocation = r.headers['location']
            url = re.sub(r"/+files/*", "/", filesLocation)
            return url
        return masterPrivateURL.rstrip('/')+'/'

    def getScienceDataPublicURL(self, path, group):
        """Get public url of object - if object has been shared publicly"""
        sciencedata_userid = self.scienceDataUser
        if not sciencedata_userid:
            return ''
        try:
            r = requests.get(current_app.config.get('SCIENCEDATA_PRIVATE_URL')+'/apps/files_zenodo/get_public_url.php?path='+path+'&group='+group, verify=False, auth=(sciencedata_userid, ''))
            url = r.json()
            current_app.logger.warn('sciencedata url: '+url)
        except ValueError as e:
            url = ''
        return url


class ScienceDataRelease(object):
    """A ScienceData release object from ScienceDataObject and Release DB objects"""

    def __init__(self, sciencedata_object, sciencedata_relase):
        """Constructor."""
        self.sciencedata_object = sciencedata_object
        self.model = sciencedata_relase

    @cached_property
    def sd(self):
        """Return ScienceDataAPI object."""
        return ScienceDataAPI()

    @cached_property
    def deposit_class(self):
        """Return a class implementing `publish` method."""
        cls = current_app.config['SCIENCEDATA_DEPOSIT_CLASS']
        if isinstance(cls, string_types):
            cls = import_string(cls)
        assert isinstance(cls, type)
        return cls

    @cached_property
    def related_identifiers(self):
        """Yield related identifiers."""
        sciencedata_url = self.sd.getScienceDataPublicURL(self.sciencedata_object.path, self.sciencedata_object.group)
        if sciencedata_url and sciencedata_url != '':
            current_app.logger.warn('sciencedata url: '+sciencedata_url)
            yield dict(
                identifier=sciencedata_url,
                relation='isSupplementTo',
            )


    @cached_property
    def defaults(self):
        """Return default metadata."""
        today = datetime.date.today().strftime("%Y-%m-%dT%H:%M:%SZ")
        return dict(
            access_right='open',
            description='Dataset from ScienceData',
            license='other-open',
            publication_date=today[:10],
            related_identifiers=list(self.related_identifiers),
            version=self.version,
            title=self.title,
            upload_type='dataset',
        )

    @property
    def metadata(self):
        """Return default metadata updated with metadata from previous version or from ScienceData - if available."""
        output = dict(self.defaults)
        latest_release = self.sciencedata_object.latest_release()
        # If this is a new version of an already published object, reuse metadata
        if latest_release.record_id:
            latest_record = Record.get_record(latest_release.record_id)
            metadata_json = latest_record['json']
            metadata = json.loads(metadata_json)
            if metadata:
                output.update(metadata)
        else:
            # Othersise try to fetch metadata from ScienceData
            headers = {'Accept': 'application/json'}
            path = self.sciencedata_object.path
            sciencedata_username = self.sd.scienceDataUser
            home_server_url = self.sd.scienceDataPrivateHomeURL
            r = requests.get(home_server_url+'metadata/getmetadata?files=%5B%22'+urllib.quote_plus(path)+'%22%5D&tag=Zenodo', headers=headers, allow_redirects=True, verify=False, auth=(sciencedata_username, ''))
            if r.status_code >= 400:
                current_app.logger.error('could not get metadata from sciencedata')
            else:
                sciencedata_ret = r.json()
                if sciencedata_ret:
                    current_app.logger.warn('got json: '+format(sciencedata_ret))
                    sd_vals = next(el for el in sciencedata_ret.values())
                    sd_tag = next(tag for tag in sd_vals['filetags'].values())
                    if sd_tag['metadata']:
                        
                        
                        
                        
                        sd_tag['metadata'].pop('uploaded', None)
                        sd_tag['metadata'].pop('bucket', None)
                        sd_tag['metadata'].pop('deposition_id', None)
                        sd_tag['metadata'].pop('url', None)
                        output.update(sd_tag['metadata'])
        # Add creators if not specified
        if ( 'creators' not in output or not output['creators'] ):
            if self.author:
                output['creators'] = [self.author]
            elif self.fullname:
                output['creators'] = [dict(name=self.fullname, affiliation='')]
        if not output['creators']:
            output['creators'] = [dict(name='Unknown', affiliation='')]
        return legacyjson_v1_translator({'metadata': output})

    @cached_property
    def files(self):
        """Get URL of file/archive to download from ScienceData."""
        version = self.version
        name = os.path.basename(self.sciencedata_object.path)
        group = self.sciencedata_object.group
        path = self.sciencedata_object.path
        kind = self.sciencedata_object.kind
        home_server_url = self.sd.scienceDataPrivateHomeURL
        file_name = os.path.basename(path)
        dir_name = os.path.dirname(path)
        download_url = home_server_url.rstrip('/')+'/download?internal=1&group='+group+'&dir='+dir_name+'&files='+file_name
        if kind == 'dir':
            filename = u'{name}.zip'.format(name=name, version=version)
        else:
            filename = u'{name}'.format(name=name, version=version)
        sciencedata_username = self.sd.scienceDataUser
        response = requests.head(download_url, allow_redirects=True, verify=False, auth=(sciencedata_username, ''))
        assert response.status_code == 200, \
            u'Could not retrieve archive from ScienceData: {0}'.format(download_url)

        yield filename, download_url

    @cached_property
    def record(self):
        """Get Release record."""
        return self.model.record

    @cached_property
    def status(self):
        """Get the release status."""
        return self.model.status

    @cached_property
    def pid(self):
        """Get PID object for the Release record."""
        if self.model.status == ReleaseStatus.PUBLISHED and self.record:
            current_app.logger.warn('fetching PID, '+format(self.record.id)+':'+format(self.record))
            fetcher = current_pidstore.fetchers[
                current_app.config.get('SCIENCEDATA_PID_FETCHER')]
            return fetcher(self.record.id, self.record)

    @cached_property
    def fullname(self):
        """Get full name of current user."""
        row = UserProfile.query.filter_by(user_id=self.sd.user_id).one()
        return row.full_name

    @cached_property
    def email(self):
        """Get email of current user."""
        row = User.query.filter_by(id=self.sd.user_id).one()
        return row.email

    @cached_property
    def author(self):
        """The available data on the current user."""
        domain = self.email.split('@')[1]
        return dict(name=self.fullname, affiliation=domain, orcid=self.sd.orcid)

    @cached_property
    def title(self):
        """Extract title from previouw release or generate one."""
        latest_release = self.sciencedata_object.latest_release()
        if latest_release.record_id:
            latest_record = Record.get_record(latest_release.record_id)
            return latest_record.title
        name = self.sciencedata_object.name
        #return u'{0}-v{1}'.format(name, self.version)
        return name

    @cached_property
    def version(self):
        """Return version."""
        if self.model is None:
            return 0
        return self.model.version
        #latest_release = self.sciencedata_object.latest_release()
        #latest_version = 0
        #if latest_release and latest_release.version:
        #    latest_version = int(latest_release.version)
        #current_app.logger.warn('version '+format(latest_release)+':'+str(latest_version))
        #latest_version = latest_version + 1
        #return str(latest_version)

    def publish(self):
        """Publish ScienceData object as record."""
        id_ = uuid.uuid4()
        deposit_metadata = dict(self.metadata)
        deposit = None
        try:
            db.session.begin_nested()
            current_app.logger.warn('metadata '+format(deposit_metadata))
            previous_releases = self.model.sciencedata_object.releases.filter_by(
                status=ReleaseStatus.PUBLISHED)
            versioning = None
            stashed_draft_child = None
            if previous_releases.count():
                last_release = previous_releases.order_by(
                        Release.created.desc()).first()
                last_recid = PersistentIdentifier.get(
                    'recid', last_release.record['recid'])
                versioning = PIDVersioning(child=last_recid)
                last_record = ZenodoRecord.get_record(
                    versioning.last_child.object_uuid)
                deposit_metadata['conceptrecid'] = last_record['conceptrecid']
                if 'conceptdoi' not in last_record:
                    last_depid = PersistentIdentifier.get(
                        'depid', last_record['_deposit']['id'])
                    last_deposit = ZenodoDeposit.get_record(
                        last_depid.object_uuid)
                    last_deposit = last_deposit.registerconceptdoi()
                    last_recid, last_record = last_deposit.fetch_published()
                deposit_metadata['conceptdoi'] = last_record['conceptdoi']
                if last_record.get('communities'):
                    deposit_metadata.setdefault('communities',
                                                last_record['communities'])
                if versioning.draft_child:
                    stashed_draft_child = versioning.draft_child
                    versioning.remove_draft_child()

            deposit = self.deposit_class.create(deposit_metadata, id_=id_)
            deposit['_deposit']['created_by'] = self.sd.user_id
            deposit['_deposit']['owners'] = [self.sd.user_id]

            # Fetch the deposit files
            sciencedata_username = self.sd.scienceDataUser
            for key, url in self.files:
                with requests.get(url, allow_redirects=True, stream=True, verify=False, auth=(sciencedata_username, '')) as r:
                    #deposit.files[key] = r.raw
                    current_app.logger.warn('got file '+format(key)+':'+url+':'+str(r.status_code)+':'+format(r.headers))

                    size = int(r.headers.get('Content-Length', 0))
                    ObjectVersion.create(
                        bucket=deposit.files.bucket,
                        key=key,
                        stream=r.raw,
                        size=size or None,
                        mimetype=r.headers.get('Content-Type'),
                    )

            # ScienceData-specific SIP store agent
            sip_agent = {
                '$schema': current_jsonschemas.path_to_url(
                    current_app.config['SIPSTORE_SCIENCEDATA_AGENT_JSONSCHEMA']),
                'user_id': self.sd.user_id,
                'sciencedata_id': sciencedata_username,
                'email': self.email,
            }
            deposit.publish(
                user_id=self.sd.user_id, sip_agent=sip_agent,
                spam_check=False)
            recid_pid, record = deposit.fetch_published()
            self.model.record_metadata = record.model
            if versioning and stashed_draft_child:
                versioning.insert_draft_child(stashed_draft_child)
            record_id = str(record.id)
            ##
            self.model.version = self.version
            self.model.status = ReleaseStatus.PUBLISHED
            ##
            db.session.commit()

            # Send Datacite DOI registration task
            if current_app.config['DEPOSIT_DATACITE_MINTING_ENABLED']:
                datacite_register.delay(recid_pid.pid_value, record_id)

            # Index the record
            RecordIndexer().index_by_id(record_id)
        except Exception:
            db.session.rollback()
            # Remove deposit from index since it was not commited.
            if deposit and deposit.id:
                try:
                    RecordIndexer().delete(deposit)
                except Exception:
                    current_app.logger.exception(
                        "Failed to remove uncommited deposit from index.")
            raise
