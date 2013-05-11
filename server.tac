import os
import socket

from twisted.application import service
from twisted.runner import procmon
from twisted.application.internet import TimerService, TCPServer
from twisted.web.client import getPage
from twisted.python import log
from twisted.spread import pb
from twisted.internet.utils import getProcessOutput



TRAC_URL = 'http://twistedmatrix.com/trac/'
TRAC_TIMEOUT = 30
CHECK_INTERVAL = 30

VCS_SERVER = socket.gethostbyname('svn.twistedmatrix.com')
HOOK_PATH = os.path.expanduser('~/config/trac-post-commit-hook')
ENV_PATH = os.path.expanduser('~/config/trac-env')
COMMIT_SERVER_PORT = 38159



class TracMonitor(object):
    def __init__(self, processMonitor, processName):
        self._processMonitor = processMonitor
        self._processName = processName

    def restart(self, f):
        log.err(f, 'accessing trac.')
        log.msg('restarting trac.')
        self._processMonitor.stopProcess(self._processName)

    def check(self, url, timeout):
        return getPage(url, timeout=timeout).addErrback(self.restart)


class TracPostCommitPbServerRoot(pb.Root):
    def __init__(self, allowedIP, hookPath, tracEnvPath, tracURL):
        self.allowedIP = allowedIP
        self.hookPath = hookPath
        self.tracEnvPath = tracEnvPath
        self.tracURL = tracURL

    def remote_postCommit(self, revision, author, msg):
        log.msg('postCommit(revision=%r)' % (revision,))
        result = getProcessOutput(self.hookPath, [
            '-p', self.tracEnvPath,
            '-r', str(revision),
            '-u', author,
            '-m', msg,
            '-s', self.tracURL
        ], errortoo=True, env=os.environ)

        def hooked(result):
            log.msg('hook completed: %r' % (result,))
            return result

        def failed(reason):
            log.err(reason, 'hook failed')
            return reason

        result.addCallbacks(hooked, failed)
        return result


class TracPostCommitPbServerRootFactory(pb.PBServerFactory):
    def buildProtocol(self, addr):
        if addr.host != self.root.allowedIP:
            raise Exception('DISALLOWED')
        return pb.PBServerFactory.buildProtocol(self, addr)



application = service.Application('trac')

# Setup trac server process monitor
processMonitor = procmon.ProcessMonitor()
processMonitor.addProcess('trac-server', [
    'twistd',
    '--reactor', 'epoll',
    '--logfile', os.path.expanduser('~/log/twistd.log'),
    '--pidfile', os.path.expanduser('~/run/twistd.pid'),
    '--rundir', os.path.expanduser('~/run/'),
    '--python', os.path.expanduser('~/config/trac_server.tac'),
    '--nodaemon',
], env=os.environ)
processMonitor.setServiceParent(application)

# Setup monitoring service
monitor = TracMonitor(processMonitor, 'trac-server')
monitorService = TimerService(CHECK_INTERVAL, monitor.check, TRAC_URL,
                              TRAC_TIMEOUT)
monitorService.setServiceParent(application)

# Setup post commit perspective broker server
serverRoot = TracPostCommitPbServerRoot(VCS_SERVER, HOOK_PATH, ENV_PATH,
                                        TRAC_URL)
postCommitService = TCPServer(
    COMMIT_SERVER_PORT,
    TracPostCommitPbServerRootFactory(serverRoot)
)
postCommitService.setServiceParent(application)
