import os
import re


class MailingSetState(object):
    """An immutable cache of the membership of mailing lists on this server.

    This is initialized once at server startup and is used for all messages that
    hit the server. There is no support for reloading this cache without
    restarting the server.

    The function call operator may be used to query the name and recipient
    addresses of a list or individual. See __call__.
    """

    # Mailing lists may not be nested more deeply than this limit
    NEST_LIMIT = 10

    def __init__(self, config):
        """
        Args:
            config: ConfigParser object holding configuration for the
                mailing-set SMTP server. The entries required here are the path
                to the directory containing list definitions, the path to the
                file containing mailing list symbols, and the domain used by
                mailing list addresses.

        Raises:
            RuntimeError: If nesting exceeds NEST_LIMIT, or if a list is missing
            a symbol.
        """
        # Store config entries first because the loader functions rely on these
        self._lists_dir = os.path.abspath(config.get('data', 'lists_dir'))
        self._symbols_file = os.path.abspath(config.get('data', 'symbols_file'))
        self._server_domain = config.get('incoming', 'domain')

        # Load state from the places specified in config
        self._lists = self._load_lists()
        self._aliases = self._load_aliases()
        self._symbols = self._load_symbols()

        self._check_symbols()

    def __call__(self, val):
        """Queries the name and recipient addresses of a list or individual.

        The query string may be the name of a mailing list, or an "individual
        identifier." An individual identifier is the first name, middle name,
        last name, username, or period-concatenated (first.last) full name of an
        individual, as long as it uniquely identifies one individual.

        Note that treating the input as a list name takes precedence, so the
        query succeeds even if an individual may also be identified by the same
        string. This ensures that it is always possible to address a message to
        each list on the server.

        Args:
            val: A mailing list name or individual identifier as described
                above.

        Returns:
            A pair (symbol,addrs) of symbol and set of recipient addresses. The
            symbol for a mailing list is the one specified in the symbols_file
            in the config used to construct this class. The symbol for an
            individual is the individual's initials in lowercase.

        Raises:
            SyntaxError: If the specified individual identifier is not unique to
                one individual, or if there is no list or individual matching
                the input string.
        """
        val = val.lower()
        if val in self._lists:
            symbol = self._symbols[val]
            addrs = self._lists[val]
        elif val in self._aliases:
            addr = self._aliases[val]
            if not addr:
                raise SyntaxError('Ambiguous person: %s' % (val,))
            symbol = self._symbols[addr]
            addrs = set([addr])
        else:
            raise SyntaxError('No such list or person: %s' % (val,))
        return (symbol, addrs)

    def _list_lists(self):
        """List of mailing list names on this server.

        A mailing list is a file in the directory lists_dir specified in the
        config used to construct this class. The name of the mailing list is the
        name of the file.

        Returns:
            A set of mailing list names.
        """
        names = os.listdir(self._lists_dir)
        def is_list(name):
            return os.path.isfile(os.path.join(self._lists_dir, name))
        return set([name for name in names if is_list(name)])

    def _read_members(self, listname):
        """Lists the members of a mailing list.

        The members of a mailing list are set in a file with the same name as
        the mailing list, in the directory lists_dir specified in the config
        used to construct this class. Each line of the file is one member. Refer
        to the documentation of _split_line for the permitted formats of a line.

        Args:
            listname: Name of the mailing list.

        Returns:
            A set of (name,addr) pairs. The name is None if no name is given for
            the member.
        """
        path = os.path.join(self._lists_dir, listname)
        with open(path) as list_file:
            return set(_split_line(line) for line in list_file if line.strip())

    def _compute(self, listname, members, depth=0):
        """Recursively flattens a mailing list containing other mailing lists.

        There is a limit of 10 on how deeply mailing lists may be nested.
        Nesting deeper than this probably means there is a cycle.

        Args:
            listname: Name of the list whose members to compute.
            members: A dict of list names to set of addresses, where the
                addresses may be other mailing lists.
            depth: Recursion depth.

        Returns:
            The flattened set of addresses.

        Raises:
            RuntimeError: If nesting exceeds NEST_LIMIT.
        """
        if depth > self.NEST_LIMIT:
            msg = 'Maximum recursion depth exceeded; lists might have a cycle'
            raise RuntimeError(msg)

        result = set()
        for addr in members[listname]:
            (local, domain) = addr.split('@', 1)
            if domain == self._server_domain and local in members:
                # Recursively expand list
                result |= self._compute(local, members, depth + 1)
            else:
                result.add(addr)
        return result

    def _load_lists(self):
        """Loads a dict of list name to set of members by looking in lists_dir.

        Returns:
            A dict of list name to set of recipient addresses. Nested mailing
            lists are flattened in this dict.

        Raises:
            RuntimeError: If nesting exceeds NEST_LIMIT.
        """
        listnames = self._list_lists()

        # Read members without flattening.
        addrs = {}
        for lname in listnames:
            addrs[lname] = set(line[1] for line in self._read_members(lname))

        # Flatten nested lists
        return dict((lname, self._compute(lname, addrs)) for lname in listnames)

    def _read_all_members(self):
        """Lists the members across all mailing lists.

        Mailing list membership is defined in the directory lists_dir specified
        in the config used to construct this class.

        Returns:
            A set of (name,addr) pairs containing every member on the server.
            The name is None if no name is given for the member.
        """
        members = set()
        for listname in self._list_lists():
            members |= self._read_members(listname)
        return members

    def _load_aliases(self):
        """Loads a dict mapping individual identifiers to email address.

        An individual identifier is the first name, middle name, last name,
        username, or period-concatenated (first.last) full name of an
        individual, as long as it uniquely identifies one individual.

        Returns:
            A dict of individual identifier to email address. If any identifier
            applies to more than one individual, such as a common first name, it
            is present as a key in the dict but the value is None.
        """
        members = self._read_all_members()
        aliases = {}

        invalid = re.compile('[^a-z0-9.]')
        def set_if_absent(key, value, clean):
            if clean:
                key = invalid.sub('', key)
            if key in aliases and aliases[key] != value:
                aliases[key] = None
            else:
                aliases[key] = value

        for (name, addr) in members:
            if name:
                # Username
                local = addr.split('@', 1)[0]
                set_if_absent(local, addr, False)

                # First name, middle name, last name
                parts = name.lower().split()
                for part in parts:
                    set_if_absent(part, addr, True)

                # Period-concatenated full name
                concat = '.'.join(parts)
                set_if_absent(concat, addr, True)

        return aliases

    def _load_symbols(self):
        """Loads a dict containing symbols suitable for using in a subject tag.

        Symbols for mailing lists are defined in the file symbols_file specified
        in the config used to construct this class. Each line corresponds to one
        list, in the format:
            list-name:SYM

        Symbols for individuals are their initials in lowercase.

        Returns:
            A dict in which the keys are list names and individual email
            addresses, and the values are the corresponding symbols.
        """
        symbols = {}

        with open(self._symbols_file) as symbols_file:
            for line in symbols_file:
                (listname, symbol) = line.strip().split(':')
                symbols[listname.lower()] = symbol

        for listname in self._list_lists():
            for (name, addr) in self._read_members(listname):
                if name:
                    abbrev = ''.join(word[:1] for word in name.split()).lower()
                    symbols[addr.lower()] = abbrev

        return symbols

    def _check_symbols(self):
        """Checks that a symbol has been defined for every mailing list.

        Raises:
            RuntimeError: If any mailing list is missing a symbol.
        """
        missing = set(self._lists.keys()) - set(self._symbols.keys())
        if missing:
            missing_names = ', '.join(missing)
            msg = 'These mailing lists are missing symbols: %s' % missing_names
            raise RuntimeError(msg)


def _split_line(line):
    """Separates a line into a name and email address.

    Args:
        line: A line in one of the formats used by the GNU Mailman list_members
            command:
                email@server.what
                First Last <email@server.what>
                "First Last" <email@server.what>
            No meaningful error checking is done, so the result is undefined if
            the input is not in one of these formats.

    Returns:
        A pair (name,addr). If the input line does not include a name, the name
        is None.
    """
    split = line.split('<', 1)
    if len(split) == 2:
        name = split[0].strip()
        name = name.strip('"').strip() # strip surrounding double quotes
        name = name.replace('\\', '').strip() # remove backslashes
        addr = split[1].strip().rstrip('>').lower()
        return (name, addr)
    else:
        addr = line.strip().lower()
        return (None, addr)
