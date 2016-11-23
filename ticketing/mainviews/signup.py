from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember
from pyramid.view import view_config

from ticketing.macros.baselayout import BaseLayout
from ticketing.models import User, salt_password
from ticketing.profile.models import UserProfile
from ticketing.boxoffice.coding import Coding
from ticketing.email.templates import GenericEmail

from lepl.apps.rfc3696 import Email
import re

class Welcome(BaseLayout):

    @view_config(
        route_name="account_signup",
        context="ticketing.models.Ticketing",
        permission="public",
        renderer="templates/signup.pt"
    )
    def signup_view(self):
        if not self.public_signup_enabled:
            self.request.session.flash("Public sign-ups are not currently enabled!", "error")
            return HTTPFound(location=self.request.route_path('welcome'))
        # If form data submitted
        if "submit" in self.request.POST:
            email = (self.request.POST["email"] if "email" in self.request.POST and len(self.request.POST["email"]) > 0 else None)
            username = (self.request.POST["username"] if "username" in self.request.POST and len(self.request.POST["username"]) > 0 else None)
            pwd_one = (self.request.POST["password"] if "password"in self.request.POST and len(self.request.POST["password"]) > 0  else None)
            pwd_two = (self.request.POST["confirm_password"] if "confirm_password" in self.request.POST and len(self.request.POST["confirm_password"]) > 0 else None)
            discount_code = (self.request.POST["discount_code"] if "discount_code" in self.request.POST and len(self.request.POST["discount_code"]) > 0 else None)
            # Check if all fields filled
            if email == None or username == None or pwd_one == None or pwd_two == None:
                self.request.session.flash("One or more fields was not filled, please try again.", "error")
                return {
                    "email": email,
                    "username": username,
                    "discount_code": discount_code
                }
            # Now run additional checks
            validator = Email()
            if not validator(email):
                self.request.session.flash("Please enter a valid email address.", "error")
                return {
                    "email": email,
                    "username": username,
                    "discount_code": discount_code
                }
            # Username checks
            username = username.lower()
            if len(username) < 3 or " " in username:
                self.request.session.flash("Please enter a valid username of more than 3 characters and containing no spaces.", "error")
                return {
                    "email": email,
                    "username": username,
                    "discount_code": discount_code
                }
            if username in self.request.root.users or (re.match(r"^[a-zA-Z]+[0-9]+$", username) != None):
                self.request.session.flash("A user already exists with the username you specified, please try again.", "error")
                return {
                    "email": email,
                    "username": username,
                    "discount_code": discount_code
                }
            # Password checks
            if pwd_one != pwd_two:
                self.request.session.flash("Your passwords do not appear to match, please try again.", "error")
                return {
                    "email": email,
                    "username": username,
                    "discount_code": discount_code
                }
            if len(pwd_one) < 5 or (re.match(r"(?=.{6,}).*", pwd_one) == None):
                self.request.session.flash("Your password is too short or not complex enough, please enter a stronger password.", "error")
                return {
                    "email": email,
                    "username": username,
                    "discount_code": discount_code
                }
            # Passed all checks - create an account...
            group = self.request.root.groups['ungrouped']
            # - See if we can find a discount group
            if discount_code != None:
                found_discount = False
                for group_key in self.request.root.groups:
                    test_group = self.request.root.groups[group_key]
                    if test_group.access_code != None and len(test_group.access_code) > 0 and test_group.access_code == discount_code:
                        group = test_group
                        found_discount = True
                        break
                if not found_discount:
                    self.request.session.flash("The discount code entered is not valid, please check it and try again.", "error")
                    return {
                        "email": email,
                        "username": username,
                        "discount_code": discount_code
                    }
            # - Now setup user
            user = User()
            user.username = user.__name__ = username
            user.password_salt = Coding().generateUniqueCode()
            user.password = salt_password(pwd_one, user.password_salt)
            user.profile = UserProfile()
            user.profile.__parent__ = user
            user.profile.raven_user = False
            user.profile.email = email
            user.__parent__ = group
            group.members.append(user)
            self.request.root.users[user.__name__] = user
            # ...send an email telling them about their new account...
            emailer = GenericEmail(self.request)
            emailer.compose_and_send(
                "Account Created",
                """Thank you for creating an account on our ticketing system, this email is just to remind you that your username is %s. No further action is required.""" 
                % (user.username),
                user.__name__
            )
            # ...and finally login
            header = remember(self.request, user.__name__)
            self.request.session["user_id"] = user.__name__
            return HTTPFound(location=self.request.route_path('user_profile_edit'), headers=header)
        return {
            "email": None,
            "username": None,
            "discount_code": None
        }