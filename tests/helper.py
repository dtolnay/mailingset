# Mailing Set: set-algebraic operations on mailing lists
# Copyright (C) 2015 by David Tolnay <dtolnay@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


class AssertFail:
    """A replacement for TestCase.assertRaisesRegexp which is not in Python 2.6.

    It works as a context manager.

    with AssertFail(self, SyntaxError, "failed!"):
        # something that is expected to raise SyntaxError
    """

    def __init__(self, test_obj, expected_type, expected_msg):
        """
        Args:
            test_obj: The TestCase instance, in order to use its assertion
                methods.
            expected_type: The type of exception that is expected, for example
                SyntaxError.
            expected_msg: The error message that is expected.
        """
        self.test_obj = test_obj
        self.expected_type = expected_type
        self.expected_msg = expected_msg

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        self.test_obj.assertEqual(self.expected_type, type)
        self.test_obj.assertEqual(self.expected_msg, str(value))
        return True # do not propagate the error
