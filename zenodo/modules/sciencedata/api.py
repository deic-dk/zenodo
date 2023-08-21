# -*- coding: utf-8 -*-
#

"""Invenio module that adds ScienceData integration to the platform."""

import json

from flask import current_app
from flask_login import current_user
from invenio_db import db
from invenio_oauthclient.models import RemoteAccount
from invenio_pidstore.proxies import current_pidstore
from mistune import markdown
import requests
from six import string_types
from werkzeug.utils import cached_property, import_string

from .models import ReleaseStatus

class ScienceDataAPI(object):
    """Wrapper for ScienceData API."""

    def __init__(self, user_id=None):
        """Create a ScienceData API object."""
        self.user_id = user_id or current_user.get_id()

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
    def getScienceDataUser(self):
        """Get ID string of ScienceData account with ORCID enabled and matching 'orcid'"""
        orcid = self.orcid
        headers = {'Accept': 'application/json'}
        r = requests.get(current_app.config.get('SCIENCEDATA_PRIVATE_URL')+'/apps/user_orcid/ws/get_user_from_orcid.php?orcid='+orcid, headers=headers, verify=False)
        sciencedata_user = r.text.replace('"', '')
        current_app.logger.warn('sciencedata_user: '+sciencedata_user)
        return sciencedata_user

    @cached_property
    def getGroups(self):
        """Get ID string of ScienceData accound with ORCID enabled and matching 'orcid'"""
        sciencedata_userid = self.getScienceDataUser
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


class ScienceDataRelease(object):
    """A ScienceData release object from a release record. This is a file or a directory,
    identified by a userid, a path and a group."""

    def __init__(self, release, use_sciencedata_metadata=True):
        """Constructor."""
        self.model = release
        self.use_sciencedata_metadata = use_sciencedata_metadata

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
    def release(self):
        """Return release metadata."""
        return self.record_metadata

    @cached_property
    def sciencedata_object(self):
        """Return object metadata."""
        return self.sciencedata_object

    @cached_property
    def title(self):
        """Extract title from a release."""
        name = self.sciencedata_object.get('name')
        version = self.release.get('version')
        return u'{0}: {1}'.format(name, version)

    @cached_property
    def description(self):
        """Extract description from a release."""
        if self.release.get('body'):
            return markdown(self.release['body'])
        elif self.sciencedata_object.get('description'):
            return self.sciencedata_object['description']
        return 'No description provided.'

    @cached_property
    def author(self):
        """The author is the person identified by the ORCID of the logged-in user."""
        return self.sd.orcid

    @cached_property
    def version(self):
        """Extract the vesion from the version string."""
        return self.release.get('version', '')

    @cached_property
    def related_identifiers(self):
        """Yield related identifiers."""
        path = self.sciencedata_object['path']
        # TODO
        yield dict(
            identifier=u'https://sciencedata.dk/{0}/tree/{1}'.format(
                self.repository['full_name'], self.release['tag_name']
            ),
            relation='isSupplementTo',
        )

    @cached_property
    def defaults(self):
        """Return default metadata."""
        return dict(
            access_right='open',
            description=self.description,
            license='other-open',
            publication_date=self.release['published_at'][:10],
            related_identifiers=list(self.related_identifiers),
            version=self.version,
            title=self.title,
            upload_type='dataset',
        )

    @cached_property
    def files(self):
        """Get URL of file/archive to download from ScienceData."""
        version = self.release['version']
        name = self.sciencedata_object['name']
        group = self.sciencedata_object['group']
        path = self.sciencedata_object['path']
        kind = self.sciencedata_object['kind']
        download_url = current_app.config.get('SCIENCEDATA_PRIVATE_URL')+'/download?files='+path
        if kind == 'dir':
            filename = u'{name}-{version}.zip'.format(name=name, version=version)
        else:
            filename = u'{name}-{version}'.format(name=name, version=version)
        sciencedata_username = self.sd.getScienceDataUser
        response = requests.head(download_url, allow_redirects=True, verify=False, auth=(sciencedata_username, ''))

        assert response.status_code == 200, \
            u'Could not retrieve archive from ScienceData: {0}'.format(download_url)

        yield filename, download_url

    @property
    def metadata(self):
        """Return default metadata updated with metadata from ScienceData if present."""
        # Fetch metadata from ScienceData, if present
        headers = {'Accept': 'application/json'}
        path = self.sciencedata_object['path']
        sciencedata_username = self.sd.getScienceDataUser
        r = requests.get(current_app.config.get('SCIENCEDATA_PRIVATE_URL')+'/metadata/getmetadata?files='+path+'&tag=zenodo', headers=headers, allow_redirects=True, verify=False, auth=(sciencedata_username, ''))
        sciencedata_file_metadata = json.loads(r.json())
        output = dict(self.defaults)
        if self.use_sciencedata_metadata:
            output.update(sciencedata_file_metadata)
        return output

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
            fetcher = current_pidstore.fetchers[
                current_app.config.get('SCIENCEDATA_PID_FETCHER')]
            return fetcher(self.record.id, self.record)

    def publish(self):
        """Publish ScienceData file or archive as record."""
        with db.session.begin_nested():
            deposit = self.deposit_class.create(self.metadata)
            deposit['_deposit']['created_by'] = self.sd.user_id
            deposit['_deposit']['owners'] = [self.sd.user_id]

            # Fetch the deposit files
            sciencedata_username = self.sd.getScienceDataUser
            for key, url in self.files:
                response = requests.get(url, allow_redirects=True, auth=(sciencedata_username, ''))
                deposit.files[key] = response.content()
                response.close()

            deposit.publish()
            recid, record = deposit.fetch_published()
            self.model.record_metadata = record.model
