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
