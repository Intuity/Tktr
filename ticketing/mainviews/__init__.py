import logging
from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid.view import notfound_view_config
from pyramid.view import forbidden_view_config
from pyramid.view import view_config
from ticketing.macros.baselayout import BaseLayout
from pyramid.httpexceptions import HTTPFound

logging = logging.getLogger("ticketing")

class ExceptionViews(BaseLayout):

    def __init__(self, context=None, request=None):
        self.context = context
        self.request = request

    @notfound_view_config(renderer="templates/404.pt")
    def view_404(self):
        logging.error("A 404 error occurred: %s" % self.context)
        return {}

    @forbidden_view_config(renderer="templates/403.pt")
    def view_403(self):
        # Get intended path
        if not self.user:
            self.request.session.flash("You will need to login before you can access other parts of the ticketing system.", "info")
            return HTTPFound(location=self.request.route_path("welcome"))
        return {}

    @view_config(
        context=Exception,
        permission=NO_PERMISSION_REQUIRED,
        renderer="templates/500.pt"
    )
    def view_500(self):
        logging.error("A 500 error occurred: %s" % self.context, exc_info=(self.context))
        return {
            "error": str(self.context)
        }

def includeme(config):
    config.add_route("welcome", "/")
    config.add_route("logout", "/logout")
    config.add_route("branch_flow", "/branch_flow")
    config.add_route("branch_raven_flow", "/branch_raven_flow")
    config.add_route("read_purchase_agreement", "/purchase_agreement")
    config.add_route("read_privacy_policy", "/privacy_policy")
    config.add_route("read_cookie_policy", "/cookie_policy")
    config.add_route("account_signup", "/account_signup")
    
