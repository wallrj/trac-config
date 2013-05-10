from fabric.api import run, settings
from fabric.contrib.console import confirm

from braid import pip, postgres, cron, git, archive, utils
from braid.twisted import service

from braid import config
_hush_pyflakes = [config]


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
            self.task_update(_installDeps=True)

            run('mkdir -p ~/svn')
            run('ln -nsf ~/svn {}/trac-env/svn-repo'.format(self.configDir))

            run('mkdir -p ~/attachments')
            run('ln -nsf ~/attachments {}/trac-env/attachments'.format(
                self.configDir))

            run('ln -nsf {} {}/trac-env/log'.format(self.logDir, self.configDir))

            run('ln -nsf {}/start {}/start'.format(self.configDir, self.binDir))

            # Overwrite the generic stop executable provided by the base class
            run('ln -nsf {}/stop {}/stop'.format(self.configDir, self.binDir))
            run('ln -nsf {}/restart {}/restart'.format(self.configDir,
                                                       self.binDir))
            run('ln -nsf {}/start-monitor {}/start-monitor'.format(
                self.configDir, self.binDir))
            cron.install(self.serviceUser, '{}/crontab'.format(self.configDir))


    def task_update(self, _installDeps=False):
        """
        Update trac config.
        """
        # TODO
        with settings(user=self.serviceUser):
            git.branch('https://github.com/twisted-infra/trac-config', self.configDir)

            if _installDeps:
                pip.install('git+https://github.com/twisted-infra/twisted-trac-source.git', python='system')
            else:
                pip.install('--no-deps --upgrade git+https://github.com/twisted-infra/twisted-trac-source.git', python='system')

    def task_start_monitor(self):
        """
        Start the monitor.
        """
        with settings(user=self.serviceUser):
            run('{}/start-monitor'.format(self.binDir), pty=False)

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
                'the database dropped and recreated. Do you want to proceed?'
            )
        else:
            msg = (
                'All existing files present in the backup will be overwritten\n'
                '(the database will not be touched). Do you want to proceed?'
            )

        print ''
        if confirm(msg, default=False):
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



globals().update(Trac('trac').getTasks())
