"""A simple top-down parser for mailing-set operations.

This is based on the Pratt parser presented in the article "Simple Top-Down
Parsing in Python" at: http://effbot.org/zone/simple-top-down-parsing.htm

A mailing-set operation is an arithmetic expression in which leaf nodes are
mailing list names and operators are _|_ for set union, _&_ for set
intersection, and _-_ for set difference. Curly braces { } are used for
parenthesization, which is REQUIRED when using more than one type of operator.

Examples:
    sf_&_{dog_|_cat}        San Franciscans who own a dog or a cat.
    {sf_&_dog}_|_cat        San Franciscan dog owners, and all cat owners.
    sf_&_dog_|_cat          INVALID due to missing parenthesization.
    sf_&_dog_&_cat          San Franciscans who own both a dog and a cat.
                            Parenthesization is not required for operators of
                            the same type.
    sf_-_dog_-_cat          San Franciscans who own neither a dog nor a cat. Set
                            difference is left associative.
    sf_-_{dog_-_cat}        San Franciscans, except those owning a dog but not a
                            cat.
    {sf_|_la}_&_dog_&_cat   People in SF or LA who own both dogs and cats.

"""
import re


def parse(resolver, address):
    """Parses a mailing-set operation.

    Args:
        resolver: A function taking a leaf token string (mailing list name or
            individual identifier) and returning a pair (symbol,addrs) of symbol
            and set of recipient addresses for that leaf token.
        address: The local part of the email address to parse.

    Returns:
        A pair (tag,addrs) consisting of the subject tag and the set of
        recipient addresses. The subject tag is constructed out of the symbols
        given by the resolver.

    Raises:
        SyntaxError: If the address could not be parsed, or if the address
            evaluated to the empty set. The error message is appropriate to
            include in a bounce message to the sender.
    """
    # Tokenize and parse address
    generator = _yield_tokens(resolver, address)
    tokens = _PeekableStream(generator)
    (tag, addrs, _) = _expression(tokens)

    if not any(token in address for token in ['_|_', '_&_', '_-_', '{', '}']):
        # Special case for "vanilla" addresses containing no set operations in
        # order to behave consistently with Mailman, making possible a drop-in
        # replacement
        tag = '%s%s' % (address[0].upper(), address[1:].lower())
    elif not addrs:
        # Set operation results in the empty set; sender will get a bounce
        raise SyntaxError('No recipients match this set expression')

    return (tag, addrs)


def _expression(tokens, rbp=0):
    """Parses a stream of mailing-set operation tokens.

    This is a slightly modified Pratt parser. The modification is that it
    enforces parenthesization when different operators appear at the same level
    in an expression.

    Args:
        tokens: The stream of tokens to parse. Tokens must have the following:
            lbp: The non-negative integer "left binding power" of the token.
                This controls operator precedence. The higher the value, the
                tighter the token binds to the tokens that follow.
            nud: The "null denotation" function of the token. It is used when
                the token appears at the beginning of a language construct.
            led: The "left denotation" function of the token. It is used when
                the token appears inside a language construct.
        rbp: The "right binding power" that determines how much of the stream to
            parse. Subexpressions are parsed while the adjoining operators have
            higher binding power than rbp.

    Returns:
        A triplet (tag,addrs,token) consisting of the subject tag, the set of
        recipient addresses, and the token that is the root node of the parsed
        syntax tree.

    Raises:
        SyntaxError: If the tokens could not be parsed.
    """
    # Parse the subexpression preceding the first adjoining operator or token of
    # lower precedence
    cur = tokens.next().nud(tokens)

    # Keep track of the most recent adjoining operator to check that they are
    # all of the same type
    prev_op = None

    while rbp < tokens.peek().lbp:
        # Check for missing parenthesization ambiguity like in "sf_&_dog_|_cat"
        if prev_op and prev_op.symbol is not tokens.peek().symbol:
            msg = "Parentheses required when mixing different operators"
            raise SyntaxError(msg)

        # Parse the next subexpression and combine
        prev_op = tokens.next()
        cur = prev_op.led(tokens, cur)

    return cur


