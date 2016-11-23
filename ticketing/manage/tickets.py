from datetime import datetime
from dateutil.relativedelta import relativedelta
from math import ceil
from pyramid.httpexceptions import HTTPFound
from pyramid.response import Response
from pyramid.view import view_config
from persistent.mapping import PersistentMapping
import re

from ticketing.boxoffice.models import Ticket, TicketType, TicketPool, TicketAddon, Payment, PaymentStage
from ticketing.macros.baselayout import BaseLayout
from ticketing.profile.models import UserProfile
from ticketing.models import PROP_KEYS
from ticketing.email.templates import GenericEmail
from ticketing.checkin.models import CheckIn

class Tickets(BaseLayout):
    
    @view_config(
        route_name="admin_tickets",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/tickets.pt"
    )
    def ticket_type_view(self):
        return {
            "pools": self.context.ticket_pools.values(),
        }
    
    @view_config(
        route_name="admin_ticket_type_edit",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/add_ticket_type.pt"
    )
    @view_config(
        route_name="admin_ticket_type_add",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/add_ticket_type.pt"
    )
    def add_tick_type_view(self):
        ticket_type = None
        if "tick_code" in self.request.matchdict:
            types = [x.tick_type for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == self.request.matchdict["tick_code"]]
            ticket_type = types[0]

        if "submit" in self.request.POST:
            groups = self.request.params.getall("selgroup")
            if ticket_type:
                ticket_type.name = self.request.POST["name"]
                ticket_type.description = self.request.POST["description"]
                if "purchase_limit" in self.request.POST and len(self.request.POST["purchase_limit"]) > 0:
                    ticket_type.purchase_limit = int(float(self.request.POST["purchase_limit"]))
                    if ticket_type.purchase_limit < 0:
                        ticket_type.purchase_limit = 0
                else:
                    ticket_type.purchase_limit = 0
                ticket_type.cost = int(float(self.request.POST["cost"]) * 100)
                ticket_type.locked_down = ("locked_down" in self.request.POST and self.request.POST["locked_down"] == "locked_down")
                to_remove = []
                for key in ticket_type.__parent__.groups:
                    if key not in groups: to_remove.append(key)
                for key in to_remove:
                    ticket_type.__parent__.groups.remove(key)
                for key in groups:
                    if key not in ticket_type.__parent__.groups:
                        ticket_type.__parent__.groups.append(key)
            else:
                new_pool = TicketPool()
                new_pool.__parent__ = self.request.root
                new_type = TicketType(name=self.request.POST["name"], description=self.request.POST["description"], cost=int(float(self.request.POST["cost"]) * 100))
                if "purchase_limit" in self.request.POST and len(self.request.POST["purchase_limit"]) > 0:
                    new_type.purchase_limit = int(float(self.request.POST["purchase_limit"]))
                    if new_type.purchase_limit < 0:
                        new_type.purchase_limit = 0
                else:
                    new_type.purchase_limit = 0
                new_type.locked_down = ("locked_down" in self.request.POST and self.request.POST["locked_down"] == "locked_down")
                new_type.__parent__ = new_pool
                new_pool.tick_type = new_type
                for key in groups:
                    new_pool.groups.append(key)
                self.request.root.ticket_pools[new_pool.__name__] = new_pool
                self.request.root.ticket_pools._p_changed = True
            return HTTPFound(location=self.request.route_path("admin_tickets"))

        return {
            "ticket_type": ticket_type,
        }

    @view_config(
        route_name="admin_tickets_addons",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/addons.pt"
    )
    def tickets_addon_view(self):
        ticket_type = None
        if "tick_code" in self.request.matchdict:
            types = [x.tick_type for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == self.request.matchdict["tick_code"]]
            ticket_type = types[0]
        if ticket_type != None and (ticket_type.addons == None or len(ticket_type.addons) == 0):
            if ticket_type.addons == None:
                ticket_type.addons = PersistentMapping()
            return HTTPFound(location=self.request.route_path("admin_ticket_addon_create", tick_code=ticket_type.__name__))
        return {"tick_type": ticket_type}

    @view_config(
        route_name="admin_ticket_addon_create",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/create_addon.pt"
    )
    @view_config(
        route_name="admin_ticket_addon_edit",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/create_addon.pt"
    )
    def create_addon_view(self):
        ticket_type = None
        addon = None
        if "tick_code" in self.request.matchdict:
            types = [x.tick_type for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == self.request.matchdict["tick_code"]]
            ticket_type = types[0]
        if "addon_code" in self.request.matchdict:
            addon_code = self.request.matchdict["addon_code"]
            if addon_code in ticket_type.addons:
                addon = ticket_type.addons[addon_code]
        # If a form is being saved
        if "submit" in self.request.POST:
            name = self.request.POST["name"]
            description = self.request.POST["description"]
            cost = float(self.request.POST["cost"]) * 100.0
            if cost < 0:
                self.request.session.flash("The price of the add-on must be a positive number.", "error")
                return {
                    "tick_type": ticket_type,
                    "addon": addon
                }
            unlimited = ("unlimited" in self.request.POST and self.request.POST["unlimited"] == "unlimited")
            exclusive = ("exclusive" in self.request.POST and self.request.POST["exclusive"] == "exclusive")
            lockdown = ("lockdown" in self.request.POST and self.request.POST["lockdown"] == "lockdown")
            quantity = 0
            # Get the quantity of add-ons to release
            if not unlimited:
                if not "quantity" in self.request.POST:
                    self.request.session.flash("The form for creating an add-on was incomplete, please try again.", "error")
                    return {
                        "tick_type": ticket_type,
                        "addon": addon
                    }
                quant_str = re.compile(r'[^\d.]+')
                quant_str = quant_str.sub('', self.request.POST["quantity"])
                if len(quant_str) == 0:
                    self.request.session.flash("You must either enter a quantity of add-ons to release or mark this add-on as unlimited.", "error")
                    return {
                        "tick_type": ticket_type,
                        "addon": addon
                    }
                quantity = int(float(quant_str))
                if quantity < 0:
                    self.request.session.flash("You must either enter a positive number of add-ons to release.", "error")
                    return {
                        "tick_type": ticket_type,
                        "addon": addon
                    }
            # If we are not editing then we will need to create an add-on
            if addon == None:
                addon = TicketAddon()
                addon.__parent__ = ticket_type
                ticket_type.addons[addon.__name__] = addon
            # Update the add-on
            addon.name = name
            addon.description = description
            addon.cost = cost
            addon.total_released = quantity
            addon.unlimited = unlimited
            addon.exclusive = exclusive
            addon.locked_down = lockdown
            return HTTPFound(location=self.request.route_path("admin_tickets_addons", tick_code=ticket_type.__name__))
        return {
            "tick_type": ticket_type,
            "addon": addon
        }

    @view_config(
        route_name="admin_ticket_addon_retract",
        context="ticketing.models.Ticketing",
        permission="admin"
    )
    def retract_addon_view(self):
        ticket_type = None
        addon = None
        if "tick_code" in self.request.matchdict:
            types = [x.tick_type for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == self.request.matchdict["tick_code"]]
            ticket_type = types[0]
        if "addon_code" in self.request.matchdict:
            addon_code = self.request.matchdict["addon_code"]
            if addon_code in ticket_type.addons:
                addon = ticket_type.addons[addon_code]
            else:
                self.request.session.flash("The requested add-on does not exist and hence was not retracted.", "error")
                return HTTPFound(location=self.request.route_path("admin_tickets_addons", tick_code=ticket_type.__name__))
        addon.unlimited = False
        addon.total_released = len(addon.allocated)
        self.request.session.flash('The add-on "%s" has been retracted.' % addon.name, "info")
        return HTTPFound(location=self.request.route_path("admin_tickets_addons", tick_code=ticket_type.__name__))

    @view_config(
        route_name="admin_ticket_addon_delete",
        context="ticketing.models.Ticketing",
        permission="admin"
    )
    def delete_addon_view(self):
        ticket_type = None
        addon = None
        if "tick_code" in self.request.matchdict:
            types = [x.tick_type for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == self.request.matchdict["tick_code"]]
            ticket_type = types[0]
        if "addon_code" in self.request.matchdict:
            addon_code = self.request.matchdict["addon_code"]
            if addon_code in ticket_type.addons:
                addon = ticket_type.addons[addon_code]
            else:
                self.request.session.flash("The requested add-on does not exist and hence was not deleted.", "error")
                return HTTPFound(location=self.request.route_path("admin_tickets_addons", tick_code=ticket_type.__name__))
        addon.__parent__ = None
        ticket_type.addons.pop(addon.__name__, None)
        if len(ticket_type.addons) > 0:
            return HTTPFound(location=self.request.route_path("admin_tickets_addons", tick_code=ticket_type.__name__))
        else:
            return HTTPFound(location=self.request.route_path("admin_tickets"))

    @view_config(
        route_name="admin_tickets_all",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/purchased_tickets.pt"
    )
    @view_config(
        route_name="admin_tickets_type",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/purchased_tickets.pt"
    )
    def purchased_tickets_view(self):
        ticket_type = None
        if "tick_code" in self.request.matchdict:
            types = [x.tick_type for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == self.request.matchdict["tick_code"]]
            ticket_type = types[0]
        # Now find all tickets of this type
        filtertype = filtervalue = None
        tickets = []

        # Run filters
        if "filtertype" in self.request.GET and len(self.request.GET["filtertype"]) > 0:
            # Get all of the filter values
            filtertype = self.request.GET["filtertype"]
            filtervalue = self.request.GET["filtervalue"].lower()
            # Ticket Purchase Status Filters
            if filtertype == "status":
                if "filtervalue-status" in self.request.GET:
                    filtervalue = self.request.GET["filtervalue-status"]
                # Get all of the tickets
                for payment in self.request.root.payments.values():
                    if ticket_type != None:
                        for ticket in payment.tickets:
                            if ticket.tick_type == ticket_type:
                                tickets.append(ticket)
                    else:
                        tickets += payment.tickets
                window = PROP_KEYS.getProperty(self.request, PROP_KEYS.PAYMENT_WINDOW)
                # Filter down
                if filtervalue == "paid":
                    tickets = [x for x in tickets if x.payment.paid]
                elif filtervalue == "unpaid":
                    tickets = [x for x in tickets if not x.payment.paid]
                elif filtervalue == "expiring":
                    tickets = [x for x in tickets if x.payment.expiring(window) and not x.payment.expired(window) and not x.payment.paid]
                elif filtervalue == "expired":
                    tickets = [x for x in tickets if x.payment.expired(window) and not x.payment.paid]
                # "all" just returns the whole ticket array

            # Guest Filters
            elif filtertype in ["guestcrsid", "guestname", "guestemail", "guestcollege"]:
                for payment in self.request.root.payments.values():
                    if ticket_type != None:
                        for ticket in payment.tickets:
                            if ticket.tick_type == ticket_type:
                                tickets.append(ticket)
                    else:
                        tickets += payment.tickets
                # For these details just filter the guest profiles on the tickets
                if filtertype == "guestcrsid":
                    tickets = [x for x in tickets if x.guest_info != None and x.guest_info.crsid != None and filtervalue in x.guest_info.crsid.lower()]
                elif filtertype == "guestname":
                    tickets = [x for x in tickets if x.guest_info != None and x.guest_info.fullname != None and filtervalue in x.guest_info.fullname.lower()]
                elif filtertype == "guestemail":
                    tickets = [x for x in tickets if x.guest_info != None and x.guest_info.email != None and filtervalue in x.guest_info.email.lower()]
                elif filtertype == "guestcollege":
                    tickets = [x for x in tickets if x.guest_info != None and x.guest_info.college != None and filtervalue in x.guest_info.college.lower()]

            elif filtertype in ["ownercrsid", "ownername", "ownerusername", "owneremail", "ownercollege"]:
                users = self.request.root.users.values()
                # For these details, filter by user then extract tickets
                if filtertype == "ownercrsid":
                    users = [x for x in users if x.profile != None and x.profile.crsid != None and filtervalue in x.profile.crsid.lower()]
                elif filtertype == "ownername":
                    users = [x for x in users if x.profile != None and x.profile.fullname != None and filtervalue in x.profile.fullname.lower()]
                elif filtertype == "owneremail":
                    users = [x for x in users if x.profile != None and x.profile.email != None and filtervalue in x.profile.email.lower()]
                elif filtertype == "ownercollege":
                    users = [x for x in users if x.profile != None and x.profile.college != None and filtervalue in x.profile.college.lower()]
                elif filtertype == "ownerusername":
                    users = [x for x in users if filtervalue in x.username.lower()]
                # After filtering run through all of the users
                for user in users:
                    if ticket_type != None:
                        for ticket in user.tickets:
                            if ticket.tick_type == ticket_type:
                                tickets.append(ticket)
                    else:
                        tickets += user.tickets
            
            elif filtertype == "refcode":
                for payment in self.request.root.payments.values():
                    if ticket_type != None:
                        for ticket in payment.tickets:
                            if ticket.tick_type == ticket_type:
                                tickets.append(ticket)
                    else:
                        tickets += payment.tickets
                tickets = [x for x in tickets if filtervalue in x.__name__.lower() and filtervalue in x.id_code.lower()]

        # Cover the case of no filters!
        else:
            for payment in self.request.root.payments.values():
                if ticket_type != None:
                    for ticket in payment.tickets:
                        if ticket.tick_type == ticket_type:
                            tickets.append(ticket)
                else:
                    tickets += payment.tickets

        # Sort it
        tickets = sorted(tickets, key=lambda x: x.payment.opened_date, reverse=True)
        form_address = None
        if ticket_type != None:
            form_address = self.request.route_path('admin_tickets_type', tick_code=ticket_type.__name__)
        else:
            form_address = self.request.route_path('admin_tickets_all')

        # Paginate the data
        total_pages = ceil(len(tickets) / 75.0)
        current_page = 1
        start_index = end_index = 0
        if len(tickets) > 0:
            if "page" in self.request.GET:
                current_page = int(float(self.request.GET["page"]))
                if current_page <= 0:
                    current_page = 1
            start_index = (current_page - 1) * 75
            end_index = start_index + 75
            if start_index >= len(tickets):
                start_index = 0
                end_index = 75
                self.request.session.flash("You requested a page that was unavailable", "error")
                current_page = 1
            if end_index >= len(tickets):
                end_index = len(tickets) - 1

        if filtertype == None or filtervalue == None:
            filtertype = ""
            filtervalue = ""

        return {
            "ticket_type": ticket_type,
            "tickets": tickets[start_index:(end_index + 1)],
            "filtertype": filtertype,
            "filtervalue": filtervalue,
            "form_address": form_address,
            "current_page": current_page,
            "total_pages": int(total_pages)
        }

    @view_config(
        route_name="admin_ticket_guest_info",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/ticket_holder_profile.pt"
    )
    def ticket_holder_view(self):
        ticket = None
        if "ticket_id" in self.request.matchdict:
            users = self.request.root.users.values()
            for user in users:
                for tick in user.tickets:
                    if tick.id_code == self.request.matchdict["ticket_id"]:
                        ticket = tick
                        break
                if ticket != None:
                    break
        else:
            return HTTPFound(location=self.request.route_path("admin_tickets"))
        # Check we actually got something
        if ticket == None:
            return HTTPFound(location=self.request.route_path("admin_tickets"))
        if "action" in self.request.GET:
            if self.request.GET["action"].lower() == "markowner":
                existing_ticket = self.user_ticket(user=ticket.owner)
                if existing_ticket == ticket:
                    self.request.session.flash("This ticket is already marked as being the owner's ticket!", "error")
                else:
                    # Swap the ticket guest details over
                    if existing_ticket != None:
                        existing_ticket.guest_info = ticket.guest_info
                    ticket.guest_info = ticket.owner.profile
                    # Confirm this
                    self.request.session.flash("Ticket marked as the owner's ticket.", "info")
            elif self.request.GET["action"].lower() == "enablealter":
                ticket.change_enabled = True
            elif self.request.GET["action"].lower() == "disablealter":
                ticket.change_enabled = False
        return {
            "ticket": ticket,
        }

    @view_config(
        route_name="admin_ticket_guest_info_edit",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/ticket_guest_profile_edit.pt"
    )
    def ticket_guest_profile_edit_view(self):
        ticket = None
        if "ticket_id" in self.request.matchdict:
            users = self.request.root.users.values()
            for user in users:
                for tick in user.tickets:
                    if tick.id_code == self.request.matchdict["ticket_id"]:
                        ticket = tick
                        break
                if ticket != None:
                    break
        else:
            return HTTPFound(location=self.request.route_path("admin_tickets"))
        # Check we actually got something
        if ticket == None:
            return HTTPFound(location=self.request.route_path("admin_tickets"))
        # Check owner is not the guest
        if ticket.guest_info == ticket.owner.profile:
            return HTTPFound(location=self.request.route_path("admin_user_profile_edit", user_id=ticket.owner.__name__))
        if "submit" in self.request.POST:
            ticket.guest_info.title = self.request.POST["title"]
            if ticket.guest_info.title == "Other":
                ticket.guest_info.title = self.request.POST["othertitle"]
            ticket.guest_info.forename = self.request.POST["forename"]
            ticket.guest_info.surname = self.request.POST["surname"]
            if "email" in self.request.POST:
                ticket.guest_info.email = self.request.POST["email"]
            day = int(float(self.request.POST["dob_day"]))
            month = int(float(self.request.POST["dob_month"]))
            year = int(float(self.request.POST["dob_year"]))
            problem = False
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
                ticket.guest_info.dob = dob
                ticket.guest_info.raven_user = ("atcambridge" in self.request.POST and self.request.POST["atcambridge"] == "yes")
                if ticket.guest_info.raven_user:
                    ticket.guest_info.crsid = self.request.POST["crsid"]
                    ticket.guest_info.email = ticket.guest_info.crsid + "@cam.ac.uk"
                    ticket.guest_info.college = self.request.POST["college"]
                    ticket.guest_info.grad_status = self.request.POST["grad_status"]
                return HTTPFound(location=self.request.route_path("admin_ticket_guest_info", ticket_id=ticket.__name__))
        if ticket.guest_info == None:
            ticket.guest_info = UserProfile()
            ticket.guest_info.__parent__ = ticket
        info = ticket.guest_info
        dob = datetime.now()
        if info.dob != None:
            dob = info.dob
        return {
            "ticket_id": ticket.__name__,
            "title": info.title,
            "othertitle": (info.title not in ["Mr", "Mrs", "Miss", "Ms", "Dr", "Prof", "Rev"] and len(info.title) > 0),
            "forename": info.forename,
            "surname": info.surname,
            "email": info.email,
            "dob_year": dob.year,
            "dob_month": dob.month,
            "dob_day": dob.day,
            "atcambridge": info.raven_user,
            "crsid": info.crsid,
            "college": info.college,
            "grad_status": info.grad_status
        }

    @view_config(
        route_name="admin_ticket_checkin_status",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/ticket_checkin_status.pt"
    )
    def ticket_checkin_edit_view(self):
        ticket = None
        if "ticket_id" in self.request.matchdict:
            users = self.request.root.users.values()
            for user in users:
                for tick in user.tickets:
                    if tick.id_code == self.request.matchdict["ticket_id"]:
                        ticket = tick
                        break
                if ticket != None:
                    break
        else:
            return HTTPFound(location=self.request.route_path("admin_tickets"))
        # Check we actually got something
        if ticket == None:
            return HTTPFound(location=self.request.route_path("admin_tickets"))
        # Act upon an update
        if "submit" in self.request.POST:
            if self.request.POST["checkedin"] == "true":
                ticket.checked_in = True
                ticket.checkin_data = CheckIn()
                ticket.checkin_data.__parent__ = tick
                ticket.checkin_data.date = datetime.now()
                ticket.checkin_data.enacted_by = self.user
            else:
                ticket.checked_in = False
                ticket.checkin_data = None
            return HTTPFound(location=self.request.route_path('admin_ticket_guest_info', ticket_id=ticket.__name__))
        return {
            "ticket": ticket,
        }

    @view_config(
        route_name="admin_tickets_allocate",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/allocate_tickets.pt"
    )
    def allocate_tickets_view(self):
        if "submit" in self.request.POST:
            username = self.request.POST["username"].lower()
            if not username in self.request.root.users:
                self.request.session.flash("The user you specified does not exist, ticket allocation failed.", "error")
                return {}
            user = self.request.root.users[username]
            num_tickets = int(float(self.request.POST["numtickets"]))
            if num_tickets <= 0:
                self.request.session.flash("You must specify a number of tickets to issue, allocation failed.", "error")
            # Build the list of requested tickets and addons
            tick_types = {}
            for i in range(0, num_tickets):
                type_code = self.request.POST["ticket-%i-type" % i]
                addon_code = self.request.POST["ticket-%i-addon" % i]
                if type_code in tick_types:
                    tick_types[type_code]["count"] += 1
                    if addon_code in tick_types[type_code]["addons"]:
                        tick_types[type_code]["addons"][addon_code] += 1
                    else:
                        tick_types[type_code]["addons"][addon_code] = 1
                else:
                    tick_types[type_code] = {"count": 1, "addons": {addon_code: 1}}
            # Check stock of tickets and addons
            for type_key in tick_types:
                number = tick_types[type_key]["count"]
                addons = tick_types[type_key]["addons"]
                if not type_key in self.request.root.ticket_pools:
                    self.request.session.flash("Invalid ticket type was specified.", "error")
                    return {}
                pool = self.request.root.ticket_pools[type_key]
                if len(pool.tickets) < number:
                    self.request.session.flash("There is not enough stock of '%s' to allocate the requested tickets." % pool.tick_type.name, "error")
                    return {}
                #if not user.__parent__.__name__ in pool.groups:
                #    self.request.session.flash("The user is not permitted to have tickets of the type '%s'." % pool.tick_type.name, "error")
                #    return {}
                # Now check addons
                for addon_key in addons:
                    if addon_key == "none":
                        continue
                    if not addon_key in pool.tick_type.addons:
                        self.request.session.flash("Invalid addon type was specified.", "error")
                        return {}
                    addon = pool.tick_type.addons[addon_key]    
                    num_addons = addons[addon_key]
                    if addon.remaining < num_addons:
                        self.request.session.flash("There is not enough stock of the addon '%s' to allocate the requested tickets." % addon.name, "error")
                        return {}
            # Issue the tickets and attach all addons requested
            has_ticket = (user.tickets != None and len(user.tickets) > 0) # Whether we need to set a ticket to be theirs
            all_tickets = []
            for type_key in tick_types:
                number = tick_types[type_key]["count"]
                addons = tick_types[type_key]["addons"]
                pool = self.request.root.ticket_pools[type_key]
                for i in range(0, number):
                    ticket = pool.tickets[0]
                    user.tickets.append(ticket)
                    pool.tickets.remove(ticket)
                    ticket.__parent__ = user
                    ticket.owner = user
                    ticket.issue_date = datetime.now()
                    ticket.change_enabled = True # Allow user to update guest details once
                    if not has_ticket:
                        ticket.guest_info = user.profile
                        has_ticket = True
                    else:
                        blank_profile = UserProfile()
                        blank_profile.__parent__ = ticket
                        ticket.guest_info = blank_profile
                    all_tickets.append(ticket)
                    # Attach an addon if available
                    for addon_key in addons:
                        if addon_key == "none" or addons[addon_key] <= 0:
                            continue
                        addon = pool.tick_type.addons[addon_key]
                        ticket.addons[addon.__name__] = addon
                        addon.allocated.append(ticket)
                        addons[addon_key] -= 1
                        break
            # Open a payment and attach all of the tickets into it
            gift = ("gift" in self.request.POST and self.request.POST["gift"] == "gift")
            payment = Payment()
            payment.owner = user
            payment.__parent__ = user
            payment.opened_date = datetime.now()
            for ticket in all_tickets:
                ticket.payment = payment
                payment.tickets.append(ticket)
            if gift:
                new_stage = PaymentStage()
                new_stage.__parent__ = payment
                new_stage.method = "gifted"
                new_stage.amount_paid = int(payment.amount_remaining)
                new_stage.processing_charge = 0
                new_stage.received = new_stage.cashed = True
                new_stage.completed = True
                new_stage.stage_owner = user.__name__
                payment.history.append(new_stage)
                payment.completed_date = datetime.now()
            else:
                new_stage = PaymentStage()
                new_stage.__parent__ = payment
                new_stage.method = "cheque"
                new_stage.method_change = True
                new_stage.stage_owner = user.__name__
                payment.history.append(new_stage)
            # Attach the payment to the user
            user.payments.append(payment)
            user.total_tickets += len(payment.tickets)
            self.request.root.payments[payment.__name__] = payment
            # Send a information email
            if user.profile != None:
                emailer = GenericEmail(self.request)
                if gift:
                    emailer.compose_and_send(
                        "Tickets Allocated",
                        """This is to notify you that %i ticket(s) have been allocated to your account, they have been transferred as a gift and
                        hence no further action is required. If you want to get in touch, your ticket allocation reference is %s.""" 
                        % (len(payment.tickets), payment.ref_code),
                        payment.owner.__name__
                    )
                else:
                    emailer.compose_and_send(
                        "Tickets Allocated",
                        """This is to notify you that %i ticket(s) have been allocated to your account. You are required to complete payment for
                        your tickets, currently they are set as a default of cheque payment, however you may change this by logging into your ticket
                        account. Your purchase reference is %s and your owed total is %s.""" 
                        % (len(payment.tickets), payment.ref_code, self.format_price(payment.total)),
                        payment.owner.__name__
                    )
            # Report all good
            self.request.session.flash("Ticket allocation successful!", "info")
            return HTTPFound(location=self.request.route_path("admin_tickets"))
        return {}

    @view_config(
        route_name="admin_tickets_release",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/release_tickets.pt"
    )
    def release_ticket_type_view(self):

        ticket_type = None
        if "tick_code" in self.request.matchdict:
            types = [x.tick_type for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == self.request.matchdict["tick_code"]]
            ticket_type = types[0]
        else:
            return HTTPFound(location=self.request.route_path("admin_tickets"))

        if "number" in self.request.POST:
            to_release = int(self.request.POST["number"])
            pool = ticket_type.__parent__
            for i in range(to_release):
                new_tick = Ticket()
                new_tick.__parent__ = pool
                new_tick.tick_type = ticket_type
                pool.tickets.append(new_tick)
            pool.tickets._p_changed = True
            ticket_type.total_released += to_release
            return HTTPFound(location=self.request.route_path("admin_tickets"))

        return {
            "ticket_type": ticket_type,
        }

    @view_config(
        route_name="admin_tickets_retract",
        context="ticketing.models.Ticketing",
        permission="admin"
    )
    def retract_ticket_type_view(self):
        types = [x.tick_type for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == self.request.matchdict["tick_code"]]
        ticket_type = types[0]
        to_retract = []
        # Avoid iterating and changing
        for tick in ticket_type.__parent__.tickets:
            to_retract.append(tick)
        for tick in to_retract:
            ticket_type.__parent__.tickets.remove(tick)
        ticket_type.total_released -= len(to_retract)
        ticket_type.__parent__.tickets._p_changed = True
        return HTTPFound(location=self.request.route_path("admin_tickets"))

    @view_config(
        route_name="admin_tickets_delete",
        context="ticketing.models.Ticketing",
        permission="admin"
    )
    def delete_ticket_type_view(self):
        pool = [x for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == self.request.matchdict["tick_code"]][0]
        self.request.root.ticket_pools.pop(pool.__name__, None)
        return HTTPFound(location=self.request.route_path("admin_tickets"))

    @view_config(
        route_name="admin_tickets_report",
        context="ticketing.models.Ticketing",
        renderer="templates/ticket_report.pt",
        permission="committee"
    )
    def ticket_report_view(self):
        
        if "submit" in self.request.POST:
            # The export fields we go through
            field_names = {
                "payref":"Payment Reference", "tickref":"Ticket Reference", 
                "salutation":"Salutation", "fullname":"Guest Fullname", "crsid":"Guest CRSid", 
                "email":"Guest Email", "phone_num":"Guest Phone Number", "dob":"Guest Date of Birth", 
                "college":"Guest College", "grad":"Guest Graduate Status", 
                "owner_fullname": "Ticket Owner Fullname", "owner_crsid": "Ticket Owner CRSid",
                "owner_forename": "Ticket Owner Forename", "owner_surname": "Ticket Owner Surname",
                "type":"Ticket Type", "addons":"Addons", "total_cost":"Total Cost", 
                "purchase_date":"Purchase Date", "pay_complete":"Paid"
            }
            field_order = [
                "payref", "tickref", "salutation", "fullname", "crsid", "email",
                "phone_num", "dob", "college", "grad", "owner_fullname", "owner_crsid", 
                "owner_forename", "owner_surname",
                "type", "addons", "total_cost", "purchase_date", "pay_complete"
            ]
            # Form controls
            tick_type = self.request.POST["tickettype"]
            upgrade_type = "any"
            if "ticketupgrade" in self.request.POST:
                upgrade_type = self.request.POST["ticketupgrade"]
            payment_status = self.request.POST["paystatus"]
            export_fields = []
            chosen_friendly = []
            for field in field_names:
                html_field = "opt_" + field
                if(html_field in self.request.POST and self.request.POST[html_field] == "export"):
                    export_fields.append(field)
                    chosen_friendly.append(field_names[field])
            ordered_fields = []
            ordered_friendly = []
            for key in field_order:
                if key in export_fields:
                    ordered_fields.append(key)
                    ordered_friendly.append(chosen_friendly[export_fields.index(key)])
            export_fields = ordered_fields
            chosen_friendly = ordered_friendly
            # Run the export
            file = ""
            # + Write the filters header
            file += "Ticket Filter," + tick_type + ",Addon Filter," + upgrade_type + ",Payment Status," + payment_status + "\n\n"
            # + Write the fields row
            file += ",".join(chosen_friendly) + "\n"
            # + Filter down the payments
            payments = sorted(self.request.root.payments.values(), key=lambda x: x.opened_date)
            window = PROP_KEYS.getProperty(self.request, PROP_KEYS.PAYMENT_WINDOW)
            if payment_status == "paid":
                payments = [x for x in payments if x.paid]
            elif payment_status == "unpaid":
                payments = [x for x in payments if not x.paid]
            elif payment_status == "expiring":
                payments = [x for x in payments if x.expiring(window) and not x.expired(window) and not x.paid]
            elif payment_status == "expired":
                payments = [x for x in payments if x.expired(window) and not x.paid]
            # + Build the list of all tickets out of the payments
            filtered_tickets = []
            if tick_type == "any":
                for payment in payments:
                    for ticket in payment.tickets:
                        filtered_tickets.append(ticket)
            elif tick_type != "any" and upgrade_type == "any":
                for payment in payments:
                    of_type = [x for x in payment.tickets if x.tick_type.__parent__.__name__ == tick_type]
                    for ticket in of_type:
                        filtered_tickets.append(ticket)
            elif tick_type != "any" and upgrade_type != "any":
                for payment in payments:
                    of_type = [x for x in payment.tickets if x.tick_type.__parent__.__name__ == tick_type]
                    for ticket in of_type:
                        for addon in ticket.addons.values():
                            if addon.__name__ == upgrade_type:
                                filtered_tickets.append(ticket)
                                break
            # + For each of the filtered tickets print out the relevant data
            for ticket in filtered_tickets:
                data = []
                if "payref" in export_fields: 
                    if ticket.payment and ticket.payment.ref_code:
                        data.append(ticket.payment.ref_code)
                    else:
                        data.append("-")
                if "tickref" in export_fields: data.append(ticket.__name__)
                if "salutation" in export_fields: 
                    if ticket.guest_info and ticket.guest_info.title:
                        data.append(ticket.guest_info.title)
                    else:
                        data.append("-")
                if "fullname" in export_fields: 
                    if ticket.guest_info and ticket.guest_info.fullname:
                        data.append(ticket.guest_info.fullname)
                    else:
                        data.append("-")
                if "crsid" in export_fields: 
                    if ticket.guest_info and ticket.guest_info.crsid:
                        data.append(ticket.guest_info.crsid)
                    else:
                        data.append("-")
                if "email" in export_fields:  
                    if ticket.guest_info and ticket.guest_info.email:
                        data.append(ticket.guest_info.email)
                    else:
                        data.append("-")
                if "phone_num" in export_fields:  
                    if ticket.guest_info and ticket.guest_info.phone_number:
                        data.append("P "+ticket.guest_info.phone_number) # Append the P to force excel to treat as a string
                    else:
                        data.append("-")
                if "dob" in export_fields:  
                    if ticket.guest_info and ticket.guest_info.dob:
                        data.append(ticket.guest_info.dob.strftime("%d/%m/%Y"))
                    else:
                        data.append("-")
                if "college" in export_fields:  
                    if ticket.guest_info and ticket.guest_info.college:
                        data.append(ticket.guest_info.college)
                    else:
                        data.append("-")
                if "grad" in export_fields:  
                    if ticket.guest_info and ticket.guest_info.grad_status:
                        data.append(ticket.guest_info.grad_status)
                    else:
                        data.append("-")
                if "owner_fullname" in export_fields:
                    if ticket.owner.profile and ticket.owner.profile.fullname:
                        data.append(ticket.owner.profile.fullname)
                    else:
                        data.append("-")
                if "owner_forename" in export_fields:
                    if ticket.owner.profile and ticket.owner.profile.forename:
                        data.append(ticket.owner.profile.forename)
                    else:
                        data.append("-")
                if "owner_surname" in export_fields:
                    if ticket.owner.profile and ticket.owner.profile.surname:
                        data.append(ticket.owner.profile.surname)
                    else:
                        data.append("-")
                if "owner_crsid" in export_fields:
                    if ticket.owner.profile and ticket.owner.profile.crsid:
                        data.append(ticket.owner.profile.crsid)
                    else:
                        data.append("-")
                if "type" in export_fields: data.append(ticket.tick_type.name)
                if "addons" in export_fields: data.append(" + ".join([x.name for x in ticket.addons.values()]))
                if "total_cost" in export_fields: data.append(str(ticket.total_cost / 100.0))
                if "purchase_date" in export_fields: data.append(ticket.payment.opened_date.strftime("%d/%m/%Y"))
                if "pay_complete" in export_fields:
                    if ticket.payment.paid: data.append("Yes")
                    else: data.append("No")
                file += ",".join(data) + "\n"
            filename = "tickets-report-%s.csv" % datetime.now().isoformat()
            return Response(
                body=file,
                status=200,
                content_type="text/csv",
                content_disposition="attachment; filename=\"%s\"" % filename,
            )
        return {}
