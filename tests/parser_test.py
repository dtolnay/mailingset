from twisted.trial import unittest

from mailingset import parser


alist = ('AA', set(['001', '011', '101', '111']))
blist = ('BB', set(['010', '011', '110', '111']))
clist = ('CC', set(['100', '101', '110', '111']))
empty = ('xx', set())
lists = {'alist': alist, 'blist': blist, 'clist': clist, 'empty': empty}
resolve = lambda address: lists[address]


class ParserTest(unittest.TestCase):

    def test_single_list(self):
        result = parser.parse(resolve, 'alist')
        expected = ('Alist', alist[1])
        self.assertEqual(result, expected)

    def test_single_in_parens(self):
        result = parser.parse(resolve, '{alist}')
        expected = ('AA', alist[1])
        self.assertEqual(result, expected)

    def test_simple_intersection(self):
        result = parser.parse(resolve, 'alist_&_blist')
        expected = ('AA&BB', alist[1] & blist[1])
        self.assertEqual(result, expected)

    def test_simple_union(self):
        result = parser.parse(resolve, 'alist_|_blist')
        expected = ('AA|BB', alist[1] | blist[1])
        self.assertEqual(result, expected)

    def test_simple_difference(self):
        result = parser.parse(resolve, 'alist_-_blist')
        expected = ('AA-BB', alist[1] - blist[1])
        self.assertEqual(result, expected)

    def test_left_associate(self):
        result = parser.parse(resolve, '{alist_-_blist}_|_clist')
        expected = ('(AA-BB)|CC', (alist[1] - blist[1]) | clist[1])
        self.assertEqual(result, expected)

    def test_right_associate(self):
        result = parser.parse(resolve, 'alist_-_{blist_|_clist}')
        expected = ('AA-(BB|CC)', alist[1] - (blist[1] | clist[1]))
        self.assertEqual(result, expected)

    def test_omitted_parens(self):
        result = parser.parse(resolve, 'alist_|_blist_|_clist')
        expected = ('AA|BB|CC', alist[1] | blist[1] | clist[1])
        self.assertEqual(result, expected)

    def test_surplus_parens(self):
        result = parser.parse(resolve, 'alist_|_{blist_|_clist}')
        expected = ('AA|BB|CC', alist[1] | blist[1] | clist[1])
        self.assertEqual(result, expected)

    def test_parens_left(self):
        result = parser.parse(resolve, '{alist_-_clist}_-_blist')
        expected = ('AA-CC-BB', (alist[1] - clist[1]) - blist[1])
        self.assertEqual(result, expected)

    def test_parens_right(self):
        result = parser.parse(resolve, 'alist_-_{clist_-_blist}')
        expected = ('AA-(CC-BB)', alist[1] - (clist[1] - blist[1]))
        self.assertEqual(result, expected)

    def test_vanilla_empty(self):
        """Vanilla address is not a set expression, so empty is not an error."""
        result = parser.parse(resolve, 'empty')
        expected = ('Empty', set())
        self.assertEqual(result, expected)

    def test_fail_empty_result(self):
        expected = 'No recipients match this set expression'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, 'alist_-_alist')

    def test_fail_unparenthesized(self):
        expected = 'Parentheses required when mixing different operators'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, 'alist_&_blist_|_clist')

    def test_fail_bad_token(self):
        expected = 'Unrecognized syntax near character 6'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, 'alist_+_blist')

    def test_fail_misplaced_leaf(self):
        expected = 'Misplaced list or person name'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, '{alist}blist')

    def test_fail_misplaced_union(self):
        expected = 'Misplaced union operator'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, '_|_alist')

    def test_fail_misplaced_intersect(self):
        expected = 'Misplaced intersection operator'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, '_&_alist')

    def test_fail_misplaced_difference(self):
        expected = 'Misplaced difference operator'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, '_-_alist')

    def test_fail_unmatched_open_paren(self):
        expected = 'Unmatched opening parenthesis'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, '{alist')

    def test_fail_misplaced_open_paren(self):
        expected = 'Misplaced opening parenthesis'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, 'alist{blist}')

    def test_fail_misplaced_close_paren(self):
        expected = 'Misplaced closing parenthesis'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, 'alist_&_}')

    def test_fail_unmatched_close_paren(self):
        expected = 'Unmatched closing parenthesis'
        with self.assertRaisesRegexp(SyntaxError, expected):
            parser.parse(resolve, '{alist_&_blist}}')


if __name__ == '__main__':
    nose.run(argv=['', __file__])
