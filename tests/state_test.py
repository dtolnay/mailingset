import configparser
import os

from twisted.trial import unittest

from mailingset.state import MailingSetState


class StateTest(unittest.TestCase):

    def setUp(self):
        """Initializes state that test cases will inspect."""
        test_dir = os.path.dirname(__file__)
        lists_path = os.path.join(test_dir, 'lists')
        symbols_path = os.path.join(test_dir, 'symbols.txt')

        config = configparser.ConfigParser()
        config.add_section('incoming')
        config.set('incoming', 'domain', 'test.local')
        config.add_section('data')
        config.set('data', 'lists_dir', lists_path)
        config.set('data', 'symbols_file', symbols_path)

        self.state = MailingSetState(config)

    def test_lists(self):
        expected = {
            'simple':  set(x + '@test.local' for x in 'ab'),
            'complex': set(x + '@test.local' for x in 'abc'),
            'nested':  set(x + '@test.local' for x in 'abc'),
            'empty':   set()}
        self.assertEqual(expected, self.state._lists)

    def test_aliases(self):
        expected = {
            'b':        'b@test.local',
            'c':        'c@test.local',
            'ww':       'c@test.local',
            'ww.xx.yy': 'c@test.local',
            'xx':       'c@test.local',
            'yy':       None,
            'yy.zz':    'b@test.local',
            'zz':       'b@test.local'}
        self.assertEqual(expected, self.state._aliases)

    def test_symbols(self):
        expected = {
            'b@test.local': 'yz',
            'c@test.local': 'wxy',
            'empty':        'x',
            'complex':      'T',
            'nested':       'N',
            'simple':       'S'}
        self.assertEqual(expected, self.state._symbols)

    def test_resolve_by_email(self):
        expected = ('yz', set(['b@test.local']))
        self.assertEqual(expected, self.state('b'))

    def test_resolve_by_partial_name(self):
        expected = ('yz', set(['b@test.local']))
        self.assertEqual(expected, self.state('zz'))

    def test_resolve_by_full_name(self):
        expected = ('yz', set(['b@test.local']))
        self.assertEqual(expected, self.state('yy.zz'))

    def test_resolve_by_list(self):
        expected = ('S', set(['a@test.local', 'b@test.local']))
        self.assertEqual(expected, self.state('simple'))

    def test_fail_missing(self):
        expected = 'No such list or person: missing'
        with self.assertRaisesRegexp(SyntaxError, expected):
            self.state('missing')

    def test_fail_ambiguous(self):
        expected = 'Ambiguous person: yy'
        with self.assertRaisesRegexp(SyntaxError, expected):
            self.state('yy')


if __name__ == '__main__':
    nose.run(argv=['', __file__])
