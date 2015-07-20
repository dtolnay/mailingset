# Mailing Set
[![Build Status](https://travis-ci.org/dtolnay/mailingset.svg?branch=master)](https://travis-ci.org/dtolnay/mailingset)
[![Coverage Status](https://coveralls.io/repos/dtolnay/mailingset/badge.svg?branch=master&service=github)](https://coveralls.io/github/dtolnay/mailingset?branch=master)

A mailing list server that treates mailing lists as sets and allows mail to be
sent to the result of set-algebraic expressions on those sets. The union,
intersection, and difference operators are supported. Sending mail to a set
operation involves specifying a set expression in the local part of the
recipient email address.

![operators](https://raw.githubusercontent.com/dtolnay/mailingset/master/docs/operators.png)

## Syntax

    somelist_|_otherlist@example.com      (set union)
    somelist_&_otherlist@example.com      (set intersection)
    somelist_-_otherlist@example.com      (set difference)
    aaa_&_{bbb_|_ccc}@example.com         (parenthesization using curly braces)

Individual people may also be used as building blocks in a set expression.

    somelist_-_dtolnay@example.com        (by username)
    somelist_-_david@example.com          (by first name)
    somelist_-_tolnay@example.com         (by last name)
    somelist_-_david.tolnay@example.com   (by period-concatenated full name)

In order to minimize confusion for the recipients, parenthesization is
*required* when mixing different operators, so operator precedence is not
relevant.

    sf_&_{dog_|_cat}        San Franciscans who own a dog or a cat
    {sf_&_dog}_|_cat        San Franciscan dog owners, and all cat owners
    sf_&_dog_|_cat          INVALID due to missing parenthesization
    sf_&_dog_&_cat          San Franciscans who own both a dog and a cat;
                            parenthesization is not required for operators of
                            the same type
    sf_-_dog_-_cat          San Franciscans who own neither a dog nor a cat; set
                            difference is left associative
    sf_-_{dog_-_cat}        San Franciscans, except those owning a dog but not a
                            cat
    {sf_|_la}_&_dog_&_cat   People in SF or LA who own both dogs and cats

![parens](https://raw.githubusercontent.com/dtolnay/mailingset/master/docs/parens.png)

## Bounces

The server may cause messages to bounce for three reasons.

An invalidly addressed email will bounce. This happens if parentheses are
mismatched like `a_&_b}_-_c`, or placed incorrectly like `a{_|_b}`.

An email will bounce if any of the building blocks cannot be resolved. For
example if there is no list named `b` and no individual has the first name, last
name, or username `b`, then an email to `a_-_b` will bounce. It is also a
problem if `b` is the first name, last name, or username of more than one
individual.

Finally, a validly addressed email will bounce if evaluating the set expression
results in the empty set. For example, an email addressed to `a_-_a` will bounce
for this reason, as will `a_&_{b_-_a}`. If lists `a` and `b` have no members in
common, an email to `a_&_b` will bounce.

## Headers

Just like GNU Mailman, Mailing Set adds a tag to the subject line of mailing
list traffic. The tag is an abbreviated representation of the set operation. For
the address `san-franciscans_&_{dog-owners_|_cat-owners}`, the tagged subject
may look like:

    [SF&(Dog|Cat)] The Original Subject

Abbreviations for list names are configured in symbols.txt as described below.

Additionally, the following headers are added to every message:

    Precedence: list
    List-Id: the_&_set_&_expression.mailingset.yourdomain.com
    List-Post: <mailto:the_&_set_&_expression@yourdomain.com>

The List-Id header makes it possible for a mail client to filter for all set
operation messages. For example in Gmail the filter would be `list:mailingset`.

## Installation

Requires Python 2.6 or 2.7.

1. Clone this repo
2. Run `pip install -e .`
3. Configure as described in the next section
4. Run `twistd -y bin/mailingset.tac` to run as a daemon, or `twistd -ny
   bin/mailingset.tac` to run in the foreground

The daemon can be killed by running `kill $(cat twistd.pid)`.

## Configuration

The following settings are defined in `conf/mailingset.conf`. An example
configuration file is provided.

- Section `[incoming]`
  - `domain`: The domain part of email addresses that may be mailing lists, i.e.
    the domain that the sender types when they want to send an email to this
    server.
  - `port`: The port on which Mailing Set should run its SMTP server.
  - `accept_from`: Comma-separated list of IP addresses in
    [CIDR notation](https://en.wikipedia.org/wiki/Classless_Inter-Domain_Routing#CIDR_notation)
    from which to accept mail. Optional. If not specified, mail is accepted from
    any IP address.
- Section `[outgoing]`
  - `server`: SMTP server through which to send outgoing mail.
  - `port`: Port of SMTP server through which to send outgoing mail.
  - `envelope_sender`: Envelope sender of outgoing messages. Bounces from other
    servers will be directed to this address.
  - `archive_addr`: Address to include on bcc of all outgoing messages for the
    purpose of archiving traffic. Optional.
- Section `[data]`
  - `lists_dir`: Relative or absolute path to directory containing list
    definitions, as described below.
  - `symbols_file`: Relative or absolute path to file containing mailing list
    symbols for use in subject tags, as described below.

#### List membership

Lists are defined as text files with one address per line. The name of the file
is the name of the list.

    lists/
      |-- cat-owners
      |-- dog-owners
      |-- san-franciscans

Each file should have lines like:

    Alice Anderson <alice@somedomain.com>
    Bob Q Brown <bob@otherdomain.com>
    other-list@yourdomain.com

Lists may be subscribed to other lists as long as there is no cycle.

The names associated with email addresses determine how that individual may be
used in a set expression. In the example above, mail to dog owners except for
Bob would be addressed as `dog-owners_-_bob.q.brown@yourdomain.com`.

There is no support for reloading mailing list definitions without restarting
the server.

#### List symbols

List symbols are used in constructing subject tags. They are configured in a
text file, typically called `symbols.txt`. The file should look like this:

    cat-owners:Cat
    dog-owners:Dog
    san-franciscans:SF

Then a message addressed to `san-franciscans_&_{dog-owners_|_cat-owners}` would
be tagged like this:

    [SF&(Dog|Cat)] The Original Subject

#### Using with Postfix

If Postfix is set up to receive incoming mail on your server, you can have it
forward set-operation mail to Mailing Set by using a transport table. Refer to
[Postfix documentation](http://www.postfix.org/transport.5.html) for information
about transport tables. Assuming Mailing Set is running on port 2500, the line
you want in your transport table is:

    /^(.*_[&|-]_.*)@/    smtp:[localhost]:2500

Add this line to `/etc/postfix/transport` and run `postmap
/etc/postfix/transport` to have Postfix rebuild its index of the transport
table. Run `postmap -q 'a_&_b@yourdomain.com' regexp:/etc/postfix/transport` and
verify that it prints out `smtp:[localhost]:2500`, meaning the message would be
rerouted.

In your Postfix config file, typically `/etc/postfix/main.cf`, register the
transport map by adding `regexp:/etc/postfix/transport` to both
`local_recipient_maps` and `transport_maps`. For a typical Postfix installation
with local LDAP users and Mailman lists, the lines would look something like:

    local_recipient_maps = ldap:ldusers $alias_maps $virtual_maps regexp:/etc/postfix/transport
    transport_maps = regexp:/etc/postfix/transport

Run `postfix check` to check for errors in the config file, then restart Postfix
by running whichever of these is appropriate for your system:

    postfix stop && postfix start
    /etc/init.d/postfix restart
    service postfix restart

#### Importing lists from Mailman

These commands can be used to retrieve mailing lists from Mailman in the correct
format:

    mkdir lists
    list_lists -b | xargs -L 1 -I {} list_members -o lists/{} -f {}

The `list_lists` and `list_members` commands are provided by Mailman. They are
typically installed in `/usr/lib/mailman/bin` or `/usr/sbin`.

You will still need to define symbols for each mailing list for use in subject
tags, or write a script to generate them heuristically.

## Licensing

Mailing Set is licensed as GPLv3. It depends on some GNU Mailman code to do
insertion of subject tags into non-ASCII subject lines, and Mailman is GPLv3. If
you need all or part of this software under a different license, please let me
know and we can consider the options.

## Limitations

Set operations are done on sets of email addresses. If an individual uses
different email addresses on different lists, the results will be incorrect.
This is not a problem if everybody uses a single email address across all
mailing lists, for example in a corporate setting where every employee uses
their single work email address.

Configuration changes require a server restart.

## FAQ

#### How can those be valid email addresses?

They are! The standard that defines this is
[RFC 5322](https://tools.ietf.org/html/rfc5322)
in which
[section 3.2.3](https://tools.ietf.org/html/rfc5322#section-3.2.3)
lists all of these characters as valid in an email address.
