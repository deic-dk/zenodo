# -*- coding: utf-8 -*-
#

"""Models for ScienceData integration."""

from __future__ import absolute_import

import uuid
from enum import Enum

from flask import current_app
from flask_babelex import lazy_gettext as _
from invenio_accounts.models import User
from invenio_db import db
from invenio_records.api import Record
from invenio_records.models import RecordMetadata
from sqlalchemy import and_
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy_utils.models import Timestamp
from sqlalchemy_utils.types import ChoiceType, JSONType, UUIDType

from .errors import AccessError

RELEASE_STATUS_TITLES = {
    'RECEIVED': _('Received'),
    'PROCESSING': _('Processing'),
    'PUBLISHED': _('Published'),
    'FAILED': _('Failed'),
    'DELETED': _('Deleted'),
}

RELEASE_STATUS_ICON = {
    'RECEIVED': 'fa-spinner',
    'PROCESSING': 'fa-spinner',
    'PUBLISHED': 'fa-check',
    'FAILED': 'fa-times',
    'DELETED': 'fa-times',
}

RELEASE_STATUS_COLOR = {
    'RECEIVED': 'default',
    'PROCESSING': 'default',
    'PUBLISHED': 'success',
    'FAILED': 'danger',
    'DELETED': 'danger',
}


class ReleaseStatus(Enum):
    """Constants for possible status of a Release."""

    __order__ = 'RECEIVED PROCESSING PUBLISHED FAILED DELETED'

    RECEIVED = 'R'
    """Release has been received and is pending processing."""

    PROCESSING = 'P'
    """Release is still being processed."""

    PUBLISHED = 'D'
    """Release was successfully processed and published."""

    FAILED = 'F'
    """Release processing has failed."""

    DELETED = 'E'
    """Release has been deleted."""

    def __init__(self, value):
        """Hack."""

    def __eq__(self, other):
        """Equality test."""
        return self.value == other

    def __str__(self):
        """Return its value."""
        return self.value

    @property
    def title(self):
        """Return human readable title."""
        return RELEASE_STATUS_TITLES[self.name]

    @property
    def icon(self):
        """Font Awesome status icon."""
        return RELEASE_STATUS_ICON[self.name]

    @property
    def color(self):
        """UI status color."""
        return RELEASE_STATUS_COLOR[self.name]


class ScienceDataObject(db.Model, Timestamp):
    """Information about a ScienceData file or folder."""

    __tablename__ = 'sciencedata_objects'

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid.uuid4,
    )
    """Object identifier."""

    path = db.Column(db.String(255), index=True, nullable=False)
    """Fully qualified name of the file or folder, including user."""

    name = db.Column(db.String(255), nullable=False)
    """Name of the file or folder."""

    kind = db.Column(db.String(255))
    """'file' or 'folder'."""

    group  = db.Column(db.String(255))
    """Possible ScienceData group."""

    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    """Invenio user ID."""

    #
    # Relationships
    #
    user = db.relationship(User)

    @classmethod
    def enable(cls, user_id, path, name, kind=None, group=None):
        """Enable object.
        """
        try:
            sdObject = cls.get(user_id=user_id, path=path, group=group)
        except NoResultFound:
            sdObject = cls.create(user_id=user_id, path=path, name=name, kind=kind, group=group)
        sdObject.user_id = user_id
        return sdObject

    @classmethod
    def delete(cls, sd_object):
        """Delete object.
        """
        with db.session.begin_nested():
            return db.session.delete(sd_object)

    @classmethod
    def create(cls, user_id, path=None, name=None, kind=None, group=None, **kwargs):
        """Create the object."""
        with db.session.begin_nested():
            obj = cls(user_id=user_id, path=path, name=name, kind=kind, group=group, **kwargs)
            db.session.add(obj)
            current_app.logger.warn('created '+format(user_id)+':'+format(path)+':'+format(name)+':'+format(kind)+':'+format(group)+':'+format(obj))
        return obj

    @classmethod
    def get(cls, user_id, path, group):
        """Return a ScienceData object.

        :param integer user_id: User identifier.
        :param integer path: ScienceData object path.
        :param integer group: ScienceData object group.
        :returns: ScienceData object.
        :raises: :py:exc:`~sqlalchemy.orm.exc.NoResultFound`: if the path
                 doesn't exist.
        :raises: :py:exc:`AccessError`: if the path cannot be accessed.
        """
        path = '/'+path
        group = '' if group==None else group
        current_app.logger.warn('getting '+format(user_id)+':'+format(path)+':'+format(group))
        sciencedata_object = cls.query.filter(and_(ScienceDataObject.user_id == user_id, ScienceDataObject.path == path, ScienceDataObject.group == group)).one()
        if (sciencedata_object and sciencedata_object.user_id and sciencedata_object.user_id != user_id):
            raise AccessError(user=user_id, path=path)
        return sciencedata_object

    def latest_release(self, status=None):
        """Chronologically latest published release of the object (path)."""
        # Bail out fast if object not in DB session.
        if self not in db.session:
            return None
        q = self.releases if status is None else self.releases.filter_by(status=status)
        return q.order_by(db.desc(Release.created)).first()

    def __repr__(self):
        """Get object representation."""
        return u'<Object {self.path}>'.format(self=self)


class Release(db.Model, Timestamp):
    """Information about a ScienceData release."""

    __tablename__ = 'sciencedata_releases'

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid.uuid4,
    )
    """Release identifier."""

    version = db.Column(db.String(255))
    """Release version."""

    errors = db.Column(
        JSONType().with_variant(
            postgresql.JSON(none_as_null=True),
            'postgresql',
        ),
        nullable=True,
    )
    """Release processing errors."""

    sciencedata_object_id = db.Column(UUIDType, db.ForeignKey(ScienceDataObject.id))
    """ScienceDataObject identifier."""

    record_id = db.Column(
        UUIDType,
        db.ForeignKey(RecordMetadata.id),
        nullable=True,
    )
    """Record identifier."""

    status = db.Column(
        ChoiceType(ReleaseStatus, impl=db.CHAR(1)),
        nullable=False,
    )
    """Status of the release, e.g. 'processing', 'published', 'failed', etc."""

    sciencedata_object = db.relationship(ScienceDataObject, backref=db.backref('releases', lazy='dynamic'))

    record_metadata = db.relationship(RecordMetadata, backref='sciencedata_releases')

    @classmethod
    def create(cls, sciencedata_object, version):
        """Create a new Release model."""
        with db.session.begin_nested():
            release = cls(
                sciencedata_object=sciencedata_object,
                # This goes right into the db table
                status=ReleaseStatus.RECEIVED,
                version=version
            )
            db.session.add(release)
        return release

    @classmethod
    def delete(cls, release_object):
        """Delete object.
        """
        with db.session.begin_nested():
            return db.session.delete(release_object)

    @classmethod
    def update(cls, vals):
        """Update model.
        """
        sdObject.update(vals)
        return sdObject

    @classmethod
    def get(cls, object_id):
        """Return a Release model.
        """
        release_object = cls.query.filter(Release.id == object_id).one()
        return release_object

    @property
    def record(self):
        """Get Record object."""
        if self.record_metadata:
            return Record(self.record_metadata.json, model=self.record_metadata)
        else:
            return None

    @property
    def deposit_id(self):
        """Get deposit identifier."""
        if self.record and '_deposit' in self.record:
            return self.record['_deposit']['id']
        else:
            return None

    def __repr__(self):
        """Get release representation."""
        return (u'<Release {self.record_id}:{self.version} ({self.status.title})>'
                .format(self=self))
