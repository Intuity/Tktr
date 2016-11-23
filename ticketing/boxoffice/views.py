# -*- coding: utf-8 -*- 

from datetime import timedelta
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from ticketing.boxoffice.issue import Issuer, OutOfStock, UserAtLimit, UserAtTypeLimit, InvalidOrder, MultipleExclusives
from ticketing.email.templates import PurchaseConfirmationEmail
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import PROP_KEYS as PROP
from ticketing.models import Ticketing
from ticketing.queue.queue import Queue

import logging
logging = logging.getLogger("ticketing") 

class BoxOffice(BaseLayout):

    @view_config(route_name="buy_tickets", context=Ticketing, permission="basic", renderer="templates/buy.pt")
    def buy_view(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))
        # Check we can be here
        # - First check queue/active status
        if Queue(self.request).timed_out():
            return HTTPFound(self.request.route_path("purchase_timeout"))
        # - Check if group is currently allowed to purchase
        elif self.request.root.properties[PROP.CUSTOMER_CONTROL_ENABLED] and self.group.__name__ not in self.request.root.properties[PROP.CONTROL_GROUPS]:
            self.request.session.flash("Sorry but you are currently not allowed to purchase tickets, please come back later.", "info")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # - Now check user details
        elif not self.user_details_complete:
            self.request.session.flash("You must complete all of your profile details before purchasing tickets.", "error")
            return HTTPFound(location=self.request.route_path("user_profile_edit"))
        # Ok, all good
        user = self.user
        # First ensure that the queuer object has reference to user
        queuer = self.queue_item
        if queuer != None:
            queuer.user_id = user.__name__
        # Then return any previous order
        issue = Issuer(self.request.root)
        try:
            issue.returnUnpurchasedTickets(user.__name__)
        except Exception, e:
            logging.exception("%s: Had issue returning previously unpurchased tickets: %s" % (self.user.username, str(e)))
            self.request.session.flash("Had an issue returning previously unpurchased tickets, please try again.", "error")
        # Deal with submission
        if "submit" in self.request.POST:
            # Check order for limit
            total_ticks = 0
            tickets = {}
            for key in self.request.POST:
                if "TYPE-" in key:
                    num_tick = int(self.request.POST[key])
                    tick_type = [x.tick_type for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == key][0]
                    tickets[key] = {"quantity": num_tick, "name": tick_type.name,}
                    total_ticks += num_tick
            if PROP.getProperty(self.request, PROP.LIMIT_ENABLED) and total_ticks > PROP.getProperty(self.request, PROP.MAX_TICKETS):
                return {"error": "At the moment you can only purchase a maximum of %i tickets, please correct your order." % PROP.getProperty(self.request, PROP.MAX_TICKETS)}
            elif total_ticks <= 0:
                return {"error": "You have not selected any tickets for purchase, please indicate the quantities you want and click Next."}
            # All good to go now
            error = None
            for key in tickets:
                quantity = tickets[key]["quantity"]
                name = tickets[key]["name"]
                # Check order
                if quantity > 0:
                    try:
                        issue.issueTickets(user.__name__, key, quantity)
                    except OutOfStock:
                        error = "There is too little stock left of %s to complete your order." % name
                        break
                    except UserAtLimit:
                        error = "Purchasing this number of tickets will exceed the limit of %i tickets." % PROP.getProperty(self.request, PROP.MAX_TICKETS)
                        break
                    except UserAtTypeLimit, e:
                        error = "You are exceeding the max number of purchases allowed (%i) of ticket type \"%s\"." % (e.limit, e.tick_type)
                        break
                    except Exception, e:
                        logging.exception("%s: unexpected error occurred whilst issuing tickets: %s" % (self.user.username, str(e)))
                        error = "Something went wrong that we were not expecting, please try again."
                        break
            if error != None:
                try:
                    issue.returnUnpurchasedTickets(user.__name__)
                except Exception, e:
                    logging.exception("%s: Unexpected error returning unpurchased tickets, please try again: %s" % (self.user.username, str(e)))
                    self.request.session.flash("Had an issue returning unpurchased tickets, please try again.", "error")
                return {"error": error}
            else:
                return HTTPFound(location=self.request.route_path("addons"))

        return {}

    @view_config(route_name="addons", context=Ticketing, permission="basic", renderer="templates/addons.pt")
    def addons_view(self):
        # Check we can be here
        # - First check queue/active status
        if Queue(self.request).timed_out():
            return HTTPFound(self.request.route_path("purchase_timeout"))
        # - Now user details
        elif not self.user_details_complete:
            self.request.session.flash("You must complete all of your profile details before purchasing tickets.", "error")
            return HTTPFound(location=self.request.route_path("user_profile_edit"))
        # Ok, all good
        user = self.request.root.users[self.request.session["user_id"]]
        tickets = [x for x in user.tickets if x.payment == None]

        if len(tickets) == 0:
            return HTTPFound(location=self.request.route_path("buy_tickets"))

        # Stock check that we have some add-ons left
        addons = False
        for ticket in tickets:
            for addon in ticket.tick_type.addons.values():
                if addon.unlimited:
                    addons = True
                    break
                elif (addon.total_released - len(addon.allocated)) > 0:
                    addons = True
                    break
        if not addons:
            return HTTPFound(location=self.request.route_path("order_details"))

        # If they submitted the form then try issuing the add-ons
        if "submit" in self.request.POST:
            try:
                # For each ticket we have check for selected add-ons
                for ticket in tickets:
                    selected_addons = self.request.params.getall(ticket.__name__ + "_addons")
                    ticket.release_addons()
                    issue = Issuer(self.request.root)
                    for addon_key in selected_addons:
                        try:
                            issue.issueAddon(self.user.__name__, ticket, addon_key)
                        except InvalidOrder:
                            logging.error("%s: Attempted to double issue addon" % self.user.username)
                            pass # Double issue of an add-on
                return HTTPFound(location=self.request.route_path("order_details"))
            except MultipleExclusives:
                self.request.session.flash("You selected two exclusive add-ons for a single ticket, please only select one.", "error")
            except OutOfStock:
                self.request.session.flash("Unfortunately one of the add-ons you chose is no longer available in the quantity you requested, please try again.", "error")
            # Make sure to release any claimed add-ons if we have gotten here (i.e. errored)
            for ticket in tickets:
                ticket.release_addons()
        return {}

    @view_config(route_name="order_details", context=Ticketing, permission="basic", renderer="templates/details.pt")
    def order_details_view(self):
        # Check we can be here
        # - First check queue/active status
        if Queue(self.request).timed_out():
            return HTTPFound(self.request.route_path("purchase_timeout"))
        # - Now user details
        elif not self.user_details_complete:
            self.request.session.flash("You must complete all of your profile details before purchasing tickets.", "error")
            return HTTPFound(location=self.request.route_path("user_profile_edit"))
        # Ok, all good
        user = self.request.root.users[self.request.session["user_id"]]
        tickets = [x for x in user.tickets if x.payment == None]
        
        if len(tickets) == 0:
            return HTTPFound(location=self.request.route_path("buy_tickets"))

        if self.guest_details_required:
            # If a user is only buying 1 ticket and hasn't already purchased, mark as own
            if len(tickets) == 1 and len([x for x in user.tickets if x.payment != None]) == 0:
                tickets[0].guest_info = user.profile

            # Don't want to allow marking if person already has a marked ticket
            if "mark" in self.request.GET and self.user_ticket() == None:
                mark_id = self.request.GET["mark"]
                filter_ticks = [x for x in tickets if x.__name__ == mark_id]
                if len(filter_ticks) == 1:
                    for tick in tickets:
                        if tick.guest_info == tick.owner.profile:
                            tick.guest_info = None
                    to_mark = filter_ticks[0]
                    to_mark.guest_info = user.profile
        else:
            # Mark all tickets as having the owner's profile - just simplifies compatibility issues
            for tick in tickets:
                tick.guest_info = user.profile

        # Check all users have the correct data and then proceed
        user_tick = False
        missing_details = False
        if self.guest_details_required:
            for tick in tickets:
                if tick.guest_info == None:
                    missing_details = True # Need to more completely validate profile here
                    break
                elif tick.guest_info == tick.owner.profile and user_tick == True:
                    user_tick = False
                    break
                elif tick.guest_info == tick.owner.profile:
                    user_tick = True
        else:
            user_tick = True
            missing_details = False

        # Check if we can move forward a stage
        if "submit" in self.request.POST:
            # Report errors or allow us to continue
            if user_tick == False and self.user_ticket() == None:
                self.request.session.flash("You must mark a ticket as your own.", "error")
                return {}
            elif missing_details:
                self.request.session.flash("You haven't completed all of the information required for your guests.", "error")
                return {}
            else:
                return HTTPFound(location=self.request.route_path("pay_for_tickets"))

        # Check whether the back button should go to addons or buy view
        addons = False
        for ticket in tickets:
            for addon in ticket.tick_type.addons.values():
                if addon.unlimited:
                    addons = True
                    break
                elif (addon.total_released - len(addon.allocated)) > 0:
                    addons = True
                    break

        return {
            "needs_info": ((user_tick == False and self.user_ticket() == None) or missing_details),
            "addons": addons
        }
    
    @view_config(route_name="pay_for_tickets", context=Ticketing, permission="basic", renderer="templates/pay.pt")
    def pay_view(self):
        # Check we can be here
        # - First check queue/active status
        if Queue(self.request).timed_out():
            return HTTPFound(self.request.route_path("purchase_timeout"))
        # Now details
        elif not self.details_complete:
            self.request.session.flash("You must complete all of your guest's details before continuing.", "error")
            return HTTPFound(location=self.request.route_path("order_details"))
        elif "method" in self.request.GET:
            logging.info("%s: Chose %s as their payment method" % (self.user.username, self.request.GET["method"]))
            # Check this is a valid, registered payment method
            method = [x for x in PROP.getProperty(self.request, PROP.PAYMENT_METHODS) if x.enabled and x.__name__.lower() == self.request.GET["method"].lower()]
            if len(method) > 0:
                method = method[0]
                # Look for a route to make this payment by
                try:
                    route_url = self.request.route_path("pay_" + method.__name__)
                    return HTTPFound(location=route_url)
                except(KeyError):
                    self.request.session.flash("An error occurred with the payment method you selected, please try again.", "error")
                    logging.info("%s: Tried to request an unknown payment method" % self.user.username)
            else:
                self.request.session.flash("An error occurred with the payment method you selected, please try again.", "error")
                logging.info("%s: Tried to request an unknown payment method" % self.user.username)
        # Clear any previous payment reference
        self.request.session.pop("payment_id", None)
        # Ok, all good
        user = self.request.root.users[self.request.session["user_id"]]
        tickets = [x for x in user.tickets if x.payment == None]
        if len(tickets) == 0:
            return HTTPFound(location=self.request.route_path("buy_tickets"))
        return {
            "methods": [x for x in PROP.getProperty(self.request, PROP.PAYMENT_METHODS) if x.enabled and x.public]
        }
    
    @view_config(route_name="pay_confirm", context=Ticketing, permission="basic", renderer="templates/confirm.pt")
    def confirmation_view(self):
        # Check we can be here - doesn't matter about timeouts here
        if not self.details_complete or len(self.user.payments) <= 0:
            self.request.session.flash("You must complete all of your guest's details before continuing.", "error")
            return HTTPFound(location=self.request.route_path("order_details"))
        # Ok, all good
        user = self.request.root.users[self.request.session["user_id"]]
        if not "payment_id" in self.request.session:
            return HTTPFound(location=self.request.route_path("pay_for_tickets"))
        payments = [x for x in user.payments if x.ref_code == self.request.session["payment_id"]]
        if len(payments) <= 0:
            return HTTPFound(location=self.request.route_path("pay_for_tickets"))
        payment = payments[0]
        logging.info("%s: Confirm purchase of tickets - payment: %s" % (self.user.username, payment.__name__))
        # Send the confirmation message
        try:
            confirm = PurchaseConfirmationEmail(self.request)
            if not confirm.compose_and_send(payment.ref_code):
                self.request.session.flash("Could not send your order confirmation, please contact webmaster@mayball.com", "error")
                logging.error("%s: Failed to send order confirmation for payment %s" % (self.user.username, payment.__name__))
        except Exception as e:
            self.request.session.flash("Could not send your order confirmation, please contact webmaster@mayball.com", "error")
            logging.exception("%s: An error occurred while trying to send payment confirmation: %s" % (self.user.username, str(e)))
        # As we are at the end of the process - clean up
        if self.request.root.properties[PROP.QUEUE_ENABLED]:
            Queue(self.request).remove_from_active(self.request.session["active_id"])
        # - Must remove payment ID or a second purchase would use the same ID!
        self.request.session.pop("payment_id", None)
        method = self.get_payment_method(payment.current_method)
        return {
            "payment": payment,
            "method": method,
            "deadlined": (method != None and method.deadlined),
            "stripe": (payment.method == "stripe"),
            "banktransfer": (payment.method == "banktransfer"),
            "cheque": (payment.method == "cheque"),
            "due_date": (payment.opened_date + timedelta(days=self.payment_window)).strftime("%d/%m/%Y"),
        }

