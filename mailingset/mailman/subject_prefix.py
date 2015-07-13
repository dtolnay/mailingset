# Copyright (C) 2014-2015 by the Free Software Foundation, Inc.
#
# This file is part of GNU Mailman.
#
# GNU Mailman is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# GNU Mailman is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# GNU Mailman.  If not, see <http://www.gnu.org/licenses/>.


# This file has been lightly modified to remove dependencies on parts of GNU
# Mailman not important for mailing-set. The original is available at:
# http://bazaar.launchpad.net/~mailman-coders/mailman/3.0/view/7341/src/mailman/handlers/subject_prefix.py
# For comparison, the original is also provided here as subject_prefix.orig.py
# and a diff is provided as subject_prefix.py.diff.


"""Subject header prefix munging."""

__all__ = [
    'SubjectPrefix',
    ]


import re

from email.header import Header, make_header, decode_header
from zope.interface import implementer


RE_PATTERN = '((RE|AW|SV|VS)(\[\d+\])?:\s*)+'
ASCII_CHARSETS = (None, 'ascii', 'us-ascii')
EMPTYSTRING = ''


def ascii_header(subject, prefix, prefix_pattern, ws):
    for chunk, charset in decode_header(subject.encode()):
        if charset not in ASCII_CHARSETS:
            return None
    subject_text = EMPTYSTRING.join(str(subject).splitlines())
    rematch = re.match(RE_PATTERN, subject_text, re.I)
    if rematch:
        subject_text = subject_text[rematch.end():]
        recolon = 'Re: '
    else:
        recolon = ''
    # At this point, the subject may become null if someone posted mail
    # with "Subject: [subject prefix]".
    if subject_text.strip() == '':
        subject_text = '(no subject)'
    else:
        subject_text = re.sub(prefix_pattern, '', subject_text)
    lines = subject_text.splitlines()
    first_line = [lines[0]]
    if recolon:
        first_line.insert(0, recolon)
    if prefix:
        first_line.insert(0, prefix)
    subject_text = EMPTYSTRING.join(first_line)
    return Header(subject_text, continuation_ws=ws)


def all_same_charset(subject, prefix, prefix_pattern, ws):
    list_charset = 'us-ascii'
    chunks = []
    for chunk, charset in decode_header(subject.encode()):
        if charset is None:
            charset = 'us-ascii'
        chunks.append(chunk.decode(charset))
        if charset != list_charset:
            return None
    subject_text = EMPTYSTRING.join(chunks)
    rematch = re.match(RE_PATTERN, subject_text, re.I)
    if rematch:
        subject_text = subject_text[rematch.end():]
        recolon = 'Re: '
    else:
        recolon = ''
    # At this point, the subject may become null if someone posted mail
    # with "Subject: [subject prefix]".
    if subject_text.strip() == '':
        subject_text = '(no subject)'
    else:
        subject_text = re.sub(prefix_pattern, '', subject_text)
    lines = subject_text.splitlines()
    first_line = [lines[0]]
    if recolon:
        first_line.insert(0, recolon)
    if prefix:
        first_line.insert(0, prefix)
    subject_text = EMPTYSTRING.join(first_line)
    return Header(subject_text, charset=list_charset, continuation_ws=ws)


def mixed_charsets(subject, prefix, prefix_pattern, ws):
    list_charset = 'us-ascii'
    chunks = decode_header(subject.encode())
    if len(chunks) == 0:
        subject_text = '(no subject)'
        chunks = [(prefix, list_charset),
                  (subject_text, list_charset),
                  ]
        return make_header(chunks, continuation_ws=ws)
    # Only search the first chunk for Re and existing prefix.
    chunk_text, chunk_charset = chunks[0]
    if chunk_charset is None:
        chunk_charset = 'us-ascii'
    first_text = chunk_text.decode(chunk_charset)
    first_text = re.sub(prefix_pattern, '', first_text).lstrip()
    rematch = re.match(RE_PATTERN, first_text, re.I)
    if rematch:
        first_text = 'Re: ' + first_text[rematch.end():]
    chunks[0] = (first_text, chunk_charset)
    chunks.insert(0, (prefix, list_charset))
    return make_header(chunks, continuation_ws=ws)


class SubjectPrefix:
    """Add a list-specific prefix to the Subject header value."""

    name = 'subject-prefix'
    description = 'Add a list-specific prefix to the Subject header value.'

    def process(self, prefix, msg):
        """See `IHandler`."""
        if not prefix.strip():
            return
        subject = msg.get('subject', '')
        # Turn the value into a Header instance and try to figure out what
        # continuation whitespace is being used.
        if isinstance(subject, Header):
            subject_text = str(subject)
        else:
            subject = make_header(decode_header(subject))
            subject_text = str(subject)
        lines = subject_text.splitlines()
        ws = '\t'
        if len(lines) > 1 and lines[1] and lines[1][0] in ' \t':
            ws = lines[1][0]
        # If the subject_prefix contains '%d', it is replaced with the mailing
        # list's sequence number.  The sequential number format allows '%d' or
        # '%05d' like pattern.
        prefix_pattern = re.escape(prefix)
        # Unescape '%'.
        prefix_pattern = '%'.join(prefix_pattern.split(r'\%'))
        p = re.compile('%\d*d')
        if p.search(prefix, 1):
            # The prefix has number, so we should search prefix w/number in
            # subject.  Also, force new style.
            prefix_pattern = p.sub(r'\s*\d+\s*', prefix_pattern)
        for handler in (ascii_header,
                        all_same_charset,
                        mixed_charsets,
                        ):
            new_subject = handler(
                subject, prefix, prefix_pattern, ws)
            if new_subject is not None:
                del msg['subject']
                msg['Subject'] = new_subject
                return
