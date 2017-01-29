from datetime import datetime
from math import ceil
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
import stripe

from ticketing.boxoffice.issue import Issuer
from ticketing.boxoffice.models import PaymentStage
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import PROP_KEYS as PROP
from ticketing.models import Ticketing
from ticketing.queue.queue import Queue

import logging
logging = logging.getLogger("ticketing") 

class PayStripe(BaseLayout):

    def refund_stripe_charge (self, charge_id):
        all_methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method = [x for x in all_methods if x.__name__ == "stripe"]
        method = method[0] if len(method) > 0 else None
        if method == None:
            logging.exception(self.user.username + ": Could not refund %s because could not find stripe payment method" % charge_id)
            return False
        priv_api_key = method.settings[PROP.STRIPE_API_KEY].value
        try:
            stripe.api_key = priv_api_key
            refund = stripe.Refund.create(
                charge=charge_id,
                reason="duplicate"
            )
            if refund != None and "id" in refund:
                logging.info(self.user.username + ": Refunded charge %s with refund id %s" % (charge_id, refund["id"]))
                return True
            else:
                logging.error(self.user.username + ": Refund of charge %s may have failed" % charge_id)
                return False
        except Exception, e:
            logging.error(self.user.username + ": Exception was thrown during refund: %s" % e)
            return False

    @view_config(route_name="pay_stripe", request_method="GET", context=Ticketing, permission="basic", renderer="templates/stripe.pt")
    def pay_stripe_view (self, error=None):
        # Check if the customer's session has timed out
        if Queue(self.request).timed_out():
            return HTTPFound(self.request.route_path("purchase_timeout"))

        # Check the customer is ready to pay
        if not self.details_complete:
            self.request.session.flash("Your guest details are incomplete, please update these before continuing.", "info")
            return HTTPFound(location=self.request.route_path("order_details"))

        # Verify stripe is enabled
        all_methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method = [x for x in all_methods if x.__name__ == "stripe" and x.enabled == True]
        method = method[0] if len(method) > 0 else None
        if method == None:
            self.request.session.flash("An error occurred with the payment method you selected, please try another.", "error")
            return HTTPFound(location=self.request.route_path("order_details"))
        
        # Retrieve stripe processing values
        process_percentage = method.settings[PROP.PAYMENT_PROCESSING_PERCENTAGE].value
        process_fee = method.settings[PROP.PAYMENT_PROCESSING_FEE].value
        pub_api_key = method.settings[PROP.STRIPE_PUBLIC_KEY].value
        organisation_name = method.settings[PROP.ORGANISATION_NAME].value
        contact_email = method.settings[PROP.STRIPE_CONTACT_EMAIL].value
        
        # Check what the user has to buy
        if len(self.session_tickets) == 0:
            self.request.session.flash("No tickets were found in your shopping basket, please try again.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        
        # Calculate the amount to pay
        subtotal = 0
        for tick in self.session_tickets:
            subtotal += tick.total_cost 
        processing = int(ceil(subtotal * process_percentage) + process_fee)
        total = subtotal + processing
        
        # Render the payment page
        return {
            "error"          : error,
            "method"         : method,
            "subtotal"       : self.format_price(subtotal),
            "processing"     : self.format_price(processing),
            "total"          : self.format_price(total),
            "org_name"       : organisation_name,
            "contact_email"  : contact_email,
            "stripe_pub_key" : pub_api_key,
            "penny_total"    : total,
            "pay_description": str(len(self.session_tickets)) + " Ticket(s)",
            "alteration"     : False,
            "payment"        : None
        }

    @view_config(route_name="pay_stripe", request_method="POST", context=Ticketing, permission="basic", renderer="templates/stripe.pt")
    def pay_stripe_view_do (self):
        # This view performs the Stripe transaction as it takes significant time. If we were to
        # construct and process the payment here as well, we would have a database transaction
        # open for too long and hence we would run the risk of a database conflict. So, instead,
        # process the Stripe charge, attach the result to the session, and then move on to the
        # construction of the payment
        # Verify stripe is enabled
        all_methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method = [x for x in all_methods if x.__name__ == "stripe" and x.enabled == True]
        method = method[0] if len(method) > 0 else None
        if method == None:
            self.request.session.flash("An error occurred with the payment method you selected, please try another.", "error")
            return HTTPFound(location=self.request.route_path("order_details"))
        
        # Check that we have been passed a Stripe purchase token
        purchase_token = self.request.POST["stripeToken"] if "stripeToken" in self.request.POST else None
        if purchase_token == None:
            return self.pay_stripe_view(error="No token was provided by Stripe, please try again.")
        
        # Check what the user has to buy
        if len(self.session_tickets) == 0:
            self.request.session.flash("No tickets were found in your shopping basket, please try again.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        
        # Retrieve stripe processing values
        process_percentage = method.settings[PROP.PAYMENT_PROCESSING_PERCENTAGE].value
        process_fee = method.settings[PROP.PAYMENT_PROCESSING_FEE].value
        organisation_name = method.settings[PROP.ORGANISATION_NAME].value
        priv_api_key = method.settings[PROP.STRIPE_API_KEY].value
        
        # Calculate the amount to pay
        subtotal = 0
        for tick in self.session_tickets:
            subtotal += tick.total_cost 
        processing = int(ceil(subtotal * process_percentage) + process_fee)
        total = subtotal + processing
        
        charge = None
        try:
            logging.info(self.user.username + ": Attempting to make Stripe charge for %i with token %s" % (total, purchase_token))
            stripe.api_key = priv_api_key
            charge = stripe.Charge.create(
                amount      = int(ceil(total)),
                currency    = "gbp",
                description = organisation_name,
                source      = purchase_token
            )
            # Handle a charge marked not paid
            if charge == None:
                logging.exception(self.user.username + ": Stripe returned a null charge object")
                return self.pay_stripe_view(error="Stripe failed to process the transaction, please get in touch with the ticketing officer.")
            
            if "paid" not in charge or charge["paid"] != True:
                logging.exception(self.user.username + ": Charge to Stripe failed with ID %s for amount %i %s" % (charge["id"], charge["amount"], charge["currency"]))
                return self.pay_stripe_view(error="Stripe did not accept the charge, please try again.")
            
            # Attach the charge to the session and move on to the completion phase
            logging.info(self.user.username + ": Charge to Stripe succeeded with ID %s for amount %i %s" % (charge["id"], charge["amount"], charge["currency"]))
            self.request.session["stripe_charge"] = charge
            return HTTPFound(location=self.request.route_path("pay_stripe_completion"))
        except stripe.error.CardError as e:
            logging.exception(self.user.username + ": Stripe declined card, raised CardError: %s" % e)
            return self.pay_stripe_view(error="Stripe declined your card with error: %s" % e)
        except stripe.error.RateLimitError as e:
            logging.exception(self.user.username + ": Stripe declined transaction due to rate limit: %s" % e)
            return self.pay_stripe_view(error="Stripe was too busy to handle this transaction, please try again.")
        except stripe.error.InvalidRequestError as e:
            logging.exception(self.user.username + ": Stripe raised an InvalidRequestError: %s" % e)
            return self.pay_stripe_view(error="Stripe declined the payment request with error: %s" % e)
        except stripe.error.AuthenticationError as e:
            logging.exception(self.user.username + ": Stripe raised AuthenticationError: %s" % e)
            return self.pay_stripe_view(error="Authentication with the Stripe service failed with error: %s" % e)
        except stripe.error.APIConnectionError as e:
            logging.exception(self.user.username + ": Stripe raised APIConnectionError: %s" % e)
            return self.pay_stripe_view(error="API connection to the Stripe service failed with error: %s" % e)
        except stripe.error.StripeError as e:
            logging.exception(self.user.username + ": Stripe a generic StripeError: %s" % e)
            return self.pay_stripe_view(error="An error ocurred when accessing the Stripe service: %s" % e)
        except Exception as e:
            logging.exception(self.user.username + ": Exception thrown in Stripe checkout: %s" % e)
            if charge != None and "paid" in charge and charge["paid"] == True:
                self.refund_stripe_charge(charge["id"])
                return self.pay_stripe_view(error="An unexpected error occurred during checkout, your card may have been charged - please get in touch with the ticketing officer immediately: %s" % e)
            else:
                return self.pay_stripe_view(error="An unexpected error occurred during checkout")
        # We should never get here!
        logging.exception(self.user.username + ": Stripe payment escaped expected block")
        return self.pay_stripe_view(error="An unexpected error occurred during checkout, please contact the ticketing officer.")

    @view_config(route_name="pay_stripe_completion", context=Ticketing, permission="basic", renderer="templates/stripe.pt")
    def pay_stripe_completion_do (self):
        # Check that we have a stripe charge object
        stripe_charge = self.request.session["stripe_charge"] if "stripe_charge" in self.request.session else None
        if stripe_charge == None:
            logging.exception(self.user.username + ": Stripe charge object was not found in session")
            return self.pay_stripe_view(error="During processing the Stripe transaction has been lost, please contact the ticketing officer.")
        
        # Clear the charge object from the session
        self.request.session.pop("stripe_charge", None)
        
        # Pickup the stripe method (regardless of if disabled as we now have made a charge!)
        all_methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method = [x for x in all_methods if x.__name__ == "stripe"]
        method = method[0] if len(method) > 0 else None
        if method == None:
            logging.exception(self.user.username + ": Payment method could not be found when trying to attach Stripe charge %s" % stripe_charge["id"])
            self.refund_stripe_charge(stripe_charge["id"])
            return self.pay_stripe_view(error="A critical error occurred during completing the Stripe payment, please contact the ticketing officer.")
         
        # Retrieve stripe processing values
        process_percentage = method.settings[PROP.PAYMENT_PROCESSING_PERCENTAGE].value
        process_fee = method.settings[PROP.PAYMENT_PROCESSING_FEE].value
        
        # Check what the user has to buy
        if len(self.session_tickets) == 0:
            logging.exception(self.user.username + ": No tickets were found pending in the checkout session when trying to attach Stripe charge %s" % stripe_charge["id"])
            self.refund_stripe_charge(stripe_charge["id"])
            return self.pay_stripe_view(error="A critical error occurred during completing the Stripe payment, please contact the ticketing officer.")
        
        # Calculate the amount to pay
        subtotal = 0
        for tick in self.session_tickets:
            subtotal += tick.total_cost 
        processing = int(ceil(subtotal * process_percentage) + process_fee)
        total = subtotal + processing
        
        try:
            # Acquire the source information
            charge_id = stripe_charge["id"] if "source" in stripe_charge else None
            source = stripe_charge["source"] if "source" in stripe_charge else None
            last_four = source["last4"] if source != None and "last4" in source else None
            logging.info(self.user.username + ": Constructing payment from Stripe charge %s" % charge_id)

            # Generate a payment and attach the payment stage to it
            payment = Issuer(self.request.root).constructPayment(user_id=self.user.__name__)
            stage = PaymentStage()
            stage.__parent__ = payment
            stage.method = "stripe"
            stage.method_properties["last_four"] = last_four
            stage.method_properties["ref_code"] = charge_id
            stage.amount_paid = total
            stage.processing_charge = processing
            stage.completed = True
            stage.received = stage.cashed = True
            stage.stage_owner = self.user.__name__
            payment.history.append(stage)
            payment.completed_date = datetime.now()
            self.request.session["payment_id"] = payment.ref_code
            logging.info(self.user.username + ": Successfully constructed payment %s for Stripe charge %s" % (payment.ref_code, charge_id))
            return HTTPFound(location=self.request.route_path("pay_confirm"))
            
        except Exception as e:
            logging.exception(self.user.username + ": Exception thrown in Stripe checkout: %s" % e)
            # We need to refund immediately as this is an error
            charge_id = stripe_charge["id"] if "source" in stripe_charge else None
            if not self.refund_stripe_charge(charge_id):
                return self.pay_stripe_view(error="An error occurred during Stripe checkout and the system could not refund you automatically: %s" % e)
            else:
                return self.pay_stripe_view(error="An error occurred during Stripe checkout but you have been automatically refunded the full amount: %s" % e)
        # We should never get here!
        logging.exception(self.user.username + ": Stripe payment completion escaped expected block")
        return self.pay_stripe_view(error="An unexpected error occurred during checkout, please contact the ticketing officer.")

    @view_config(route_name="alter_pay_stripe", request_method="GET", context=Ticketing, permission="basic", renderer="templates/stripe.pt")
    def alter_pay_stripe_view (self, error=None):
        # Retrieve the payment
        payment_id = self.request.matchdict["payment_id"] if "payment_id" in self.request.matchdict else None
        payment = self.request.root.payments[payment_id] if payment_id != None else None
        if payment == None:
            self.request.session.flash("Could not find the requested payment, please try again.", "info")
            return HTTPFound(location=self.request.route_path("user_profile"))

        # Verify stripe is enabled
        all_methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method = [x for x in all_methods if x.__name__ == "stripe" and x.enabled == True]
        method = method[0] if len(method) > 0 else None
        if method == None:
            self.request.session.flash("An error occurred with the payment method you selected, please try another.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        
        # Retrieve stripe processing values
        process_percentage = method.settings[PROP.PAYMENT_PROCESSING_PERCENTAGE].value
        process_fee = method.settings[PROP.PAYMENT_PROCESSING_FEE].value
        pub_api_key = method.settings[PROP.STRIPE_PUBLIC_KEY].value
        organisation_name = method.settings[PROP.ORGANISATION_NAME].value
        contact_email = method.settings[PROP.STRIPE_CONTACT_EMAIL].value
        
        # Calculate the amount to pay
        subtotal = payment.amount_remaining
        processing = int(ceil(subtotal * process_percentage) + process_fee)
        total = int(ceil(subtotal + processing))
        
        # Render the payment page
        return {
            "error"          : error,
            "method"         : method,
            "subtotal"       : self.format_price(subtotal),
            "processing"     : self.format_price(processing),
            "total"          : self.format_price(total),
            "org_name"       : organisation_name,
            "contact_email"  : contact_email,
            "stripe_pub_key" : pub_api_key,
            "penny_total"    : total,
            "pay_description": str(len(payment.tickets)) + " Ticket(s)",
            "alteration"     : True,
            "payment"        : payment
        }

    @view_config(route_name="alter_pay_stripe", request_method="POST", context=Ticketing, permission="basic", renderer="templates/stripe.pt")
    def alter_pay_stripe_view_do (self):
        # Retrieve the payment
        payment_id = self.request.matchdict["payment_id"] if "payment_id" in self.request.matchdict else None
        payment = self.request.root.payments[payment_id] if payment_id != None else None
        if payment == None:
            self.request.session.flash("Could not find the requested payment, please try again.", "info")
            return HTTPFound(location=self.request.route_path("user_profile"))
        
        # This view performs the Stripe transaction as it takes significant time. If we were to
        # construct and process the payment here as well, we would have a database transaction
        # open for too long and hence we would run the risk of a database conflict. So, instead,
        # process the Stripe charge, attach the result to the session, and then move on to the
        # construction of the payment
        # Verify stripe is enabled
        all_methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method = [x for x in all_methods if x.__name__ == "stripe" and x.enabled == True]
        method = method[0] if len(method) > 0 else None
        if method == None:
            self.request.session.flash("An error occurred with the payment method you selected, please try another.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        
        # Check that we have been passed a Stripe purchase token
        purchase_token = self.request.POST["stripeToken"] if "stripeToken" in self.request.POST else None
        if purchase_token == None:
            return self.alter_pay_stripe_view(error="No token was provided by Stripe, please try again.")
        
        # Retrieve stripe processing values
        process_percentage = method.settings[PROP.PAYMENT_PROCESSING_PERCENTAGE].value
        process_fee = method.settings[PROP.PAYMENT_PROCESSING_FEE].value
        organisation_name = method.settings[PROP.ORGANISATION_NAME].value
        priv_api_key = method.settings[PROP.STRIPE_API_KEY].value
        
        # Calculate the amount to pay
        subtotal = payment.amount_remaining
        processing = int(ceil(subtotal * process_percentage) + process_fee)
        total = int(ceil(subtotal + processing))
        
        charge = None
        try:
            logging.info(self.user.username + ": Attempting to make Stripe charge to alter payment %s with total %i with token %s" % (payment_id, total, purchase_token))
            stripe.api_key = priv_api_key
            charge = stripe.Charge.create(
                amount      = int(ceil(total)),
                currency    = "gbp",
                description = organisation_name,
                source      = purchase_token
            )
            # Handle a charge marked not paid
            if charge == None:
                logging.exception(self.user.username + ": Stripe returned a null charge object")
                return self.alter_pay_stripe_view(error="Stripe failed to process the transaction, please get in touch with the ticketing officer.")
            
            if "paid" not in charge or charge["paid"] != True:
                logging.exception(self.user.username + ": Charge to Stripe failed with ID %s for amount %i %s" % (charge["id"], charge["amount"], charge["currency"]))
                return self.alter_pay_stripe_view(error="Stripe did not accept the charge, please try again.")
            
            # Attach the charge to the session and move on to the completion phase
            logging.info(self.user.username + ": Charge to Stripe succeeded with ID %s for amount %i %s" % (charge["id"], charge["amount"], charge["currency"]))
            self.request.session["stripe_charge"] = charge
            return HTTPFound(location=self.request.route_path("alter_pay_stripe_completion", payment_id=payment.__name__))
        except stripe.error.CardError as e:
            logging.exception(self.user.username + ": Stripe declined card, raised CardError: %s" % e)
            return self.alter_pay_stripe_view(error="Stripe declined your card with error: %s" % e)
        except stripe.error.RateLimitError as e:
            logging.exception(self.user.username + ": Stripe declined transaction due to rate limit: %s" % e)
            return self.alter_pay_stripe_view(error="Stripe was too busy to handle this transaction, please try again.")
        except stripe.error.InvalidRequestError as e:
            logging.exception(self.user.username + ": Stripe raised an InvalidRequestError: %s" % e)
            return self.alter_pay_stripe_view(error="Stripe declined the payment request with error: %s" % e)
        except stripe.error.AuthenticationError as e:
            logging.exception(self.user.username + ": Stripe raised AuthenticationError: %s" % e)
            return self.alter_pay_stripe_view(error="Authentication with the Stripe service failed with error: %s" % e)
        except stripe.error.APIConnectionError as e:
            logging.exception(self.user.username + ": Stripe raised APIConnectionError: %s" % e)
            return self.alter_pay_stripe_view(error="API connection to the Stripe service failed with error: %s" % e)
        except stripe.error.StripeError as e:
            logging.exception(self.user.username + ": Stripe a generic StripeError: %s" % e)
            return self.alter_pay_stripe_view(error="An error ocurred when accessing the Stripe service: %s" % e)
        except Exception as e:
            logging.exception(self.user.username + ": Exception thrown in Stripe checkout: %s" % e)
            if charge != None and "paid" in charge and charge["paid"] == True:
                self.refund_stripe_charge(charge["id"])
                return self.alter_pay_stripe_view(error="An unexpected error occurred during checkout, your card may have been charged - please get in touch with the ticketing officer immediately: %s" % e)
            else:
                return self.alter_pay_stripe_view(error="An unexpected error occurred during checkout")
        # We should never get here!
        logging.exception(self.user.username + ": Stripe payment escaped expected block")
        return self.alter_pay_stripe_view(error="An unexpected error occurred during checkout, please contact the ticketing officer.")

    @view_config(route_name="alter_pay_stripe_completion", context=Ticketing, permission="basic", renderer="templates/stripe.pt")
    def alter_pay_stripe_completion_do (self):
        # Check that we have a stripe charge object
        stripe_charge = self.request.session["stripe_charge"] if "stripe_charge" in self.request.session else None
        if stripe_charge == None:
            logging.exception(self.user.username + ": Stripe charge object was not found in session")
            return self.alter_pay_stripe_view(error="During processing the Stripe transaction has been lost, please contact the ticketing officer.")
        
        # Clear the charge object from the session
        self.request.session.pop("stripe_charge", None)
        
        # Retrieve the payment
        payment_id = self.request.matchdict["payment_id"] if "payment_id" in self.request.matchdict else None
        payment = self.request.root.payments[payment_id] if payment_id != None else None
        if payment == None:
            logging.exception(self.user.username + ": Payment could not be located whilst trying to update payment with Stripe charge %s" % stripe_charge["id"])
            self.refund_stripe_charge(stripe_charge["id"])
            return self.alter_pay_stripe_view(error="During processing a critical error occurred, please contact the ticketing officer immediately.")
        
        # Pickup the stripe method (regardless of if disabled as we now have made a charge!)
        all_methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method = [x for x in all_methods if x.__name__ == "stripe"]
        method = method[0] if len(method) > 0 else None
        if method == None:
            logging.exception(self.user.username + ": Method could not be found whilst trying to update payment %s with Stripe charge %s" % (payment_id, stripe_charge["id"]))
            self.refund_stripe_charge(stripe_charge["id"])
            return self.alter_pay_stripe_view(error="During processing a critical error occurred, please contact the ticketing officer immediately.")
         
        # Retrieve stripe processing values
        process_percentage = method.settings[PROP.PAYMENT_PROCESSING_PERCENTAGE].value
        process_fee = method.settings[PROP.PAYMENT_PROCESSING_FEE].value
        
        # Calculate the amount to pay
        subtotal = payment.amount_remaining
        processing = int(ceil(subtotal * process_percentage) + process_fee)
        total = int(ceil(subtotal + processing))
        
        try:
            # Acquire the source information
            charge_id = stripe_charge["id"] if "source" in stripe_charge else None
            source = stripe_charge["source"] if "source" in stripe_charge else None
            last_four = source["last4"] if source != None and "last4" in source else None
            logging.info(self.user.username + ": Constructing payment from Stripe charge %s" % charge_id)

            # Attach new payment stage to the payment
            stage = PaymentStage()
            stage.__parent__ = payment
            stage.method = "stripe"
            stage.method_properties["last_four"] = last_four
            stage.method_properties["ref_code"] = charge_id
            stage.amount_paid = total
            stage.processing_charge = processing
            stage.completed = True
            stage.received = stage.cashed = True
            stage.stage_owner = self.user.__name__
            payment.history.append(stage)
            payment.completed_date = datetime.now()
            self.request.session["payment_id"] = payment.ref_code
            logging.info(self.user.username + ": Successfully updated payment %s with Stripe charge %s" % (payment.ref_code, charge_id))
            return HTTPFound(location=self.request.route_path("alter_confirm", payment_id=payment_id))
            
        except Exception as e:
            logging.exception(self.user.username + ": Exception thrown in Stripe checkout: %s" % e)
            # We need to refund immediately as this is an error
            charge_id = stripe_charge["id"] if "source" in stripe_charge else None
            if not self.refund_stripe_charge(charge_id):
                return self.alter_pay_stripe_view(error="An error occurred during Stripe checkout and the system could not refund you automatically: %s" % e)
            else:
                return self.alter_pay_stripe_view(error="An error occurred during Stripe checkout but you have been automatically refunded the full amount: %s" % e)
        # We should never get here!
        logging.exception(self.user.username + ": Stripe payment completion escaped expected block")
        return self.alter_pay_stripe_view(error="An unexpected error occurred during checkout, please contact the ticketing officer.")
