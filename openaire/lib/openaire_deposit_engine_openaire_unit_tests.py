## This file is part of Invenio.
## Copyright (C) 2010, 2011, 2012 CERN.
##
## Invenio is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.
##
## Invenio is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Invenio; if not, write to the Free Software Foundation, Inc.,
## 59 Temple Place, Suite 330, Boston, MA 02111-1307, USA.

"""
"""
from StringIO import StringIO
try:
    import json
except ImportError:
    import simplejson as json
import os
import re
import unittest2 as unittest

from invenio.openaire_deposit_checks import CFG_METADATA_FIELDS_CHECKS, \
    _RE_DOI, _RE_AUTHOR_ROW, _check_authors
from invenio.openaire_deposit_config import CFG_METADATA_FIELDS
from invenio.openaire_deposit_engine import OpenAIREPublication
from invenio.openaire_deposit_fixtures import FIXTURES, MARC_FIXTURES
from invenio.testutils import make_test_suite, run_test_suite
from invenio.webuser import get_nickname
from invenio.dbquery import run_sql
from invenio.bibrecord import record_get_field_value


class DOIRegressionTest(unittest.TestCase):
    dois = [
        "10.1000/123456",
        "10.1016.12.31/nature.S0735-1097(98)2000/12/31/34:7-7",
        "10.1007/978-3-642-28108-2_19",
        "10.1007.10/978-3-642-28108-2_19",
        "10.1579/0044-7447(2006)35\[89:RDUICP\]2.0.CO;2",
    ]

    not_dois = [
        "4210.1000/123456",
        "10.4515260,51.1656910",
    ]

    def test_doi_regexp(self):
        for doi in self.dois:
            self.assertTrue(
                _RE_DOI.match(doi), "Failed matching DOI %s" % doi)

        for doi in self.not_dois:
            self.assertFalse(
                _RE_DOI.match(doi), "Incorrectly matched %s as DOI" % doi)


class AuthorCheckRegressionTest(unittest.TestCase):
    validnames = """Lastname, Firstname
Lastname,Firstname
Lastname, First name
Lastname,First name
Lastname, I. N.
Lastname, I.N.
Lastname, IN
Lastname, I.
Lastname, First-name A.
Lastname, A.First-name
Lastname, IN.
Lastname, I
Lastname,I
van der Lastname,I
Last-name and more,I."""

    def test_author_regexp(self):
        failed = []
        for l in self.validnames.splitlines():
            m = _RE_AUTHOR_ROW.match(l)
            if not m:
                failed.append(l)
        self.assertEqual(failed, [])

    def test_author_name_check(self):
        (field, state, messages) = _check_authors(
            {'authors': self.validnames}, 'en', lambda x: x
        )
        self.assertNotEqual(state, "error", unicode(messages))


class EngineTest(unittest.TestCase):
    user_id = None
    project_id = '283595'


    def record_marc_output(self, rec):
        """
        Print MARC for a given record.

        Used to compare a record generated by engine with the content of the record.
        """
        rec = rec.items()
        rec.sort()

        marc = ""

        for field_code, fields in rec:
            for subfields, ind1, ind2, a, b in fields:
                line = "\n%s%s%s " % (field_code, ind1 or '_', ind2 or '_')
                for subcode, subvalue in subfields:
                    line += "$$%s%s" % (subcode, subvalue)
                marc += line
        return marc

    def get_fixture(self, type):
        """ Retrieve fixutre and expected MARC """
        fixture = {}
        # Append pub id to field name.
        for field, val in FIXTURES[type].items():
            fixture['%s_%s' % (field, self.pub_id)] = val
        return fixture, MARC_FIXTURES[type]

    def assertMarcIsEqual(self, expected_marc, marc):
        """
        Assert that two MARC representations are equal, but exclude
        eg. 001 control fields.
        """
        # Filter out the control field.
        rm_pat = re.compile("^001.*$")
        rm_func = lambda x: not rm_pat.match(x)

        expected_marc_list = filter(
            rm_func, [x.strip() for x in expected_marc.split('\n')])
        marc_list = filter(rm_func, [x.strip() for x in marc.split('\n')])

        i = 0
        for i in range(0, max(len(expected_marc_list), len(marc_list))):
            try:
                l1 = expected_marc_list[i]
            except IndexError:
                l1 = ''
            try:
                l2 = marc_list[i]
            except IndexError:
                l2 = ''
            i += 1

            if l1.startswith("RE:"):
                if not re.match(l1[3:], l2):
                    raise AssertionError("%s doesn't match %s" % (l1, l2))
            else:
                if l1 != l2:
                    raise AssertionError("%s != %s" % (l1, l2))

    #
    # Tests
    #
    def setUp(self):
        if self.user_id == None:
            res = run_sql("SELECT id FROM user WHERE nickname='admin'")
            assert(len(res) == 1, "Couldn't find admin user")
            self.user_id = int(res[0][0])

        self.pub = OpenAIREPublication(self.user_id)
        self.pub_id = self.pub.publicationid

    def tearDown(self):
        self.pub.delete()
        self.pub = None
        self.pub_id = None

    def _test_pubtype(self, type):
        """
        Test MARC generated for a given publication type.
        """
        fixture, expected_marc = self.get_fixture(type)
        self.pub.merge_form(fixture)
        self.pub.check_metadata()
        self.pub.check_projects()
        self.pub.link_project(self.project_id)
        rec = self.pub.get_record()
        marc = self.record_marc_output(rec)

        self.assertMarcIsEqual(expected_marc, marc)

    def test_publishedArticle(self):
        self._test_pubtype('publishedArticle')

    def test_report(self):
        self._test_pubtype('report')

    def test_data(self):
        self._test_pubtype('data')

    def test_thesis(self):
        self._test_pubtype('thesis')

    def test_book(self):
        self._test_pubtype('book')

    def test_bookpart(self):
        self._test_pubtype('bookpart')

    def test_conference(self):
        self._test_pubtype('conferenceContribution')

    def test_preprint(self):
        self._test_pubtype('preprint')

    def test_workingpaper(self):
        self._test_pubtype('workingPaper')

#
# Create test suite
#
TEST_SUITE = make_test_suite(DOIRegressionTest, AuthorCheckRegressionTest, EngineTest)

if __name__ == "__main__":
    run_test_suite(TEST_SUITE)
