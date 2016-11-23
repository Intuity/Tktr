from datetime import datetime, timedelta
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from ticketing.boxoffice.issue import Issuer
from ticketing.boxoffice.coding import Coding
from ticketing.boxoffice.models import PaymentStage
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import PROP_KEYS as PROP
from ticketing.models import Ticketing
from ticketing.queue.queue import Queue


class PayBankTransfer(BaseLayout):

    @view_config(route_name="alter_pay_banktransfer", context=Ticketing, permission="basic", renderer="templates/banktransfer.pt")
    @view_config(route_name="pay_banktransfer", context=Ticketing, permission="basic", renderer="templates/banktransfer.pt")
    def banktransfer_view(self):
        # Detect a payment alteration
        payment_id = None
        payment = None
        if "payment_id" in self.request.matchdict:
            payment_id = self.request.matchdict["payment_id"]
        # Check we can be here
        methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method = [x for x in methods if x.__name__ == "banktransfer" and x.enabled == True]
        # - First check queue/active status
        if payment_id == None and Queue(self.request).timed_out():
            return HTTPFound(self.request.route_path("purchase_timeout"))
        # - Now details
        elif payment_id == None and not self.details_complete:
            self.request.session.flash("You must complete all of your guest's details before continuing.", "error")
            return HTTPFound(location=self.request.route_path("order_details"))
        # - Check that the payment method is enabled?
        elif len(method) <= 0:
            self.request.session.flash("There was an error with the payment method you selected, please try again.", "error")
            return HTTPFound(location=self.request.route_path("pay_for_tickets"))
        # - Now run some checks that this person actually should be able to pay this
        elif payment_id != None:
            if not payment_id in self.request.root.payments:
                self.request.session.flash("The requested payment does not exist.", "error")
                return HTTPFound(location=self.request.route_path("user_profile"))
            else:
                payment = self.request.root.payments[payment_id]
                if payment.owner != self.user:
                    self.request.session.flash("The requested payment could not be found on your account.", "error")
                    return HTTPFound(location=self.request.route_path("user_profile"))
                elif payment.paid:
                    self.request.session.flash("The requested payment has already been completed, no need to alter the payment.", "error")
                    return HTTPFound(location=self.request.route_path("user_profile"))
        # Get method, processing fee & other parameters
        method = method[0]
        process_fee = method.settings[PROP.PAYMENT_PROCESSING_FEE].value
        org_name = method.get_value(PROP.ORGANISATION_NAME)
        account_number = method.get_value(PROP.BANK_ACCOUNT)
        sort_code = method.get_value(PROP.BANK_SORT_CODE)
        
        if payment_id == None:
            tickets = [x for x in self.user.tickets if x.payment == None]
            if len(tickets) == 0:
                return HTTPFound(location=self.request.route_path("buy_tickets"))

            subtotal = 0
            for tick in tickets:
                subtotal += tick.total_cost
            processing = process_fee
            total = subtotal + processing

            if "action" in self.request.GET and self.request.GET["action"] == "pay":
                if "payment_id" in self.request.session:
                    ref_code = self.request.session["payment_id"]
                    payment = Issuer(self.request.root).constructPayment(
                        user_id=self.user.__name__,
                        paid=False,
                        ref_code=ref_code
                    )
                    stage = PaymentStage()
                    stage.__parent__ = payment
                    stage.method = "banktransfer"
                    stage.processing_charge = processing
                    stage.stage_owner = self.user.__name__
                    payment.history.append(stage)
                    return HTTPFound(location=self.request.route_path("pay_confirm"))

            if not "payment_id" in self.request.session: # NEED TO CHECK FOR UNIQUENESS
                self.request.session["payment_id"] = Coding().generateUniqueCode(short=True,withdash=False)
        
            return {
                "method":           method,
                "subtotal":         self.format_price(subtotal),
                "processing":       self.format_price(processing),
                "total":            self.format_price(total),
                "org_name":         org_name,
                "alteration":       False,
                "account_number":   account_number,
                "sort_code":        sort_code,
                "payment_id":       self.request.session["payment_id"],
                "payment":          None,
                "due_date":         (datetime.now() + timedelta(days=self.payment_window)).strftime("%d/%m/%Y"),
            }
        else:
            subtotal = payment.amount_remaining
            processing = process_fee
            total = subtotal + processing
            if payment.current_method == "banktransfer":
                subtotal = payment.current_stage.amount_remaining
                processing = payment.current_stage.processing_charge
                total = subtotal + processing
            if "action" in self.request.GET and self.request.GET["action"] == "pay":
                # Don't bother adding a payment stage if we are already paying this way!
                if payment.current_method != "banktransfer":
                    # Add a new stage to the payment
                    new_stage = PaymentStage()
                    new_stage.__parent__ = payment
                    new_stage.method = "banktransfer"
                    new_stage.method_change = True
                    new_stage.processing_charge = processing
                    new_stage.stage_owner = self.user.__name__
                    payment.history.append(new_stage)
                # Forward on to the correct place
                return HTTPFound(location=self.request.route_path("alter_confirm", payment_id=payment_id))

            return {
                "method":           method,
                "subtotal":         self.format_price(subtotal),
                "processing":       self.format_price(processing),
                "total":            self.format_price(total),
                "org_name":         org_name,
                "alteration":       True,
                "account_number":   account_number,
                "sort_code":        sort_code,
                "payment_id":       payment_id,
                "payment":          payment,
                "due_date":         (datetime.now() + timedelta(days=self.payment_window)).strftime("%d/%m/%Y"),
            }
