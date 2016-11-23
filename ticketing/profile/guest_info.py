from datetime import datetime
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
import stripe

from ticketing.boxoffice.models import PaymentStage
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import Ticketing, PROP_KEYS
from ticketing.profile.models import UserProfile
from ticketing.profile.process import ProcessAndValidate

import logging
logging = logging.getLogger("ticketing") 

class GuestInfo(BaseLayout):
            
    @view_config(
        route_name="guest_info", 
        context=Ticketing, 
        permission="basic", 
        renderer="templates/edit_guest_details.pt"
    )
    @view_config(
        route_name="ticket_edit_guest",
        context=Ticketing,
        permission="basic",
        renderer="templates/edit_guest_details.pt"
    )
    def guest_info_view(self):
        # Get the ticket details
        user = self.user
        tick_id = None
        post_purchase = (self.request.matched_route.name == "ticket_edit_guest")
        # Find the ticket ID
        if "tick_id" in self.request.matchdict:
            tick_id = self.request.matchdict["tick_id"]
        elif "tick" in self.request.GET:
            tick_id = self.request.GET["tick"]
        elif "tickid" in self.request.POST:
            tick_id = self.request.POST["tick_id"]
        else:
            if post_purchase:
                self.request.session.flash("An error occurred whilst trying to retrieve the ticket details.", "error")
                return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
            else:
                return HTTPFound(location=self.request.route_path("order_details"))
        # Check guest details requirement is actually enabled
        if not self.guest_details_required:
            if post_purchase:
                return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
            else:
                return HTTPFound(location=self.request.route_path("order_details"))
        # Try getting the ticket
        try:
            ticket = [x for x in user.tickets if x.__name__ == tick_id][0]
        except Exception:
            if post_purchase:
                self.request.session.flash("An error occurred whilst trying to retrieve the ticket details.", "error")
                return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
            else:
                return HTTPFound(location=self.request.route_path("order_details"))
        # Check if this ticket is locked down
        locked_down = ticket.tick_type.locked_down
        if not locked_down: # Check all addons as well
            for addon in ticket.addons.values():
                if addon.locked_down:
                    locked_down = True
                    break
        if locked_down:
            self.request.session.flash("Editing of guest details for this ticket has been disabled.", "info")
            return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
        # Check if this ticket is allowed to be edited
        if post_purchase and self.details_fee_enabled and not ticket.change_enabled:
            return HTTPFound(location=self.request.route_path("ticket_edit_guest_pay", tick_id=tick_id))
        elif post_purchase and not ticket.payment.paid:
            self.request.session.flash("You must complete payment for this ticket before editing guest details.", "info")
            return HTTPFound(location=self.request.route_path("user_profile", tick_id=tick_id))
        # If this is the owners ticket then don't allow them to change the details
        if ticket.guest_info == ticket.owner.profile:
            if post_purchase:
                return HTTPFound(location=self.request.route_path("user_profile_edit"))
            else:
                return HTTPFound(location=self.request.route_path("order_details"))
        # Pre-populate form with data
        if ticket.guest_info != None:
            info = ticket.guest_info
            dob = datetime.now()
            if info.dob != None:
                dob = info.dob
            atcam = "yes"
            if info.crsid == None or len(info.crsid.replace(" ","")) < 3:
                atcam = "no"
            return {
                "tick_id": tick_id,
                "title": info.title,
                "othertitle": (info.title not in ["Mr", "Mrs", "Miss", "Ms", "Dr", "Prof", "Rev"] and len(info.title) > 0),
                "forename": info.forename,
                "surname": info.surname,
                "email": info.email,
                "dob_year": dob.year,
                "dob_month": dob.month,
                "dob_day": dob.day,
                "atcambridge": atcam,
                "crsid": info.crsid,
                "college": info.college,
                "grad_status": info.grad_status,
                "post_purchase": post_purchase
            }
        else:
            return {
                "tick_id": tick_id,
                "title": "",
                "othertitle": False,
                "forename": "",
                "surname": "",
                "email": "",
                "dob_year": datetime.now().year,
                "dob_month": datetime.now().month,
                "dob_day": datetime.now().day,
                "atcambridge": "no",
                "crsid": "",
                "college": "",
                "grad_status": "",
                "post_purchase": post_purchase
            }

    @view_config(
        route_name="ticket_edit_guest_pay", 
        context=Ticketing, 
        permission="basic", 
        renderer="templates/edit_guest_details_payment.pt"
    )
    # Note this route is only accessible post purchase
    def guest_info_edit_pay_view(self):
        # Get the ticket details
        user = self.user
        tick_id = (self.request.matchdict["tick_id"] if "tick_id" in self.request.matchdict else None)
        if tick_id == None:
            self.request.session.flash("An error occurred whilst trying to retrieve the ticket details.", "error")
            return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
        # Check guest details requirement is actually enabled
        if not self.guest_details_required:
            return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
        # Try getting the ticket
        try:
            ticket = [x for x in user.tickets if x.__name__ == tick_id][0]
        except Exception:
            self.request.session.flash("An error occurred whilst trying to retrieve the ticket details.", "error")
            return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
        # Check if this ticket is locked down
        locked_down = ticket.tick_type.locked_down
        if not locked_down: # Check all addons as well
            for addon in ticket.addons.values():
                if addon.locked_down:
                    locked_down = True
                    break
        if locked_down:
            self.request.session.flash("Editing of guest details for this ticket has been disabled.", "info")
            return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
        # Check that we haven't already paid for editing of this ticket and that we have to in the first place!
        if (self.details_fee_enabled and ticket.change_enabled) or not self.details_fee_enabled:
            return HTTPFound(location=self.request.route_path("ticket_edit_guest", tick_id=tick_id))
        # Check if the user first needs to complete payment
        if not ticket.payment.paid:
            self.request.session.flash("You must complete payment for this ticket before editing guest details.", "info")
            return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
        # If this is the owners ticket then don't allow them to change the details
        if ticket.guest_info == ticket.owner.profile:
            return HTTPFound(location=self.request.route_path("user_profile_edit"))
        # If we receive a payment then deal with it
        if "stripeToken" in self.request.POST:
            # Run Stripe payment to authorise
            organisation_name = self.get_payment_method('stripe').settings[PROP_KEYS.ORGANISATION_NAME].value
            details_fee = PROP_KEYS.getProperty(self.request, PROP_KEYS.DETAILS_FEE)
            token = self.request.POST["stripeToken"]
            stripe.api_key = self.get_payment_method('stripe').settings[PROP_KEYS.STRIPE_API_KEY].value
            charge = None
            error = None
            try:
                charge = stripe.Charge.create(
                    amount      = details_fee,
                    currency    = "gbp",
                    source      = token,
                    description = organisation_name
                )
                if "paid" in charge and charge["paid"] == True:
                    # Update the ticket that a guest alteration is allowed and then forward to the editing form
                    ticket.change_enabled = True
                    # Append a payment stage covering the detail change charge
                    charge_stage = PaymentStage()
                    charge_stage.__parent__ = ticket.payment
                    charge_stage.method_properties["last_four"] = charge["source"]["last4"]
                    charge_stage.method_properties["ref_code"] = charge["id"]
                    charge_stage.amount_paid = details_fee
                    charge_stage.processing_charge = details_fee
                    charge_stage.completed = charge_stage.received = charge_stage.cashed = True
                    charge_stage.stage_owner = self.user.__name__
                    charge_stage.date = datetime.now()
                    charge_stage.method = "stripe"
                    charge_stage.transfer = True
                    ticket.payment.history.append(charge_stage)
                    # Forward to the page to actually edit details
                    return HTTPFound(location=self.request.route_path("ticket_edit_guest", tick_id=tick_id))
                else:
                    error = "The payment failed, please check your details and try again!"
                    if "failure_message" in charge and charge["failure_message"] != None:
                        error = charge["failure_message"]
            except stripe.error.CardError, e:
                logging.error(self.user.username + ": Stripe invalid card error occurred: %s" % e)
                error = e
            except stripe.error.InvalidRequestError, e:
                logging.error(self.user.username + ": Stripe invalid card request occurred: %s" % e)
                error = e
            except stripe.error.RateLimitError, e:
                logging.error(self.user.username + ": Stripe rate limit error: %s" % e)
                error = "Too many people are trying to pay right now, please try again in a moment"
            except stripe.error.AuthenticationError, e:
                logging.error(self.user.username + ": Stripe authentication error: %s" % e)
                error = "An authentication error occurred trying to connect to Stripe, please contact the committee"
            except stripe.error.APIConnectionError, e:
                logging.error(self.user.username + ": Stripe API connection error: %s" % e)
                error = "Failed to connect to Stripe, please contact the committee"
            except stripe.error.StripeError, e:
                logging.error(self.user.username + ": Generic stripe error: %s" % e)
                error = "An error occurred with Stripe: %s" % e
            except Exception, e:
                logging.error(self.user.username + ": Exception thrown in Stripe guest detail payment: %s" % e)
                error = e
            # If we end up here with a paid charge, we need to refund it
            if charge != None and "paid" in charge and charge["paid"] == True:
                try:
                    refund = stripe.Refund.create(
                        charge=charge["id"],
                        reason="duplicate"
                    )
                    if refund != None and "id" in refund:
                        logging.error("%s: Refunded charge %s with refund id %s" % (self.user.username, charge["id"], refund["id"]))
                        error = "Your card was charged and then refunded, an error was thrown: %s" % error
                    else:
                        logging.error("%s: Refund of charge %s may have failed" % (self.user.username, charge["id"]))
                        error = "You card was charged, an error occurred and we may or may not have refunded you, please get in touch with the committee."
                except Exception, e:
                    logging.exception("%s: Exception was thrown during refund %s" % (self.user.username, e))
                    error = "Your card was charged and then an error occurred when we tried to refund you: %s" % e
            return {
                "ticket":   ticket,
                "error":    error
            }
        return {
            "ticket":       ticket
        }

    @view_config(
        route_name="guest_info", 
        context=Ticketing, 
        permission="basic", 
        renderer="templates/edit_guest_details.pt",
        request_method="POST"
    )
    @view_config(
        route_name="ticket_edit_guest",
        context=Ticketing,
        permission="basic",
        renderer="templates/edit_guest_details.pt",
        request_method="POST"
    )
    def guest_info_view_do(self):
        user = self.user
        tick_id = None
        post_purchase = (self.request.matched_route.name == "ticket_edit_guest")
        # Find the ticket ID
        if "tick_id" in self.request.matchdict:
            tick_id = self.request.matchdict["tick_id"]
        elif "tick" in self.request.GET:
            tick_id = self.request.GET["tick"]
        elif "tickid" in self.request.POST:
            tick_id = self.request.POST["tick_id"]
        else:
            if post_purchase:
                self.request.session.flash("An error occurred whilst trying to retrieve the ticket details.", "error")
                return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
            else:
                return HTTPFound(location=self.request.route_path("order_details"))
        # Try getting the ticket
        try:
            ticket = [x for x in user.tickets if x.__name__ == tick_id][0]
        except Exception:
            if post_purchase:
                self.request.session.flash("An error occurred whilst trying to retrieve the ticket details.", "error")
                return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
            else:
                return HTTPFound(location=self.request.route_path("order_details"))
        # Check if this ticket is locked down
        locked_down = ticket.tick_type.locked_down
        if not locked_down: # Check all addons as well
            for addon in ticket.addons.values():
                if addon.locked_down:
                    locked_down = True
                    break
        if locked_down:
            self.request.session.flash("Editing of guest details for this ticket has been disabled.", "info")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Check if this ticket is allowed to be edited
        if post_purchase and self.details_fee_enabled and not ticket.change_enabled:
            self.request.session.flash("Editing of guest details for this ticket has not been paid for.", "info")
            return HTTPFound(location=self.request.route_path("ticket_edit_guest_pay", tick_id=tick_id))
        elif post_purchase and not ticket.payment.paid:
            self.request.session.flash("You must complete payment for this ticket before editing guest details.", "info")
            return HTTPFound(location=self.request.route_path("user_profile", tick_id=tick_id))
        # If this is the owners ticket then don't allow them to change the details
        if ticket.guest_info == ticket.owner.profile:
            if post_purchase:
                return HTTPFound(location=self.request.route_path("user_profile_edit"))
            else:
                return HTTPFound(location=self.request.route_path("order_details"))
        # Ok - process the form and validate all details
        processor = ProcessAndValidate(
                        self.request.POST, 
                        self.request.registry._settings["base_dir"],
                        PROP_KEYS.getProperty(self.request, PROP_KEYS.MINIMUM_AGE),
                        PROP_KEYS.getProperty(self.request, PROP_KEYS.EVENT_DATE),
                        photo_required=PROP_KEYS.getProperty(self.request, PROP_KEYS.PHOTO_REQUIRED),
                        phone_number_required=False)
        try:
            data = processor.process()
            # If we get this far all data is valid and we can continue
            if ticket.guest_info == None:
                ticket.guest_info = UserProfile()
                ticket.guest_info.__parent__ = ticket
                ticket.guest_info.ticket = ticket
                ticket._p_changed = True
            # - Fill in details
            info = ticket.guest_info
            info.title = data["title"]
            info.forename = data["forename"]
            info.surname = data["surname"]
            info.email = data["email"]
            info.raven_user = data["atcambridge"]
            info.photo_file = data["photofile"]
            info.dob = data["dob"]
            if info.raven_user:
                info.crsid = data["crsid"]
                info.email = info.crsid + "@cam.ac.uk"
                info.college = data["college"]
                info.grad_status = data["grad_status"]
            info._p_changed = True
            # If we are post purchase, and charging for detail changes make sure we lock again
            if post_purchase:
                ticket.change_enabled = False
        except ValueError, e:
            message = str(e)
            self.request.session.flash(message, "error")
            # Get title
            title = ""
            if "title" in self.request.POST:
                title = self.request.POST["title"]
                if title == "Other":
                    title = self.request.POST["othertitle"]
            email = crsid = college = grad_status = None
            if (self.request.POST["atcambridge"] == "yes"):
                email = self.request.POST["crsid"].replace(" ","") + "@cam.ac.uk"
                crsid = self.request.POST["crsid"]
                college = self.request.POST["college"]
                grad_status = self.request.POST["grad_status"]
            else:
                email = self.request.POST["email"]
            return {
                "tick_id": tick_id,
                "title": title,
                "othertitle": (title not in ["Mr", "Mrs", "Miss", "Ms", "Dr", "Prof", "Rev"] and len(title) > 0),
                "forename": self.request.POST["forename"],
                "surname": self.request.POST["surname"],
                "email": email,
                "dob_year": self.request.POST["dob_year"],
                "dob_month": self.request.POST["dob_month"],
                "dob_day": self.request.POST["dob_day"],
                "atcambridge": self.request.POST["atcambridge"],
                "crsid": crsid,
                "college": college,
                "grad_status": grad_status,
                "post_purchase": post_purchase
            }
        # Return back if everything is ok
        if post_purchase:
            self.request.session.flash("Guest details updated successfully!", "info")
            return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
        else:
            return HTTPFound(location=self.request.route_path("order_details"))

    @view_config(
        route_name="ticket_make_mine",
        context=Ticketing,
        permission="basic"
    )
    def make_my_ticket_view(self):
        user = self.user
        tick_id = None
        post_purchase = False
        # Find the ticket ID
        if "tick_id" in self.request.matchdict:
            tick_id = self.request.matchdict["tick_id"]
            post_purchase = True
        elif "tick" in self.request.GET:
            tick_id = self.request.GET["tick"]
        elif "tickid" in self.request.POST:
            tick_id = self.request.POST["tick_id"]
        else:
            if post_purchase:
                self.request.session.flash("An error occurred whilst trying to retrieve the ticket details.", "error")
                return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
            else:
                return HTTPFound(location=self.request.route_path("order_details"))
        # Try getting the ticket
        try:
            ticket = [x for x in user.tickets if x.__name__ == tick_id][0]
        except Exception:
            if post_purchase:
                self.request.session.flash("An error occurred whilst trying to retrieve the ticket details.", "error")
                return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
            else:
                return HTTPFound(location=self.request.route_path("order_details"))
        # Check if this ticket is locked down
        locked_down = ticket.tick_type.locked_down
        if not locked_down: # Check all addons as well
            for addon in ticket.addons.values():
                if addon.locked_down:
                    locked_down = True
                    break
        if locked_down:
            self.request.session.flash("Editing of guest details for this ticket has been disabled.", "info")
            return HTTPFound(location=self.request.route_path("ticket_details", tick_id=tick_id))
        # If this is the owners ticket then don't allow them to change the details
        if ticket.guest_info == ticket.owner.profile:
            self.request.session.flash("This ticket was already your ticket, nothing has changed.", "info")
        else:
            # Get my ticket
            try:
                my_ticket = self.user_ticket()
                if not my_ticket:
                    # For whatever reason I mustn't have a ticket, just make this one mine
                    ticket.guest_info = ticket.owner.profile
                    self.request.session.flash("Your ticket has successfully been marked.", "info")
                else:
                    guest_profile = ticket.guest_info
                    ticket.guest_info = ticket.owner.profile
                    my_ticket.guest_info = guest_profile
                    self.request.session.flash("Your ticket has successfully be swapped with your guest.", "info")
            except Exception:
                self.request.session.flash("An error occurred whilst trying to find your current ticket, please try again.", "error")
        return HTTPFound(location=self.request.route_path("ticket_details", tick_id=ticket.__name__))
