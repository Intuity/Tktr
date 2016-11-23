import logging
from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember
from pyramid.view import view_config

from ticketing.models import Ticketing, salt_password
from ticketing.macros.baselayout import BaseLayout

logging = logging.getLogger("ticketing")

class APILoginView(BaseLayout):

    @view_config(
        route_name="api_login",
        context=Ticketing,
        permission="public",
        renderer="templates/login.pt"
    )
    def api_login_view(self):
        return {}

    @view_config(
        route_name="api_login",
        context="ticketing.models.Ticketing",
        permission="public",
        request_method="POST"
    )
    def api_login_view_do(self):
        # Get username and password
        username = self.request.POST["username"].lower()
        password = self.request.POST["password"]
        # Check if user exists and is non-raven
        if not username in self.request.root.users:
            self.request.session.flash("Your username or password was incorrect", "error")
            return HTTPFound(location=self.request.route_path("api_login"))
        user = self.request.root.users[username]
        if user.profile != None and user.profile.raven_user:
            self.request.session.flash("Your account appears to be a Raven account, please use the Raven login instead.", "error");
            return HTTPFound(location=self.request.route_path("api_login"))
        # Check password
        if user.password != salt_password(password, user.password_salt):
            self.request.session.flash("Your username or password was incorrect", "error")
            return HTTPFound(location=self.request.route_path("api_login"))
        # Ok, this all looks ok - lets go!
        header = remember(self.request, user.__name__)
        self.request.session["user_id"] = user.__name__
        return HTTPFound(location=self.request.route_path('api_token_issue'), headers=header)

    @view_config(
        route_name="api_login_raven",
        permission="public"
    )
    def api_login_raven_view(self):
        self.request.session["raven_route"] = self.request.route_path("api_login_raven_return")
        return HTTPFound(location=self.request.route_path("raven_first_stage"))

    @view_config(
        route_name="api_login_raven_return",
        permission="raven",
        context=Ticketing
    )
    def api_login_raven_return_view(self):
        # Choose raven path, create a user if necessary
        users = self.context.users.values()
        raven_obj = self.request.session["raven"]
        # Should select a single user
        user = [x for x in users if x.profile != None and x.profile.crsid != None and x.profile.crsid.lower() == raven_obj.raven_crsid.lower()]
        if len(user) == 0:
            self.request.session.flash("No account exists for this Raven login", "error")
            return HTTPFound(location=self.request.route_path("api_login"))
        else:
            user = user[0]
            header = remember(self.request, user.__name__)
            self.request.session["user_id"] = user.__name__
            return HTTPFound(location=self.request.route_path('api_token_issue'), headers=header)
