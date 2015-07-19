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


import os

import configparser
import email
import netaddr
import nose
import StringIO

from twisted.internet import address
from twisted.internet import base
from twisted.internet import defer
from twisted.internet import error
from twisted.mail import smtp
from twisted.protocols import loopback
from twisted.test import proto_helpers
from twisted.trial import unittest

from mailingset.service import SetSMTPFactory


# Print traceback at creation for delayed calls that are not cleaned up when a
# test case finishes
base.DelayedCall.debug = True

class MailingSetTest(unittest.TestCase):

    def setUp(self):
        """Re-initializes config before each test case.

        Individual test cases may override any of these settings in order to
        exercise specific functionality.
        """
        test_dir = os.path.dirname(__file__)
        lists_path = os.path.join(test_dir, 'lists')
        symbols_path = os.path.join(test_dir, 'symbols.txt')

        self.config = configparser.ConfigParser()

        self.config.add_section('incoming')
        self.config.set('incoming', 'domain', 'test.local')
        self.config.set('incoming', 'accept_from', '127.0.0.0/24')

        self.config.add_section('outgoing')
        self.config.set('outgoing', 'server', 'localhost')
        self.config.set('outgoing', 'port', '12398')
        self.config.set('outgoing', 'envelope_sender', 'mailingset@test.local')

        self.config.add_section('data')
        self.config.set('data', 'lists_dir', lists_path)
        self.config.set('data', 'symbols_file', symbols_path)

    def _server_proto(self, validate=None):
        """Creates a Mailing Set SMTP server protocol based on self.config.

        Some validation is done on outgoing messages to ensure they comply with
        the outgoing message configuration in self.config. After that, they are
        passed to a caller-supplied function for further validation.

        Args:
            validate: A function that will receive outgoing mail from the server
                protocol. It should be callable like validate(to_addrs, msg)
                where to_addrs is a set of recipient addresses as strings, and
                msg is the email.message.Message object holding the headers and
                content of the message.

        Returns:
            An instance of protocol.Protocol implementing the Mailing Set SMTP
            server protocol.
        """
        def sendmail(server, from_addr, to_addrs, msg, port):
            """Receives outgoing messages produced by the server."""
            def assertions():
                """Validates the outgoing messages."""
                # Check compliance with outgoing message configuration in
                # self.config
                self.assertEqual(server, self.config.get('outgoing', 'server'))
                self.assertEqual(from_addr,
                        self.config.get('outgoing', 'envelope_sender'))
                self.assertEqual(port, self.config.getint('outgoing', 'port'))

                # Parse message headers and content
                msg_parser = email.parser.FeedParser()
                msg_parser.feed(msg)
                parsed_msg = msg_parser.close()
                self.assertEqual('body\n', parsed_msg.get_payload())

                # Call user-supplied function for further validation
                if validate:
                    validate(to_addrs, parsed_msg)

            # Defer assertions so the reactor reaches a clean state even if
            # assertions fail
            return defer.execute(assertions)

        # Construct Mailing Set SMTP server protocol
        factory = SetSMTPFactory(self.config, sendmail)
        return factory.buildProtocol(('127.0.0.1', 0))

    def _client_proto(self, to_addr):
        """Creates an SMTP client protocol to send a single message.

        The message will have sender "sender@test.local", subject "subject", and
        body "body". It will appear to be sent from one of the accept_from
        addresses in self.config.

        Args:
            to_addr: The address to which the message is to be sent.

        Returns:
            An instance of protocol.Protocol implementing the SMTP client
            protocol. The protocol will send a single message to the specified
            address upon being connected to a server protocol.
        """
        from_addr = 'sender@test.local'

        # Build the message, which SMTPSenderFactory requires to be a file-like
        # object
        parsed_msg = email.parser.Parser().parsestr('body')
        parsed_msg['Subject'] = 'subject'
        msg_file = StringIO.StringIO(parsed_msg.as_string())

        # Choose an accepted source IP address
        accept_from = self.config.get('incoming', 'accept_from')
        network = netaddr.IPNetwork(accept_from.split(',')[0])
        source_ip = network[0]

        # Construct the SMTP client protocol
        done = defer.Deferred()
        factory = smtp.SMTPSenderFactory(from_addr, to_addr, msg_file, done)
        return factory.buildProtocol((source_ip, 0))

    def test_single_list(self):
        """Tests a message to a single list with no fancy set operations."""
        client = self._client_proto('named@test.local')

        def validate(to_addrs, msg):
            """Validates that the recipient and subject are set correctly."""
            self.assertEqual(set(['b@test.local', 'c@test.local']), to_addrs)
            self.assertEqual('[Named] subject', msg['Subject'])
        server = self._server_proto(validate)

        return loopback.loopbackTCP(server, client)

    def test_bad_source_ip(self):
        """Attempts connection from address outside the accept_from range.

        The server should reject the connection with a 550 error code.
        """
        server = self._server_proto()

        # Connect a transport on which the server will send back responses, but
        # the source IP address is outside the allowed CIDR blocks defined in
        # setUp()
        addr = address.IPv4Address('TCP', '128.0.0.1', 54321)
        trans = proto_helpers.StringTransport(peerAddress=addr)
        server.makeConnection(trans)

        # Attempt to connect from the bad source IP
        server.dataReceived('HELO test.local\r\n')
        trans.clear()
        server.dataReceived('MAIL FROM: sender@test.local\r\n')
        response = trans.value()

        # Clean up protocol before doing anything that might raise exception
        server.connectionLost(error.ConnectionLost())

        # Confirm that server rejected the connection
        expected = '550 Cannot receive from specified address'
        self.assertTrue(response.startswith(expected))

    def test_longhand(self):
        """Executes hard-coded SMTP interaction to check every server response.
        """
        server = self._server_proto()

        # Connect a transport on which the server will send back responses
        addr = address.IPv4Address('TCP', '127.0.0.1', 54321)
        trans = proto_helpers.StringTransport(peerAddress=addr)
        server.makeConnection(trans)

        # Send lines to server and save responses to validate later
        server.dataReceived('HELO me.test\r\n')
        trans.clear()
        server.dataReceived('MAIL FROM: sender@test.local\r\n')
        response1 = trans.value()
        trans.clear()
        server.dataReceived('RCPT TO: named@test.local\r\n')
        response2 = trans.value()
        trans.clear()
        server.dataReceived('DATA\r\n')
        response3 = trans.value()
        trans.clear()
        server.dataReceived('body\r\n')
        response4 = trans.value()
        trans.clear()
        server.dataReceived('.\r\n')
        response5 = trans.value()
        trans.clear()
        server.dataReceived('QUIT\r\n')
        response6 = trans.value()

        # Clean up protocol before doing anything that might raise exception
        server.connectionLost(error.ConnectionDone())

        # Check server response codes and messages against expected
        self.assertEqual(response1, '250 Sender address accepted\r\n')
        self.assertEqual(response2, '250 Recipient address accepted\r\n')
        self.assertEqual(response3, '354 Continue\r\n')
        self.assertEqual(response4, '')
        self.assertEqual(response5, '250 Delivery in progress\r\n')
        self.assertEqual(response6, '221 See you later\r\n')


if __name__ == '__main__':
    nose.run(argv=['', __file__])