class _PeekableStream(object):
    """Wraps a generator to support peeking a value without consuming it."""

    def __init__(self, source):
        """
        Args:
            source: The generator-like source of values to wrap. Values are
                retrieved by calling next() on this object.
        """
        self._source = source
        self._head = self._source.next()

    def peek(self):
        """Gets one value from the source without advancing the source."""
        return self._head

    def next(self):
        """Gets one value from the source and advances the source past it."""
        value = self._head
        self._head = self._source.next()
        return value


def _yield_tokens(resolver, address):
    """Tokenizes the given address into a stream of tokens.

    Args:
        resolver: A function taking a leaf token string (mailing list name or
            individual identifier) and returning a pair (symbol,addrs) of symbol
            and set of recipient addresses for that leaf token.
        address: The local part of the email address to tokenize.

    Yields:
        Tokens. A token is a class that has the following:
            lbp: The non-negative integer "left binding power" of the token.
                This controls operator precedence. The higher the value, the
                tighter the token binds to the tokens that follow.
            nud: The "null denotation" function of the token. It is used when
                the token appears at the beginning of a language construct.
            led: The "left denotation" function of the token. It is used when
                the token appears inside a language construct.

    Raises:
        SyntaxError: If the address could not be tokenized.
    """
    token_pat = r"""
        (
            [A-Za-z0-9]+(?:[_.-][A-Za-z0-9]+)*  # leaf token
        ) | (
            _[|&-]_|\{|\}                       # operator or parenthesis
        ) |
            .                                   # anything else (error)
        """

    # Keep track of position in input to give good error messages
    i = 1

    for leaf, operator in re.compile(token_pat, re.VERBOSE).findall(address):
        if leaf:
            symbol, addrs = resolver(leaf)
            yield _LeafToken(symbol, addrs)
        elif operator == '_|_':
            # Union is associative, meaning (A|B)|C == A|(B|C)
            union = lambda a, b: a | b
            yield _OperatorToken('union', '|', union, assoc=True)
        elif operator == '_&_':
            # Intersection is also associative
            intersection = lambda a, b: a & b
            yield _OperatorToken('intersection', '&', intersection, assoc=True)
        elif operator == '_-_':
            # Difference is not associative
            difference = lambda a, b: a - b
            yield _OperatorToken('difference', '-', difference, assoc=False)
        elif operator == '{':
            yield _LeftParenToken()
        elif operator == '}':
            yield _RightParenToken()
        else:
            raise SyntaxError('Unrecognized syntax near character %d' % (i,))
        i += len(leaf) + len(operator)

    yield _EndToken()


class _LeafToken(object):
    """A token representing a mailing list name or individual identifier."""

    lbp = 3

    def __init__(self, name, addrs):
        """
        Args:
            name: String containing the mailing list name or individual
                identifier.
            addrs: Set of recipient addresses.
        """
        self.name = name
        self.addrs = addrs

    def nud(self, tokens):
        """Null denotation function.

        When a leaf token appears at the beginning of a language construct, the
        result is the mailing list or individual being referenced.
        """
        return (self.name, self.addrs, self)

    def led(self, tokens, left):
        """Left denotation function.

        A leaf token may not appear inside a language construct, so this is an
        error.
        """
        raise SyntaxError('Misplaced list or person name')


