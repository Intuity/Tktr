from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember, forget
from pyramid.view import view_config

from ticketing.macros.baselayout import BaseLayout
from ticketing.models import Ticketing, User, salt_password, PROP_KEYS, Group
from ticketing.profile.models import UserProfile
from ticketing.queue.queue import Queue

class Welcome(BaseLayout):

    @view_config(
        route_name="welcome",
        context="ticketing.models.Ticketing",
        permission="public",
        renderer="templates/welcome.pt"
    )
    def welcome_view(self):
        # Check whether the site is setup?
        if not "properties" in self.request.root.__dict__:
            print "Need to setup site!"
            return HTTPFound(location=self.request.route_path("setup"))
        # If queue enabled, deal with it
        elif not self.has_queued:
            return HTTPFound(location=self.request.route_path("queue"))
        # Check queue/active status
        elif Queue(self.request).timed_out():
            return HTTPFound(self.request.route_path("purchase_timeout"))
        elif "user_id" in self.request.session and self.request.session["user_id"] in self.context.users:
            return HTTPFound(location=self.request.route_path("branch_flow"))
        return {}

    @view_config(
        route_name="welcome",
        context="ticketing.models.Ticketing",
        permission="public",
        request_method="POST"
    )
    def welcome_view_do(self):
        if not self.has_queued:
            return HTTPFound(location=self.request.route_path("queue"))
        # Get username and password
        username = self.request.POST["username"].lower()
        password = self.request.POST["password"]
        # Check if user exists and is non-raven
        if not username in self.request.root.users:
            self.request.session.flash("Your username or password was incorrect", "error")
            return HTTPFound(location=self.request.route_path("welcome"))
        user = self.request.root.users[username]
        if user.profile != None and user.profile.raven_user:
            self.request.session.flash("Your account appears to be a Raven account, please use the Raven login instead.", "error");
            return HTTPFound(location=self.request.route_path("welcome"))
        # Check password
        if user.password != salt_password(password, user.password_salt):
            self.request.session.flash("Your username or password was incorrect", "error")
            return HTTPFound(location=self.request.route_path("welcome"))
        # Ok, this all looks ok - lets go!
        header = remember(self.request, user.__name__)
        self.request.session["user_id"] = user.__name__
        if user.profile == None:
            profile = UserProfile()
            profile.raven_user = False
            profile.__parent__ = user
            profile.__name__ = user.__name__ + "-profile"
            user.profile = profile
            return HTTPFound(location=self.request.route_path('user_profile_edit'), headers=header)
        elif None in [user.profile.dob, user.profile.fullname]:
            return HTTPFound(location=self.request.route_path('user_profile_edit'), headers=header)
        else:
            return HTTPFound(location=self.request.route_path('user_profile'), headers=header)

    @view_config(
        name="start_raven",
        permission="public",
    )
    def start_raven_view(self):
        if not self.has_queued:
            return HTTPFound(location=self.request.route_path("queue"))
        self.request.session["raven_route"] = self.request.route_path("branch_raven_flow")
        return HTTPFound(location=self.request.route_path("raven_first_stage"))
    
    @view_config(
        route_name="branch_raven_flow",
        permission="raven",
        context=Ticketing,
    )
    def branch_raven_flow_view(self):
        if not self.has_queued:
            return HTTPFound(location=self.request.route_path("queue"))
        # Choose raven path, create a user if necessary
        users = self.context.users.values()
        raven_obj = self.request.session["raven"]
        # Should select a single user
        user = [x for x in users if x.profile != None and x.profile.crsid != None and x.profile.crsid.lower() == raven_obj.raven_crsid.lower()]
        if len(user) == 0:
            # Add in the basic user and setup privileges
            raven = self.request.session["raven"]
            self.request.session.pop("raven", None)
            user = User()
            user.username = user.__name__ = raven.raven_crsid.lower()
            # Attach profile
            profile = UserProfile()
            profile.raven_user = True
            profile.crsid = raven.raven_crsid.lower()
            profile.__parent__ = user
            profile.__name__ = user.__name__ + "-profile"
            profile.email = profile.crsid + "@cam.ac.uk"
            user.profile = profile
            # Attach to a group
            # - Check whether any group has a filter for this user
            group = None
            for grp in self.request.root.groups.values():
                if user.username in grp.user_filter:
                    group = grp
                    break
            # - If we didn't find a group then filter into generic Raven group
            if group == None:
                # If a 'current' Raven member (an active student/staff member) filter into one group
                if "raven_current" in self.request.session and self.request.session["raven_current"]:
                    group = self.context.groups["raven"]
                else:
                    group = self.context.groups["raven_alumni"]
            user.__parent__ = group
            group.members.append(user)
            # Attach to root
            self.context.users[user.__name__] = user
            # Attach status
            self.request.session.pop("raven", None)
            self.request.session.pop("raven_current", None)
            self.request.session["user_id"] = user.__name__
            header = remember(self.request, user.__name__)
            # Update queuer object with user id
            queuer = self.queue_item
            if queuer != None:
                queuer.user_id = user.__name__
            return HTTPFound(location=self.request.route_path('user_profile_edit'), headers=header)
        elif user[0].profile == None:
            user = user[0]
            # Attach profile
            profile = UserProfile()
            profile.raven_user = True
            profile.crsid = raven.raven_crsid.lower()
            profile.__parent__ = user
            profile.__name__ = user.__name__ + "-profile"
            profile.email = profile.crsid + "@cam.ac.uk"
            user.profile = profile
            # Attach status
            self.request.session.pop("raven", None)
            self.request.session["user_id"] = user.__name__
            header = remember(self.request, user.__name__)
            # Update queuer object with user id
            queuer = self.queue_item
            if queuer != None:
                queuer.user_id = user.__name__
            return HTTPFound(location=self.request.route_path('user_profile_edit'), headers=header)
        elif None in [user[0].profile.dob, user[0].profile.fullname]:
            # Attach status
            user = user[0]
            self.request.session.pop("raven", None)
            self.request.session["user_id"] = user.__name__
            header = remember(self.request, user.__name__)
            # Update queuer object with user id
            queuer = self.queue_item
            if queuer != None:
                queuer.user_id = user.__name__
            return HTTPFound(location=self.request.route_path('user_profile_edit'), headers=header)
        else:
            user = user[0]
            # Load the users id into the session
            self.request.session.pop("raven", None)
            self.request.session["user_id"] = user.__name__
            header = remember(self.request, user.__name__)
            # Update queuer object with user id
            queuer = self.queue_item
            if queuer != None:
                queuer.user_id = user.__name__
            return HTTPFound(location=self.request.route_path('user_profile'), headers=header)
    
    @view_config(
        route_name="branch_flow",
        permission="basic",
        context=Ticketing,
    )
    def branch_flow_view(self):
        user = self.context.users[self.request.session["user_id"]]
        if user.profile == None or None in [user.profile.dob, user.profile.fullname]:
            return HTTPFound(location=self.request.route_path('user_profile_edit'))
        else:
            return HTTPFound(location=self.request.route_path('user_profile'))

    @view_config(route_name="logout", permission="public")
    def logout_view(self):
        header = forget(self.request)
        self.request.session.pop("user_id", None)
        self.request.session.pop("active_id", None)
        self.request.session.pop("payment_id", None)
        return HTTPFound(location=self.request.route_path("welcome"), headers=header)

    @view_config(
        route_name="read_purchase_agreement",
        context=Ticketing,
        permission="public",
        renderer="templates/purchase_agreement.pt"
    )
    def purchase_agreement_view(self):
        agreement_doc = PROP_KEYS.getProperty(self.request, PROP_KEYS.PURCHASE_AGREEMENT)
        return {
            "document": agreement_doc
        }

    @view_config(
        route_name="read_privacy_policy",
        context=Ticketing,
        permission="public",
        renderer="templates/privacy_policy.pt"
    )
    def privacy_policy_view(self):
        agreement_doc = PROP_KEYS.getProperty(self.request, PROP_KEYS.PRIVACY_POLICY)
        return {
            "document": agreement_doc
        }

    @view_config(
        route_name="read_cookie_policy",
        context=Ticketing,
        permission="public",
        renderer="templates/cookie_policy.pt"
    )
    def cookie_policy_view(self):
        agreement_doc = PROP_KEYS.getProperty(self.request, PROP_KEYS.COOKIE_POLICY)
        return {
            "document": agreement_doc
        }

