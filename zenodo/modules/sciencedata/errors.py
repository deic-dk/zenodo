# -*- coding: utf-8 -*-

"""ScienceData errors."""


class ScienceDataError(Exception):
    """General ScienceData error."""


class MultipleORCIDAccountsError(ScienceDataError):
    """Multiple accounts with same ORCID found."""

    message = u'Multiple ScienceData accounts with the same ORCID found'

    def __init__(self, orcid=None):
        """Constructor."""
        super(MultipleORCIDAccountsError, self).__init__(self.message)
        self.orcid = orcid


class NoORCIDAccountError(ScienceDataError):
    """Multiple accounts with same ORCID found."""

    message = u'No ScienceData accounts with this ORCID found'

    def __init__(self, orcid=None):
        """Constructor."""
        super(NoORCIDAccountError, self).__init__(self.message)
        self.orcid = orcid


class NoORCIDError(ScienceDataError):
    """No ORCID."""

    message = u'No ORCID found'

    def __init__(self):
        """Constructor."""
        super(NoORCIDError, self).__init__(self.message)


class AccessError(ScienceDataError):
    """Access permissions error."""

    message = u'The user cannot access the ScienceData object'

    def __init__(self, user=None, sciencedata_object=None, message=None):
        """Constructor."""
        super(AccessError, self).__init__(self.message)
        self.user = user
        self.sciencedata_object = sciencedata_object


