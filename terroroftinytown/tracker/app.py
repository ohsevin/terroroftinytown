# encoding=utf-8
import functools
import os.path

from tornado.web import URLSpec as U
import tornado.web

from terroroftinytown.services.registry import registry
from terroroftinytown.tracker import account, admin, project, api
from terroroftinytown.tracker import model
from terroroftinytown.tracker.base import BaseHandler
from terroroftinytown.tracker.errors import UserIsBanned
from terroroftinytown.tracker.ui import FormUIModule
from terroroftinytown.tracker.stats import Stats


class Application(tornado.web.Application):
    def __init__(self, database, redis=None, **kwargs):
        self.db = database
        self.redis = redis

        handlers = [
            U(r'/', IndexHandler, name='index'),
            U(r'/admin/', admin.AdminHandler, name='admin.overview'),
            U(r'/admin/banned', admin.BannedHandler, name='admin.banned'),
            U(r'/admin/login', account.LoginHandler, name='admin.login'),
            U(r'/admin/logout', account.LogoutHandler, name='admin.logout'),
            U(r'/admin/results', admin.ResultsHandler, name='admin.results'),
            U(r'/admin/error_reports', admin.ErrorReportsListHandler,
              name='admin.error_reports'),
            U(r'/admin/error_reports/delete_all',
              admin.ErrorReportsDeleteAllHandler,
              name='admin.error_reports.delete_all'),
            U(r'/users/', account.AllUsersHandler, name='users.overview'),
            U(r'/user/([a-z0-9_-]*)', account.UserHandler, name='user.overview'),
            U(r'/projects/overview', project.AllProjectsHandler, name='projects.overview'),
            U(r'/project/([a-z0-9_-]*)', project.ProjectHandler, name='project.overview'),
            U(r'/project/([a-z0-9_-]*)/queue', project.QueueHandler, name='project.queue'),
            U(r'/project/([a-z0-9_-]*)/claims', project.ClaimsHandler, name='project.claims'),
            U(r'/project/([a-z0-9_-]*)/settings', project.SettingsHandler, name='project.settings'),
            U(r'/project/([a-z0-9_-]*)/delete', project.DeleteHandler, name='project.delete'),
            U(r'/api/live_stats', api.LiveStatsHandler, name='api.live_stats'),
            U(r'/api/project_settings', api.ProjectSettingsHandler, name='api.project_settings'),
            U(r'/api/get', api.GetHandler, name='api.get'),
            U(r'/api/done', api.DoneHandler, name='api.done'),
            U(r'/api/error', api.ErrorHandler, name='api.error'),
            U(r'/status', StatusHandler, name='index.status'),
        ]

        static_path = os.path.join(
            os.path.dirname(__file__), 'static'
        )
        template_path = os.path.join(
            os.path.dirname(__file__), 'template'
        )

        ui_modules = {
            'Form': FormUIModule,
        }

        super(Application, self).__init__(
            handlers,
            static_path=static_path,
            template_path=template_path,
            login_url='/admin/login',
            ui_modules=ui_modules,
            **kwargs
        )

        def job_task():
            model.Item.release_old(autoqueue_only=True)
            model.Budget.calculate_budgets()

        job_task()

        self._job_timer = tornado.ioloop.PeriodicCallback(
            job_task,
            60 * 1000
        )
        self._job_timer.start()

    def checkout_item(self, username, ip_address=None, version=-1, client_version=-1):
        if model.BlockedUser.is_username_blocked(username, ip_address):
            raise UserIsBanned()

        return model.checkout_item(username, ip_address, version, client_version)

    def checkin_item(self, item_id, tamper_key, results):
        model.checkin_item(item_id, tamper_key, results)

    def report_error(self, item_id, tamper_key, message):
        model.report_error(item_id, tamper_key, message)


class IndexHandler(BaseHandler):
    def get(self):
        lifetime_list = [
            (username, found, scanned)
            for username, (found, scanned)
            in Stats.instance.get_lifetime().items()
        ]
        lifetime_list = sorted(lifetime_list, key=lambda item: item[2],
                               reverse=True)

        stats = {
            'global': Stats.instance.get_global(),
            'lifetime': lifetime_list[:300],
            'live': Stats.instance.get_live(),
        }

        self.render('index.html', stats=stats)


class StatusHandler(BaseHandler):
    GIT_HASH = model.get_git_hash()

    def get(self):
        projects = list([
            model.Project.get_plain(name)
            for name in model.Project.all_project_names()])
        project_stats = Stats.instance.get_project()

        self.render('status.html', projects=projects, services=registry,
                    project_stats=project_stats,
                    git_hash=self.GIT_HASH)
