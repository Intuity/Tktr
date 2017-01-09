from datetime import datetime
from math import floor
from persistent.list import PersistentList
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPFound

from ticketing.email.templates import GenericEmail
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import PROP_KEYS as PROP
from ticketing.models import Document
from ticketing.setup.initial import Initial
from ticketing.queue.queue import Queue


class Settings(BaseLayout):
    
    settings_map = {
        PROP.QUEUE_ENABLED              : { "field": "queue_enabled", "type": "hidden", "test_val": "yes" },
        PROP.MAX_SESSION_TIME           : { "field": "maxsessiontime", "type": "int" },
        PROP.CONCURRENT_NUM             : { "field": "concurrentcustomers", "type": "int" },
        PROP.CUSTOMER_CONTROL_ENABLED   : { "field": "control_enabled", "type": "hidden", "test_val": "yes" },
        PROP.LIMIT_ENABLED              : { "field": "limit_enabled", "type": "hidden", "test_val": "yes" },
        PROP.MAX_TICKETS                : { "field": "maxtickets", "type": "int" },
        PROP.PAYMENT_WINDOW             : { "field": "payment_window", "type": "int" },
        PROP.EVENT_DATE                 : { "field": "event_date", "type": "date" },
        PROP.EVENT_NAME                 : { "field": "event_name", "type": "text" },
        PROP.MINIMUM_AGE                : { "field": "minimum_age", "type": "int" },
        PROP.TRANSFER_FEE_ENABLED       : { "field": "transfer_fee_enabled", "type": "checkbox", "test_val": "transfer_fee_enabled" },
        PROP.TRANSFER_FEE               : { "field": "transfer_fee", "type": "money" },
        PROP.DETAILS_FEE_ENABLED        : { "field": "details_fee_enabled", "type": "checkbox", "test_val": "details_fee_enabled" },
        PROP.DETAILS_FEE                : { "field": "details_fee", "type": "money" },
        PROP.CHECKIN_ACTIVE             : { "field": "checkin_enabled", "type": "hidden", "test_val": "yes" },
        PROP.CHECKIN_SHOW_ALL           : { "field": "checkin_show_all", "type": "checkbox", "test_val": "checkin_show_all" },
        PROP.CHECKIN_OVERRIDE_ONE       : { "field": "overrideone", "type": "password", "test_val": "*" },
        PROP.CHECKIN_OVERRIDE_TWO       : { "field": "overridetwo", "type": "password", "test_val": "*" },
        PROP.CHECKIN_OVERRIDE_THREE     : { "field": "overridethree", "type": "password", "test_val": "*" },
        PROP.AUTO_EMAIL_INCLUDED_TEXT   : { "field": "email_included_text", "type": "text" },
        PROP.AUTO_EMAIL_CONTACT_DETAILS : { "field": "email_contact_text", "type": "text" },
        PROP.SIGNUP_ENABLED             : { "field": "public_signup_enabled", "type": "checkbox", "test_val": "public_signup_enabled" },
        PROP.ALUMNI_RAVEN_ENABLED       : { "field": "alumnus_raven_enabled", "type": "checkbox", "test_val": "alumnus_raven_enabled" },
        PROP.ACCOUNT_LOCK_DOWN          : { "field": "account_lock_down", "type": "checkbox", "test_val": "account_lock_down" },
        PROP.ERROR_BOX_CONTACT_INFO     : { "field": "error_contact_info", "type": "text" },
        PROP.TICKET_DOWNLOAD_ENABLED    : { "field": "ticket_download_enabled", "type": "checkbox", "test_val": "ticket_download_enabled" },
        PROP.GUEST_DETAILS_REQUIRED     : { "field": "guest_details_required", "type": "checkbox", "test_val": "guest_details_required" }
    }

    @view_config(
        route_name="admin_settings",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/settings.pt"
    )
    def settings_view(self):
        # Copy in existing setting values
        settings = {}
        for key in self.settings_map:
            if key in self.request.root.properties:
                settings[key] = self.request.root.properties[key]

        # Process posted data
        if "submit" in self.request.POST:
            # Store settings and then verify
            for key in self.settings_map:
                param = self.settings_map[key]
                field = param["field"]
                prep_value = None
                # Convert to a suitable format
                try:
                    if param["type"] == "hidden":
                        prep_value = (self.request.POST[field] == param["test_val"])
                    elif param["type"] == "int":
                        prep_value = int(float(self.request.POST[field]))
                    elif param["type"] == "float":
                        prep_value = float(self.request.POST[field])
                    elif param["type"] == "money":
                        prep_value = int(float(self.request.POST[field]) * 100.0)
                    elif param["type"] == "date":
                        raw_val = self.request.POST[field]
                        if raw_val == None:
                            continue
                        parts = raw_val.split("/")
                        if len(parts) != 3:
                            continue
                        day = int(float(parts[0]))
                        month = int(float(parts[1]))
                        year = (int(float(parts[2])) if int(float(parts[2])) > 1000 else (int(float(parts[2])) + 1000))
                        prep_value = datetime(year, month, day)
                    elif param["type"] == "password":
                        raw_val = self.request.POST[field]
                        prep_value = (raw_val if not '*' in raw_val else self.request.root.properties[key])
                    elif param["type"] == "checkbox":
                        prep_value = (field in self.request.POST and self.request.POST[field] == param["test_val"])
                    elif param["type"] == "text":
                        prep_value = self.request.POST[field]
                except Exception as e:
                    print "Exception caught when storing setting", e
                # Store the value into the settings dictionary
                if prep_value != None:
                    settings[key] = prep_value
            # Perform some basic verification
            if settings[PROP.PAYMENT_WINDOW] <= 0:
                self.request.session.flash("Payment window must be greater than zero days.", "error")
            elif settings[PROP.MAX_SESSION_TIME] < 5:
                self.request.session.flash("The maximum session time must be greater than 5 minutes to ensure smooth check-out.", "error")
            elif settings[PROP.CONCURRENT_NUM] <= 0:
                self.request.session.flash("The maximum number of concurrent customers must be greater than zero.", "error")
            elif settings[PROP.MAX_TICKETS] < 1:
                self.request.session.flash("The maximum ticket number must be at least one.", "error")
            elif settings[PROP.MINIMUM_AGE] < 0:
                self.request.session.flash("The minimum age must be greater than zero.", "error")
            else:
                # Copy across to actually save
                for key in settings:
                    self.request.root.properties[key] = settings[key]
                # Save selected control groups
                groups = self.request.params.getall("selgroup")
                to_remove = []
                for group in self.request.root.properties[PROP.CONTROL_GROUPS]:
                    if group not in groups:
                        to_remove.append(group)
                for group in to_remove:
                    self.request.root.properties[PROP.CONTROL_GROUPS].remove(group)
                for group in groups:
                    if group not in self.request.root.properties[PROP.CONTROL_GROUPS]:
                        self.request.root.properties[PROP.CONTROL_GROUPS].append(group)
            # Change the enabled payment methods
            methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
            enabled_methods = []
            for key in [x for x in self.request.POST.keys() if "pm_enable_" in x.lower()]:
                method_key = key.split("pm_enable_")[1]
                enabled_methods.append(method_key.lower())
            for method in methods:
                method.enabled = (method.__name__.lower() in enabled_methods and self.request.POST[("pm_enable_" + method.__name__.lower())] == "yes")

        # Prepare the values to be rendered
        rendered_values = {}
        for key in self.settings_map:
            param = self.settings_map[key]
            if key in settings:
                rendered_values[param["field"]] = settings[key]
            else:
                rendered_values[param["field"]] = ""

        # Do not publicly show the API key or passwords
        rendered_values["stripe_api_key"] = '*'*20
        if len(rendered_values["overrideone"]) > 0:
            rendered_values["overrideone"] = '*'*20
        if len(rendered_values["overridetwo"]) > 0:
            rendered_values["overridetwo"] = '*'*20
        if len(rendered_values["overridethree"]) > 0:
            rendered_values["overridethree"] = '*'*20

        # Return data to renderer
        return {
            "settings": rendered_values,
            "control_groups": PROP.getProperty(self.request, PROP.CONTROL_GROUPS),
            "purchase_agreement": (self.request.root.properties[PROP.PURCHASE_AGREEMENT].main_body and len(self.request.root.properties[PROP.PURCHASE_AGREEMENT].main_body) > 0),
            "privacy_policy": (self.request.root.properties[PROP.PRIVACY_POLICY].main_body and len(self.request.root.properties[PROP.PRIVACY_POLICY].main_body) > 0),
            "cookie_policy": (self.request.root.properties[PROP.COOKIE_POLICY].main_body and len(self.request.root.properties[PROP.COOKIE_POLICY].main_body) > 0),
            "payment_methods": PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        }

    @view_config(
        route_name="admin_document",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/document.pt"
    )
    def document_view(self):
        # Get the document
        document = self.request.root.properties[self.request.matchdict["doc_code"]]
        if type(document) is not Document:
            self.request.session.flash("Document does not exist!", "error")
            return HTTPFound(location=self.request.route_path("admin_settings"))
        if "submit" in self.request.POST:
            document.main_body = self.request.POST["body"]
            to_remove = []
            for point in document.headline_points:
                to_remove.append(point)
            for point in to_remove:
                document.headline_points.remove(point)
            for highpoint in self.request.params.getall("highpoint"):
                document.headline_points.append(highpoint)
        return {
            "document": document,
        }

    @view_config(
        route_name="admin_notes",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/notes.pt"
    )
    def notes_view(self):
        # Get the notes
        mode = self.request.matchdict["mode"].lower()
        ident = self.request.matchdict["id"]
        if not mode in ["user", "payment", "ticket"]:
            self.request.session.flash("Invalid mode for notes!", "error")
            return HTTPFound(location=self.request.route_path("admin_summary"))
        notes = ""
        user = payment = ticket = None
        # Find the object
        if mode == "user":
            user = self.request.root.users[ident.lower()]
            notes = user.notes
        elif mode =="payment":
            payment = self.request.root.payments[ident.upper()]
            notes = payment.notes
        elif mode == "ticket":
            for payment in self.request.root.payments.values():
                for tick in payment.tickets:
                    if tick.__name__ == ident.upper():
                        ticket = tick
                        break
            notes = ticket.notes
        # Save the changes if necessary
        if "submit" in self.request.POST:
            if mode == "user":
                user.notes = self.request.POST["notes"]
                return HTTPFound(location=self.request.route_path("admin_view_user", user_id=user.__name__))
            elif mode == "payment":
                payment.notes = self.request.POST["notes"]
                return HTTPFound(location=self.request.route_path("admin_single_payment", ref_code=payment.__name__))
            elif mode == "ticket":
                ticket.notes = self.request.POST["notes"]
                return HTTPFound(location=self.request.route_path("admin_ticket_guest_info", ticket_id=ticket.__name__))
        return {
            "notes": notes,
        }

    @view_config(
        route_name="admin_test_email",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/test_email.pt"
    )
    def admin_test_email_view(self):
        if "submit" in self.request.POST:
            user_id = self.request.POST["user_id"]
            success = GenericEmail(self.request).compose_and_send("Testing Email System", "Here is the test email", user_id)
            if success == True:
                self.request.session.flash("Sent message successfully!", "info")
            else:
                self.request.session.flash("Message did not send successfully!", "error")
        return {}

    @view_config(
        route_name="admin_queue",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/queue.pt"
    )
    def admin_queue_view(self):
        # Enact the kicking of customers :)
        if "action" in self.request.GET and self.request.GET["action"] == "kick":
            client = self.request.GET["client"]
            if client in self.request.root.active:
                Queue(self.request).remove_from_active(client)
        # Run a few other timeout checks
        Queue(self.request).check_for_timeouts()
        Queue(self.request).check_active()
        return {}
    
    @view_config(
        route_name="admin_payment_settings",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/payment_settings.pt"
    )
    def admin_payment_settings_view(self):
        # Deal with the different payment methods
        methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        if "submit" in self.request.POST:
            errored = False
            # Process method settings
            for key in self.request.POST.keys():
                if "enable_" in key:
                    sect_key = key.split("enable_")[1]
                    method = [x for x in methods if x.__name__ == sect_key]
                    if len(method) > 0:
                        method = method[0]
                        method.enabled = (self.request.POST[key].lower() == "yes")
                        # Go through properties
                        for prop_key in method.settings:
                            post_key = sect_key + "+" + prop_key
                            prop = method.settings[prop_key]
                            if post_key in self.request.POST:
                                good = prop.update_value(self.request.POST[post_key])
                                if not good:
                                    errored = True
                        # Go through eligible groups
                        if method.groups == None:
                            method.groups = PersistentList()
                        del method.groups[:]
                        for group_key in self.request.root.groups.keys():
                            post_key = sect_key + "+" + group_key + "+group"
                            if post_key in self.request.POST and self.request.POST[post_key] == group_key:
                                method.groups.append(self.request.root.groups[group_key])
            if errored:
                self.request.session.flash("Some data was not saved as it didn't pass validation.", "error")
        elif "action" in self.request.GET and self.request.GET["action"] == "resetdefaults":
            setup = Initial(self.context, self.request)
            # Clear payment methods
            methods = self.request.root.properties[PROP.PAYMENT_METHODS]
            del methods[:] # Remove all payment methods
            # Run the setup
            setup.db_setup_pay_methods(self.request.root)
            self.request.session.flash("Payment methods reset to default values.", "info")
            # Mark methods as changed
            methods._p_changed = True
        return {
            "methods": methods
        }
    
    def sort_payment_method_settings(self, settings):
        keys = settings.keys()
        keys.sort()
        return_arr = []
        for key in keys:
            return_arr.append(settings[key])
        return return_arr

    def client_time_left(self, client_id):
        if not client_id in self.request.root.active:
            return "-"
        seconds = Queue(self.request).purchase_time_left(active_id=client_id)
        minutes = int(floor(seconds / 60.0))
        rem_seconds = seconds - minutes * 60
        str_time = "%i:%.2i" % (minutes, rem_seconds)
        return str_time

    def client_last_ping(self, client_id):
        if not client_id in self.request.root.active:
            return "-"
        client = self.request.root.active[client_id]
        seconds = (datetime.now() - client.last_checkin_time).seconds
        minutes = int(floor(seconds / 60.0))
        rem_seconds = seconds - minutes * 60
        str_time = "%i:%.2i" % (minutes, rem_seconds)
        return str_time
