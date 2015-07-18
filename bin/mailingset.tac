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


from configparser import ConfigParser

from twisted.application import internet, service
from twisted.mail import smtp
from twisted.python import log, logfile

from mailingset.service import SetSMTPFactory


def create_application():
    config = ConfigParser()
    config.read('conf/mailingset.conf')

    mailingset_app = service.Application('Mailing-Set SMTP Server')
    incoming_port = config.getint('incoming', 'port')
    mailingset_factory = SetSMTPFactory(config, smtp.sendmail)
    mailingset_service = internet.TCPServer(incoming_port, mailingset_factory)
    mailingset_service.setServiceParent(mailingset_app)

    mailingset_log = logfile.LogFile.fromFullPath('mailingset.log')
    log.addObserver(log.FileLogObserver(mailingset_log).emit)

    return mailingset_app

# The application given to the Twisted application infrastructure
application = create_application()

# vim: ft=python
