# Alter payment views
from datetime import timedelta
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from ticketing.email.templates import PurchaseAlterationEmail
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import Ticketing
from ticketing.models import PROP_KEYS as PROP

import logging
logging = logging.getLogger("ticketing")

class AlterPayment(BaseLayout):

    @view_config(
        route_name="alter_payment", 
        context=Ticketing, 
        permission="basic", 
        renderer="templates/alter_payment.pt"
    )
    def alter_payment_view(self):
        tick_id = self.request.matchdict["tick_id"]
        user = self.user
        ticket = None
        # Find ticket
        for tick in user.tickets:
            if tick.__name__ == tick_id:
                ticket = tick
                break
        # If not found, user doesn't own it!
        if ticket == None:
            self.request.session.flash("The requested ticket does not exist.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Check this is not a purchased ticket
        elif ticket.payment.paid:
            self.request.session.flash("The requested ticket has already been paid for.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Move to the payment stage
        elif "method" in self.request.GET:
            logging.info(self.user.username + " has chosen " + self.request.GET["method"] + " as payment method")
            # Check this is a valid, registered payment method
            method = self.get_payment_method(self.request.GET["method"].lower())
            if method != None:
                # Look for a route to make this payment by
                try:
                    route_url = self.request.route_path("alter_pay_" + method.__name__, payment_id=ticket.payment.__name__)
                    return HTTPFound(location=route_url)
                except(KeyError):
                    self.request.session.flash("An error occurred with the payment method you selected, please try again.", "error")
                    logging.warn(self.user.username + " has requested a payment route that doesn't exist")
            else:
                self.request.session.flash("An error occurred with the payment method you selected, please try again.", "error")
                logging.warn(self.user.username + " has requested a payment method either that doesn't exist or is disabled")
        # Get payment method
        orig_method = self.get_payment_method(ticket.payment.history[-1].method)
        orig_method_name = "Unknown"
        if orig_method != None:
            orig_method_name = orig_method.name
        return {
            "tick_id": tick_id,
            "payment" : ticket.payment,
            "orig_method_name": orig_method_name,
            "orig_method": orig_method,
            "methods": [x for x in PROP.getProperty(self.request, PROP.PAYMENT_METHODS) if x.enabled and x.public]
        }

    @view_config(
        route_name="alter_confirm",
        context=Ticketing,
        permission="basic",
        renderer="templates/alter_confirm.pt"
    )
    def alter_payment_confirm_view(self):
        payment_id = self.request.matchdict["payment_id"]
        payment = self.request.root.payments[payment_id]
        method = self.get_payment_method(payment.current_method)
        # Check payment ownership
        if payment.owner != self.user:
            self.request.session.flash("The requested payment does not exist.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        logging.info(self.user.username + " has confirmed " + payment.current_method + " as payment method")
        # Send a confirmation email
        confirm = PurchaseAlterationEmail(self.request)
        if not confirm.compose_and_send(payment.ref_code):
            self.request.session.flash("Could not send your alteration confirmation, please contact webmaster@mayball.com", "error")
            logging.error(self.user.username + ": could not send alteration confirmation")
        return {
            "payment": payment,
            "banktransfer": (payment.method == "banktransfer"),
            "due_date": (payment.opened_date + timedelta(days=self.payment_window)).strftime("%d/%m/%Y"),
            "method": method,
            "org_name": method.get_value(PROP.ORGANISATION_NAME),
            "acct_number": method.get_value(PROP.BANK_ACCOUNT),
            "sort_code": method.get_value(PROP.BANK_SORT_CODE),
        }
