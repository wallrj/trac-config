from fabric.api import run, settings

from braid import pip, postgres, cron, git, archive, utils
from braid.twisted import service
from braid.utils import confirm

from braid import config
from braid.tasks import addTasks
__all__ = ['config']


class Trac(service.Service):
    def task_install(self):
        """
        Install trac.
        """
        self.bootstrap(python='system')

        # FIXME: Make these idempotent.
        postgres.createUser('trac')
        postgres.createDb('trac', 'trac')

        with settings(user=self.serviceUser):
            pip.install('psycopg2', python='system')
            self.update(_installDeps=True)

            run('/bin/mkdir -p ~/svn')
            run('/bin/ln -nsf ~/svn {}/trac-env/svn-repo'.format(self.configDir))

            run('/bin/mkdir -p ~/attachments')
            run('/bin/ln -nsf ~/attachments {}/trac-env/attachments'.format(
                self.configDir))

            run('/bin/ln -nsf ~/website/trac-files/templates {}/trac-env/templates'.format(
                self.configDir))

            run('/bin/ln -nsf {} {}/trac-env/log'.format(self.logDir, self.configDir))

            run('/bin/ln -nsf {}/start {}/start'.format(self.configDir, self.binDir))

            cron.install(self.serviceUser, '{}/crontab'.format(self.configDir))


    def update(self, _installDeps=False):
        """
        Update trac config.
        """
        # TODO
        with settings(user=self.serviceUser):
            git.branch('https://github.com/twisted-infra/trac-config', self.configDir)
            git.branch('https://github.com/twisted-infra/t-web', '~/website')

            if _installDeps:
                pip.install('git+https://github.com/twisted-infra/twisted-trac-source.git', python='system')
            else:
                pip.install('--no-deps --upgrade git+https://github.com/twisted-infra/twisted-trac-source.git', python='system')


    def task_update(self):
        """
        Update config and restart.
        """
        self.update()
        self.task_restart()


    def task_dump(self, localfile):
        """
        Create a tarball containing all information not currently stored in
        version control and download it to the given C{localfile}.
        """
        with settings(user=self.serviceUser):
            with utils.tempfile() as temp:
                postgres.dumpToPath('trac', temp)

                archive.dump({
                    'htpasswd': 'config/htpasswd',
                    'attachments': 'attachments',
                    'db.dump': temp,
                }, localfile)

    def task_restore(self, localfile, restoreDb=True):
        """
        Restore all information not stored in version control from a tarball
        on the invoking users machine.
        """
        restoreDb = str(restoreDb).lower() in ('true', '1', 'yes', 'ok', 'y')

        if restoreDb:
            msg = (
                'All existing files present in the backup will be overwritten and\n'
                'the database dropped and recreated.'
            )
        else:
            msg = (
                'All existing files present in the backup will be overwritten\n'
                '(the database will not be touched).'
            )

        print ''
        if confirm(msg):
            # TODO: Ask for confirmation here
            if restoreDb:
                postgres.dropDb('trac')
                postgres.createDb('trac', 'trac')

            with settings(user=self.serviceUser):
                with utils.tempfile() as temp:
                    archive.restore({
                        'htpasswd': 'config/htpasswd',
                        'attachments': 'attachments',
                        'db.dump': temp,
                    }, localfile)
                    if restoreDb:
                        postgres.restoreFromPath('trac', temp)



addTasks(globals(), Trac('trac').getTasks())
