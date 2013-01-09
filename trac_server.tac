
# Perform an early import of svn.client because trac is going to want
# to import it eventually, but by the time it does it, it will be in
# danger of a deadlock.  Doing it here avoids the need to acquire the
# import lock at some random later time when it will probably fail.
from svn import client

from external import TracResource, RootResource

from twisted.application.service import Application
from twisted.application.internet import TCPServer

application = Application('Trac')

from twisted.internet import reactor

from twisted.web.server import Site
from twisted.python.threadpool import ThreadPool

threadpool = ThreadPool(name="trac")
reactor.callWhenRunning(threadpool.start)
reactor.addSystemEventTrigger("during", "shutdown", threadpool.stop)
tracResource = TracResource(reactor, threadpool, '/home/trac-migration/Run/trac/htpasswd', 'trac-projects/twisted')
htdocs = "/home/trac-migration/Run/trac/trac-projects/twisted/htdocs"
attachments = "/home/trac-migration/Run/trac/trac-projects/twisted/attachments"
root = RootResource(tracResource, htdocs, attachments)
site = Site(root, "httpd.log")
TCPServer(9881, site, interface="127.0.0.1").setServiceParent(application)