class _OperatorToken(object):
    """A token representing a union, intersection, or difference operator."""

    lbp = 2

    def __init__(self, name, symbol, do_operator, assoc):
        """
        Args:
            name: The human-readable name of the operator, like 'intersection'.
            symbol: The symbol for the operator, like '&'.
            do_operator: A function taking two sets and returning the set that
                is the result of applying the operator to the input sets.
            assoc: Boolean, whether this operator is associative. An associative
                operator satisfies (A*B)*C == A*(B*C) for all sets A, B, C. This
                mean parentheses are unnecessary and A*B*C is unambiguous.
        """
        self.name = name
        self.symbol = symbol
        self.do_operator = do_operator
        self.assoc = assoc

    def nud(self, tokens):
        """Null denotation function.

        An operator may not appear at the beginning of a language construct, so
        this is an error.
        """
        raise SyntaxError('Misplaced %s operator' % self.name)

    def led(self, tokens, left):
        """Left denotation function.

        When an operator appears inside a language construct, the operator is
        applied to combine the expression to its left with the expression to its
        right.
        """
        right = _expression(tokens, self.lbp)
        tag = self._combine_tags(left, right)
        addrs = self.do_operator(left[1], right[1])
        return (tag, addrs, self)

    def _combine_tags(self, left, right):
        """Combines the tags from the left and right of this operator into one.

        Args:
            left: Triplet (tag,addrs,token) from the left-hand argument.
            right: Triplet (tag,addrs,token) from the right-hand argument.

        Returns:
            The combined tag.
        """
        left_str = self._parenthesize_if_necessary(left, True)
        right_str = self._parenthesize_if_necessary(right, self.assoc)
        return left_str + self.symbol + right_str

    def _parenthesize_if_necessary(self, other, left_or_assoc):
        """Parenthesizes the other token's tag if omitting parentheses would
        affect the meaning of the expression.

        For example, if this token represents a set difference operator with
        left-hand argument A and right-hand argument B-C, parentheses are
        required around the right-hand argument because A-(B-C) is not the same
        as A-B-C.

        Args:
            other: Triplet (tag,addrs,token) from one of this operator's
                arguments.
            left_or_assoc: True if the argument is coming from the left or this
                operator is associative. In either case, parentheses can be
                omitted if the argument comes from an operator that is the same
                as the current one.

        Returns:
            The appropriately parenthesized tag.
        """
        if other[2].lbp > self.lbp:
            # higher precedence than this operator, no ambiguity without parens
            return other[0]
        elif other[2].symbol == self.symbol and left_or_assoc:
            # same symbol, no ambiguity without parens
            return other[0]
        else:
            return '(' + other[0] + ')'


class _LeftParenToken(object):
    """A token representing a left (opening) parenthesis."""

    lbp = 1

    def nud(self, tokens):
        """Null denotation function.

        When an opening parenthesis appears at the beginning of a language
        construct, the result is the expression between it and the matching
        closing parenthesis.
        """
        expr = _expression(tokens, self.lbp)

        # Check that everything until a closing parenthesis has been consumed
        next_token = tokens.peek()
        if not isinstance(next_token, _RightParenToken):
            raise SyntaxError('Unmatched opening parenthesis')
        # Call 'next' here instead of where 'peek' is called above so that it is
        # not possible to consume the end-of-input token
        tokens.next()

        return expr

    def led(self, tokens, left):
        """Left denotation function.

        An opening parenthesis may not appear inside a language construct, so
        this is an error.
        """
        raise SyntaxError('Misplaced opening parenthesis')


class _RightParenToken(object):
    """A token representing a right (closing) parenthesis.

    In a correctly parenthesized expression, the 'nud' and 'led' methods of this
    token are never called. Instead, closing parentheses are consumed by the
    'nud' method of their matching opening parenthesis token.
    """
    lbp = 1

    def nud(self, tokens):
        """Null denotation function.

        A closing parenthesis may not appear at the beginning of a language
        construct, so this is an error.
        """
        raise SyntaxError('Misplaced closing parenthesis')

    def led(self, tokens, left):
        """Left denotation function.

        A closing parenthesis may not appear inside a language construct, so
        this is an error.
        """
        raise SyntaxError('Unmatched closing parenthesis')


class _EndToken(object):
    """A token representing the end of the input.

    This has lower binding power than any other token, so it is never consumed
    from the token stream. As a result, it does not need 'nud' and 'led'
    methods.
    """
    lbp = 0
