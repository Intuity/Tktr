import cgi
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pyramid.httpexceptions import HTTPFound
from pyramid.response import Response
from pyramid.view import view_config
import re

from ticketing.boxoffice.coding import Coding
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import Group, User, salt_password, PROP_KEYS
from ticketing.profile.models import UserProfile, PostalAddress
from ticketing.email.templates import GenericEmail
from ticketing.boxoffice.download import TicketDownload

class Accounts(BaseLayout):

    @view_config(
        route_name="admin_accounts",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/accounts.pt"
    )
    def accounts_view(self):
        return {
            "groups": sorted(self.request.root.groups.values(), key=lambda x: x.name)
        }

    @view_config(
        route_name="admin_accounts_export",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/account_export.pt"
    )
    def account_export_view(self):
        if "submit" in self.request.POST:
            opt_keys = [
                "opt_username", "opt_salutation", "opt_fullname", "opt_crsid", "opt_email", "opt_phone_num", "opt_dob", 
                "opt_college", "opt_grad", "opt_postal", "opt_tickets", "opt_completed", "opt_notes", "opt_payments"
            ]
            friendly = {
                "opt_username": "Username", "opt_salutation": "Salutation", "opt_fullname": "Full Name", "opt_crsid": "CRSid", 
                "opt_email": "Email Address", "opt_phone_num": "Phone Number", "opt_dob": "Date of Birth", "opt_college": "College", 
                "opt_grad": "Graduate Status", "opt_postal": "Postal Address", "opt_tickets": "Num Tickets", 
                "opt_completed": "Profiles Completed", "opt_notes": "Notes", "opt_payments": "Pending Payments"
            }
            chosen = []
            options = {}
            # Grab all keys from the post request
            for key in opt_keys:
                if key in self.request.POST and self.request.POST[key].lower() == "export":
                    options[key] = True
                    chosen.append(friendly[key])
                else:
                    options[key] = False
            # Get the group - if any was specified
            group_id = self.request.POST["group"]
            accounts = []
            if group_id != "any":
                group = self.request.root.groups[group_id]
                for user in group.members:
                    accounts.append(user)
            else:
                accounts = self.request.root.users.values()
            # Start CSV file
            file = ""
            file += "Group Chosen," + ("Any" if group_id == "any" else self.request.root.groups[group_id].name) + "\n\n"
            file += ",".join(chosen) + "\n"
            # Now start to perform filtering operation
            has_tickets = ("has_tickets" in self.request.POST and self.request.POST["has_tickets"] == "hastickets")
            for user in accounts:
                if has_tickets and len(user.tickets) == 0:
                    continue
                row = []
                if options["opt_username"]:
                    row.append((user.username if user.username and user.username else user.__name__))
                if options["opt_salutation"]:
                    row.append((user.profile.title if user.profile and user.profile.title else "-"))
                if options["opt_fullname"]:
                    row.append((user.profile.fullname if user.profile and user.profile.fullname else "-"))
                if options["opt_crsid"]:
                    row.append((user.profile.crsid if user.profile and user.profile.crsid and user.profile.raven_user else "-"))
                if options["opt_email"]:
                    row.append((user.profile.email if user.profile and user.profile.email else "-"))
                if options["opt_phone_num"]:
                    row.append((("\" " + user.profile.phone_number + " \"") if user.profile and user.profile.phone_number else "-"))
                if options["opt_dob"]:
                    row.append((user.profile.dob.strftime("%d/%m/%Y") if user.profile and user.profile.dob else "-"))
                if options["opt_college"]:
                    row.append((user.profile.college if user.profile and user.profile.college else "-"))
                if options["opt_grad"]:
                    row.append((user.profile.grad_status if user.profile and user.profile.grad_status else "-"))
                if options["opt_postal"]:
                    row.append((("\"" + user.profile.address.export() + "\"") if user.profile and user.profile.address else "-"))
                if options["opt_tickets"]:
                    row.append((("%i" % len(user.tickets)) if user.tickets else "0"))
                if options["opt_completed"]:
                    all_complete = True
                    reason = None
                    # Check their profile first!
                    if not user.profile.complete:
                        all_complete = False
                        reason = "User profile incomplete"
                    else:
                        # Check all guests
                        for ticket in user.tickets:
                            if ticket.guest_info == None or not ticket.guest_info.complete:
                                all_complete = False
                                reason = ticket.__name__ + " Incomplete"
                                break
                    row.append(("Yes" if all_complete else reason))
                if options["opt_notes"]:
                    row.append((user.notes.replace("\n"," ") if user.notes else "-"))
                if options["opt_payments"]:
                    all_paid = True
                    for payment in user.payments:
                        if not payment.paid:
                            all_paid = False
                            break
                    row.append(("No" if all_paid else "Yes"))
                file += ",".join(row) + "\n"
            filename = "accounts-export-%s.csv" % datetime.now().isoformat()
            return Response(
                body=file,
                status=200,
                content_type="text/csv",
                content_disposition="attachment; filename=\"%s\"" % filename,
            )
        return {
            "groups": sorted(self.request.root.groups.values(), key=lambda x: x.name)
        }

    @view_config(
        route_name="admin_group_add",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/add_group.pt"
    )
    @view_config(
        route_name="admin_group_edit",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/add_group.pt"
    )
    def add_group_view(self):
        name = None
        privilege = None
        access_code = None
        edit = False
        if "group_id" in self.request.matchdict and self.request.matchdict["group_id"] in self.request.root.groups:
            group = self.request.root.groups[self.request.matchdict["group_id"]]
            if not group.can_delete:
                self.request.session.flash("This group cannot be edited!", "error")
                return HTTPFound(location=self.request.route_path("admin_accounts"))
            name = group.name
            access_code = group.access_code
            privilege = group.privileges[0]
            edit = True
        return {
            "name": name, 
            "privilege": privilege,
            "access_code": access_code,
            "edit": edit
        }

    @view_config(
        route_name="admin_group_add",
        context="ticketing.models.Ticketing",
        permission="admin",
        request_method="POST",
        renderer="templates/add_group.pt"
    )
    @view_config(
        route_name="admin_group_edit",
        context="ticketing.models.Ticketing",
        permission="admin",
        request_method="POST",
        renderer="templates/add_group.pt"
    )
    def add_group_view_do(self):
        name = self.request.POST["name"]
        privilege = self.request.POST["privilege"]
        access_code = self.request.POST["access_code"].replace(" ", "")
        if len(name.replace(" ","")) < 2:
            self.request.session.flash("The name entered is not valid, please try again.", "error")
            return {"name": None, "privilege": privilege}
        if privilege not in ["basic", "staff", "committee", "admin"]:
            self.request.session.flash("The privilege chosen is not valid, please try again.", "error")
            return {"name": name, "privilege": None}
        if len(access_code) == 0:
            access_code = None
        else:
            access_code = re.sub('[\W_]+', '', access_code)
        if "group_id" in self.request.matchdict and self.request.matchdict["group_id"] in self.request.root.groups:
            group = self.request.root.groups[self.request.matchdict["group_id"]]
            group.name = name
            group.access_code = access_code
            group.privileges = [privilege]
            group._p_changed = True
            self.request.session.flash("Group updated successfully!", "info")
        else:
            # Create a new group
            group = Group()
            group.name = name
            group.privileges = [privilege]
            group.access_code = access_code
            group.__name__ = Coding().generateUniqueCode(withdash=False)
            group.__parent__ = self.request.root
            self.request.root.groups[group.__name__] = group
            self.request.root.groups._p_changed = True
            self.request.session.flash("Group added successfully!", "info")
        return HTTPFound(location=self.request.route_path("admin_accounts"))

    @view_config(
        route_name="admin_group_delete",
        context="ticketing.models.Ticketing",
        permission="admin"
    )
    def delete_group_view(self):
        if not self.request.matchdict["group_id"] in self.request.root.groups:
            self.request.session.flash("The group you specified does not exist on the system.", "error")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        group = self.request.root.groups[self.request.matchdict["group_id"]]
        if not group.can_delete:
            self.request.session.flash("Cannot remove this group as it is protected!")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        # Move all members into the "ungrouped" group
        ungrouped = self.request.root.groups["ungrouped"]
        for member in group.members:
            ungrouped.members.append(member)
            member.__parent__ = ungrouped
        ungrouped.members._p_changed = True
        # Unlink the group
        self.request.root.groups.pop(self.request.matchdict["group_id"], None)
        return HTTPFound(location=self.request.route_path("admin_accounts"))

    @view_config(
        route_name="admin_group_filter",
        context="ticketing.models.Ticketing",
        renderer="templates/group_filter.pt",
        permission="admin"
    )
    def group_filter_view(self):
        if not self.request.matchdict["group_id"] in self.request.root.groups:
            self.request.session.flash("The group you specified does not exist on the system.", "error")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        group = self.request.root.groups[self.request.matchdict["group_id"]]
        # Act on a removal action
        if "action" in self.request.GET:
            if self.request.GET["action"] == "remove":
                username = str(self.request.GET["username"])
                if username in group.user_filter:
                    group.user_filter.remove(username)
                    self.request.session.flash("The user %s has been removed from the filter." % username, "info")
                else:
                    self.request.session.flash("Username does not exist in filter.", "error")
            elif self.request.GET["action"] == "clear":
                copy = []
                for user in group.user_filter: copy.append(user)
                for user in copy: group.user_filter.remove(user)
                self.request.session.flash("Filter cleared successfully.", "info")
        group_users = []
        for user in group.members:
            group_users.append(user.username)
        return {
            "group": group,
            "group_users": group_users
        }

    @view_config(
        route_name="admin_group_filter",
        context="ticketing.models.Ticketing",
        renderer="templates/group_filter.pt",
        permission="admin",
        request_method="POST"
    )
    def group_filter_view_do(self):
        if not self.request.matchdict["group_id"] in self.request.root.groups:
            self.request.session.flash("The group you specified does not exist on the system.", "error")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        group = self.request.root.groups[self.request.matchdict["group_id"]]
        if "action" in self.request.GET:
            if self.request.GET["action"].lower() == "upload":
                if not "filterfile" in self.request.POST or not isinstance(self.request.POST["filterfile"], cgi.FieldStorage):
                    self.request.session.flash("You did not upload a filter file!", "error")
                else:
                    # Ok grab the data and run it!
                    file_handle = self.request.POST["filterfile"].file
                    read_data = None
                    while 1:
                        chunk = file_handle.read(2<<16)
                        if not chunk: break
                        if read_data == None: read_data = chunk
                        else: read_data += chunk
                    if len(read_data) > 0:
                        # Split by line
                        lines = read_data.split("\n")
                        pattern = re.compile("[\W_]+")
                        cleaned = []
                        # Generate clean usernames
                        for line in lines:
                            cleaned = pattern.sub("", line).lower()
                            # Now this to the existing filter
                            if not cleaned in group.user_filter:
                                group.user_filter.append(cleaned)
                    # Ok all good
                    self.request.session.flash("Filter updated successfully.", "info")
            elif self.request.GET["action"] == "add":
                pattern = re.compile("[\W_]+")
                username = pattern.sub("", self.request.POST["username"]).lower()
                if username in group.user_filter:
                    self.request.session.flash("User is already part of the filter.", "error")
                else:
                    group.user_filter.append(username)
                    self.request.session.flash("User has been added to the filter successfully!", "info")
            # Run a check for existing users in other groups that should be in this one
            for grp in self.request.root.groups.values():
                if grp == group: continue # Don't worry about our group - that'd be silly!
                to_move = []
                for user in grp.members:
                    if user.username in group.user_filter:
                        to_move.append(user)
                for user in to_move:
                    group.members.append(user)
                    user.__parent__ = group
                    grp.members.remove(user)
        # Generate group users
        group_users = []
        for user in group.members:
            group_users.append(user.username)
        return {
            "group": group,
            "group_users": group_users
        }
            

    @view_config(
        route_name="admin_users",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/users.pt"
    )
    def users_view(self):
        users = self.context.users.values()

        # Support filtering of users
        if "filter" in self.request.GET:
            filter_type = self.request.GET["filter"]
            filter_value = self.request.GET["value"].lower()
            if filter_type == "crsid":
                users = [x for x in users if x.profile != None and x.profile.crsid != None and filter_value in x.profile.crsid.lower()]
            elif filter_type == "name":
                users = [x for x in users if x.profile != None and x.profile.fullname != None and filter_value in x.profile.fullname.lower()]
            elif filter_type == "email":
                users = [x for x in users if x.profile != None and x.profile.email != None and filter_value in x.profile.email.lower()]
            elif filter_type == "college":
                users = [x for x in users if x.profile != None and x.profile.college != None and filter_value in x.profile.college.lower()]
            elif filter_type == "username":
                users = [x for x in users if filter_value in x.username.lower()]
            elif filter_type == "group":
                users = [x for x in users if filter_value in x.__parent__.name.lower()]
            return {
                "users": users,
                "filter": filter_type,
                "value": filter_value,
            }

        return {
            "users": users,
            "filter": None,
            "value": "",
        }

    @view_config(
        route_name="admin_view_user",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/user_profile.pt"
    )
    def user_profile_view(self):
        if not self.request.matchdict["user_id"] in self.request.root.users:
            self.request.session.flash("Requested user does not exist!", "error")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        user = self.request.root.users[self.request.matchdict["user_id"]]
        if "action" in self.request.GET:
            if self.request.GET["action"] == "counttotal":
                user.total_tickets = len(user.tickets)
                self.request.session.flash("Recounted the total number of tickets this user has.", "info")
            elif self.request.GET["action"] == "sendtickets":
                emailer = GenericEmail(self.request)
                emailer.compose_and_send(
                    "Event Tickets",
                    """Please find the tickets you have purchased attached as a PDF to this email. Please download and print-out the tickets and bring them with you to the event.""",
                    user.__name__,
                    pdf_attachment=TicketDownload(self.request).user_tickets_pdf(user)
                )
                self.request.session.flash("All tickets have been sent to this user via email.", "info")
        if user.profile == None:
            self.request.session.flash("Requested user had not setup a profile, now has a blank profile.", "info")
            user.profile = UserProfile()
            user.profile.__parent__ = user
        return {
            "chosen_user": user
        }

    @view_config(
        route_name="admin_user_profile_edit",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/user_profile_edit.pt"
    )
    def user_profile_edit_view(self):
        if not self.request.matchdict["user_id"] in self.request.root.users:
            self.request.session.flash("Requested user does not exist!", "error")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        user = self.request.root.users[self.request.matchdict["user_id"]]
        if "submit" in self.request.POST:
            problem = False
            user.profile.title = self.request.POST["title"]
            if user.profile.title == "Other":
                user.profile.title = self.request.POST["othertitle"]
            user.profile.forename = self.request.POST["forename"]
            user.profile.surname = self.request.POST["surname"]
            if "email" in self.request.POST:
                user.profile.email = self.request.POST["email"]
            user.profile.phone_number = self.request.POST["phone_number"]
            day = int(float(self.request.POST["dob_day"]))
            month = int(float(self.request.POST["dob_month"]))
            year = int(float(self.request.POST["dob_year"]))
            if day < 1 or day > 31 or month < 1 or month > 12:
                problem = True
                self.request.session.flash("Invalid date of birth, please try again", "error")
            dob = datetime(year, month, day)
            event_date = PROP_KEYS.getProperty(self.request, PROP_KEYS.EVENT_DATE)
            minimum_age = PROP_KEYS.getProperty(self.request, PROP_KEYS.MINIMUM_AGE)
            if relativedelta(event_date, dob).years < minimum_age:
                problem = True
                self.request.session.flash("Guests must be aged %i on the day of the event, age entered is too young." % minimum_age, "error")
            if not problem:
                user.profile.dob = dob
                user.profile.raven_user = ("atcambridge" in self.request.POST and self.request.POST["atcambridge"] == "yes")
                if user.profile.raven_user:
                    user.profile.crsid = self.request.POST["crsid"]
                    user.profile.email = user.profile.crsid + "@cam.ac.uk"
                    user.profile.college = self.request.POST["college"]
                    user.profile.grad_status = self.request.POST["grad_status"]
                else:
                    if user.profile.address == None:
                        user.profile.address = PostalAddress()
                        user.profile.address.__parent__ = user
                    user.profile.address.line_one = self.request.POST["lineone"]
                    user.profile.address.line_two = self.request.POST["linetwo"]
                    user.profile.address.city = self.request.POST["city"]
                    user.profile.address.county = self.request.POST["county"]
                    user.profile.address.country = self.request.POST["country"]
                    user.profile.address.postal_code = self.request.POST["postal_code"]
                return HTTPFound(location=self.request.route_path("admin_view_user", user_id=user.__name__))
        if user.profile == None:
            user.profile = UserProfile()
            user.profile.__parent__ = user
        info = user.profile
        dob = datetime.now()
        if info.dob != None:
            dob = info.dob
        # Address
        lineone = linetwo = city = county = country = postal_code = ""
        if info.address != None:
            lineone = info.address.line_one
            linetwo = info.address.line_two
            city = info.address.city
            county = info.address.county
            country = info.address.country
            postal_code = info.address.postal_code
        return {
            "user_id": user.__name__,
            "title": info.title,
            "othertitle": (info.title not in ["Mr", "Mrs", "Miss", "Ms", "Dr", "Prof", "Rev"] and len(info.title) > 0),
            "forename": info.forename,
            "surname": info.surname,
            "phone_number": info.phone_number,
            "email": info.email,
            "dob_year": dob.year,
            "dob_month": dob.month,
            "dob_day": dob.day,
            "atcambridge": info.raven_user,
            "crsid": info.crsid,
            "college": info.college,
            "grad_status": info.grad_status,
            "needs_address": (info.raven_user == False),
            "lineone": lineone,
            "linetwo": linetwo,
            "city": city,
            "county": county,
            "country": country,
            "postal_code": postal_code,
        }

    @view_config(
        route_name="admin_user_password",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/password.pt"
    )
    def user_password_view(self):
        if not "user_id" in self.request.matchdict and not self.request.matchdict["user_id"] in self.request.root.users:
            self.request.session.flash("Requested user does not exist!", "error")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        user = self.request.root.users[self.request.matchdict["user_id"]]
        # Check actually allowed to change password
        if user.profile != None and user.profile.raven_user:
            self.request.session.flash("This user is authenticated via Raven and therefore does not have a password stored in the system.", "error")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        # Act on data being passed from view
        if "submit" in self.request.POST:
            password_one = self.request.POST["password_one"]
            password_two = self.request.POST["password_two"]
            if password_one != password_two:
                self.request.session.flash("You have not entered the same password twice, please try again.", "error")
                return {
                    "user": user
                }
            elif len(password_one) < 6:
                self.request.session.flash("For security reasons you must enter a password of 6 letters or more.", "error")
                return {
                    "user": user
                }
            # Generate a new salt, salt the password and store it
            user.password_salt = Coding().generateUniqueCode(withdash=False)
            user.password = salt_password(password_one, user.password_salt)
            self.request.session.flash("%s's password has been successfully changed." % user.username, "info")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        return {
            "user": user,
        }

    @view_config(
        route_name="admin_user_add",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/add_user.pt"
    )
    def user_add_view(self):
        if "submit" in self.request.POST:
            username = self.request.POST["username"].lower().replace(" ","")
            password = self.request.POST["password"]
            userprefix = self.request.POST["userprefix"].lower().replace(" ","")
            numberusers = int(float(self.request.POST["numberusers"]))
            startingpoint = int(float(self.request.POST["startingnumber"]))
            group_key = self.request.POST["group"]
            single = (self.request.POST["singleuser"] == "single")
            # Check username not already in use
            error = True
            if single:
                if username in self.request.root.users:
                    self.request.session.flash("A user with this username already exists.", "error")
                elif group_key not in self.request.root.groups:
                    self.request.session.flash("The group selected is invalid, please try again.", "error")
                elif len(password) < 6:
                    self.request.session.flash("The password you entered is too short, please enter a longer one.", "error")
                elif len(username) < 3:
                    self.request.session.flash("Please enter a username longer than 2 letters.", "error")
                else:
                    error = False
                    # Otherwise we're good, create user
                    group = self.request.root.groups[group_key]
                    user = User()
                    user.username = user.__name__ = username
                    user.password_salt = Coding().generateUniqueCode()
                    user.password = salt_password(password, user.password_salt)
                    user.__parent__ = group
                    group.members.append(user)
                    self.request.root.users[user.__name__] = user
                    self.request.session.flash("User %s has been added successfully!" % username, "info")
                    return HTTPFound(location=self.request.route_path("admin_accounts"))
            else:
                if len(userprefix) < 2:
                    self.request.session.flash("Please enter a prefix of 2 or more characters.", "error")
                elif numberusers <= 1:
                    self.request.session.flash("Please enter a number of users greater than 1.", "error")
                elif startingpoint < 0:
                    self.request.session.flash("Please enter a starting point number greater than or equal to 0.", "error")
                elif group_key not in self.request.root.groups:
                    self.request.session.flash("The group selected is invalid, please try again.", "error")
                else:
                    error = False
                    creds = {}
                    coding = Coding()
                    group = self.request.root.groups[group_key]
                    # Otherwise we're good, create lots of users and passwords
                    for i in range(numberusers):
                        password = coding.genRandomString(size=6).lower()
                        username = ("%s%i%s" % (userprefix, (i + startingpoint), coding.genRandomString(size=2))).lower()
                        creds[username] = password
                        # Create the user
                        newuser = User()
                        newuser.username = newuser.__name__ = username
                        newuser.password_salt = coding.generateUniqueCode()
                        newuser.password = salt_password(password, newuser.password_salt)
                        newuser.__parent__ = group
                        group.members.append(newuser)
                        self.request.root.users[newuser.__name__] = newuser
                    # Confirm a success
                    self.request.session.flash("Successfully added %i users to %s!" % (numberusers, group.name), "info")
                    # - Forward to showing the full list of users that were added
                    self.request.session["added_users"] = creds
                    return HTTPFound(location=self.request.route_path("admin_user_add_list"))
            # Respond to a thrown error
            if error:
                return {
                    "groups": sorted(self.request.root.groups.values(), key=lambda x: x.name),
                    "username": username, "selgroup": group_key, "single": single,
                    "userprefix": userprefix, "numberusers": numberusers, "startingnumber": startingpoint,
                }
        return {
            "groups": sorted(self.request.root.groups.values(), key=lambda x: x.name),
            "username": None, "selgroup": None, "single": True,
            "userprefix": None, "numberusers": 0, "startingnumber": 0,
        }

    @view_config(
        route_name="admin_user_add_list",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/list_added_users.pt"
    )
    def user_add_list_view(self):
        if not "added_users" in self.request.session:
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        users = self.request.session["added_users"]
        group = self.request.root.users[users.keys()[0]].__parent__
        if "type" in self.request.GET and self.request.GET["type"].lower() == "csv":
            csv = "Username,Password,Group\n,,,\n"
            for user in users:
                csv += '%s,%s,%s\n' % (user, users[user], group.name)
            return Response(
                body=csv,
                status=200,
                content_type="text/csv",
                content_disposition="attachment"
            )
        return {
            "usernames": sorted(users.keys()),
            "users": users,
            "group": group
        }

    @view_config(
        route_name="admin_user_delete",
        context="ticketing.models.Ticketing",
        permission="admin"
    )
    def user_delete_view(self):
        if not self.request.matchdict["user_id"] in self.request.root.users:
            self.request.session.flash("Requested user does not exist!", "error")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        else:
            user = self.request.root.users[self.request.matchdict["user_id"]]
            group = user.__parent__
            group.members.remove(user)
            self.request.root.users.pop(user.__name__, None)
            self.request.session.flash("User %s deleted successfully." % user.username, "info")
        return HTTPFound(location=self.request.route_path("admin_accounts"))

    @view_config(
        route_name="admin_user_group",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/user_group.pt"
    )
    def user_group_view(self):
        if not self.request.matchdict["user_id"] in self.request.root.users:
            self.request.session.flash("Requested user does not exist!", "error")
            return HTTPFound(location=self.request.route_path("admin_accounts"))
        user = self.request.root.users[self.request.matchdict["user_id"]]
        if "submit" in self.request.POST:
            group_key = self.request.POST["selgroup"]
            if not group_key in self.request.root.groups:
                self.request.session.flash("The group you selected does not exist.", "error")
            else:
                new_group = self.request.root.groups[group_key]
                current = user.__parent__
                # De-register from one and put into the other
                new_group.members.append(user)
                user.__parent__ = new_group
                current.members.remove(user)
                # Clear the filter on any groups that have this user
                for grp in self.request.root.groups.values():
                    if user.username in grp.user_filter:
                        grp.user_filter.remove(user.username)
                self.request.session.flash("Moved %s to %s successfully" % (user.username, new_group.name), "info")
                return HTTPFound(location=self.request.route_path("admin_accounts"))
        return {
            "user": user,
        }

    @view_config(
        route_name="admin_user_check",
        context="ticketing.models.Ticketing",
        permission="public"
    )
    def check_username_view(self):
        user_id = self.request.matchdict["user_id"].lower()
        if user_id in self.request.root.users:
            return Response("true")
        else:
            return Response("false")
