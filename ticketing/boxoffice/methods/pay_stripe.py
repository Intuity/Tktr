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

    @view_config(route_name="alter_pay_stripe", context=Ticketing, permission="basic", renderer="templates/stripe.pt")
    @view_config(route_name="pay_stripe", context=Ticketing, permission="basic", renderer="templates/stripe.pt")
    def stripe_view(self):
        # Detect a payment alteration
        payment_id = None
        payment = None
        if "payment_id" in self.request.matchdict:
            payment_id = self.request.matchdict["payment_id"]
        # Check we can be here
        methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method = [x for x in methods if x.__name__ == "stripe" and x.enabled == True]
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
        
        method = method[0]
        # Get some property values
        process_percentage = method.settings[PROP.PAYMENT_PROCESSING_PERCENTAGE].value
        process_fee = method.settings[PROP.PAYMENT_PROCESSING_FEE].value
        pub_api_key = method.settings[PROP.STRIPE_PUBLIC_KEY].value
        organisation_name = method.settings[PROP.ORGANISATION_NAME].value
        contact_email = method.settings[PROP.STRIPE_CONTACT_EMAIL].value
        
        # Ok, all good
        user = self.request.root.users[self.request.session["user_id"]]
        tickets = [x for x in user.tickets if x.payment == None]
        if payment_id == None and len(tickets) == 0:
            return HTTPFound(location=self.request.route_path("buy_tickets"))
        subtotal = 0
        for tick in tickets:
            subtotal += tick.total_cost

        # If we have submitted a Stripe purchase
        error = None
        if "stripeToken" in self.request.POST:
            stripe.api_key = method.settings[PROP.STRIPE_API_KEY].value
            token = self.request.POST["stripeToken"]
            if payment_id == None:
                # Create the holder Stripe payment first, but don't store
                payment = None
                try:
                    payment = Issuer(self.request.root).constructPayment(
                        user_id=self.request.session["user_id"]
                        # ref_code is auto generated
                    )
                    # Try running purchase
                    charge = None
                    try:
                        processing = int(ceil(subtotal * process_percentage) + process_fee)
                        total = int(subtotal + processing)
                        # Create the Stripe charge
                        charge = stripe.Charge.create(
                            amount=total,
                            currency="gbp",
                            source=token,
                            description=organisation_name,
                        )
                        if "paid" in charge and charge["paid"] == True:
                            stage = PaymentStage()
                            stage.__parent__ = payment
                            stage.method = "stripe"
                            stage.method_properties["last_four"] = charge["source"]["last4"]
                            stage.method_properties["ref_code"] = charge["id"]
                            stage.amount_paid = total
                            stage.processing_charge = processing
                            stage.completed = True
                            stage.stage_owner = user.__name__
                            payment.history.append(stage)
                            payment.completed_date = datetime.now()
                            self.request.session["payment_id"] = payment.ref_code
                            logging.info(self.user.username + ": Stripe charge %s succeeded for payment %s" % (charge["id"], payment.__name__))
                            return HTTPFound(location=self.request.route_path("pay_confirm"))
                        else:
                            if "failure_message" in charge and charge["failure_message"] != None:
                                error = charge["failure_message"]
                                logging.error(self.user.username + ": Stripe refused charge: %s" % error)
                            else:
                                logging.error(self.user.username + ": Stripe refused charge")
                                error = "Charge was not accepted by Stripe"
                    except stripe.error.CardError,e :
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
                        logging.exception(self.user.username + ": Generic stripe error: %s" % e)
                        error = "An error occurred with Stripe: %s" % e
                    except Exception, e:
                        logging.exception(self.user.username + ": Exception thrown in stripe checkout: %s" % e)
                        error = e
                    # If we got here and a charge exists, then we need to check if we should refund it
                    if charge != None and "paid" in charge and charge["paid"] == True:
                        # Need to refund pronto!
                        try:
                            refund = stripe.Refund.create(
                                charge=charge["id"],
                                reason="duplicate"
                            )
                            if refund != None and "id" in refund:
                                logging.info(self.user.username + ": Refunded charge %s with refund id %s" % (charge["id"], refund["id"]))
                                error = "Your card was charged and then refunded, an error was thrown: %s" % error
                            else:
                                logging.error(self.user.username + ": Refund of charge %s may have failed" % charge["id"])
                                error = "You card was charged, an error occurred and we may or may not have refunded you, please get in touch with the committee."
                        except Exception, e:
                            logging.error(self.user.username + ": Exception was thrown during refund: %s" % e)
                            error = "Your card was charged and then an error occurred when we tried to refund you: %s" % e
                except Exception, e:
                    logging.error(self.user.username + ": Payment construction threw an error, %s" % e)
                    error = "An error occurred constructing your payment"
                # If we got here we might need to cancel the created payment
                if payment != None:
                    Issuer(self.request.root).cancelPayment(
                        ref_code=payment.__name__,
                        return_to_session=True
                    )
            else:
                # Try running payment alteration
                charge = None
                try:
                    subtotal = payment.amount_remaining
                    processing = int(ceil(subtotal * process_percentage) + process_fee)
                    total = int(ceil(subtotal + processing))
                    charge = stripe.Charge.create(
                        amount=total,
                        currency="gbp",
                        source=token,
                        description=organisation_name,
                    )
                    if "paid" in charge and charge["paid"] == True:
                        new_stage = PaymentStage()
                        new_stage.__parent__ = payment
                        new_stage.method = "stripe"
                        new_stage.method_properties["last_four"] = charge["source"]["last4"]
                        new_stage.method_properties["ref_code"] = charge["id"]
                        new_stage.amount_paid = total
                        new_stage.processing_charge = processing
                        new_stage.received = new_stage.cashed = True
                        new_stage.completed = True
                        new_stage.stage_owner = user.__name__
                        payment.history.append(new_stage)
                        payment.completed_date = datetime.now()
                        logging.info(self.user.username + ": Stripe charge %s succeeded for payment %s" % (charge["id"], payment.__name__))
                        # Forward on to the correct place
                        return HTTPFound(location=self.request.route_path("alter_confirm", payment_id=payment_id))
                    else:
                        if "failure_message" in charge and charge["failure_message"] != None:
                            error = charge["failure_message"]
                            logging.error(self.user.username + ": Stripe refused charge: %s" % error)
                        else:
                            error = "Charge was not accepted by Stripe"
                            logging.error(self.user.username + ": Stripe refused charge")
                except stripe.error.CardError,e :
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
                    logging.exception(self.user.username + ": Generic stripe error: %s" % e)
                    error = "An error occurred with Stripe: %s" % e
                except Exception, e:
                    logging.exception(self.user.username + ": Exception thrown in stripe checkout: %s" % e)
                    error = e
                # If we got here and a charge exists, then we need to check if we should refund it
                if charge != None and "paid" in charge and charge["paid"] == True:
                    # Need to refund pronto!
                    try:
                        refund = stripe.Refund.create(
                            charge=charge["id"],
                            reason="duplicate"
                        )
                        if refund != None and "id" in refund:
                            logging.info(self.user.username + ": Refunded charge %s with refund id %s" % (charge["id"], refund["id"]))
                            error = "Your card was charged and then refunded, an error was thrown: %s" % error
                        else:
                            logging.error(self.user.username + ": Refund of charge %s may have failed" % charge["id"])
                            error = "You card was charged, an error occurred and we may or may not have refunded you, please get in touch with the committee."
                    except Exception, e:
                        logging.exception(self.user.username + ": Exception was thrown during refund: %s" % e)
                        error = "Your card was charged and then an error occurred when we tried to refund you: %s" % e
        # Return information
        if payment_id == None:
            processing = int(ceil(subtotal * process_percentage) + process_fee)
            total = subtotal + processing
            return {
                "error":            error,
                "method":           method,
                "subtotal":         self.format_price(subtotal),
                "processing":       self.format_price(processing),
                "total":            self.format_price(total),
                "org_name":         organisation_name,
                "contact_email":    contact_email,
                "stripe_pub_key":   pub_api_key,
                "penny_total":      total,
                "pay_description":  str(len(self.session_tickets)) + " Ticket(s)",
                "alteration":       False,
                "payment":          None
            }
        else:
            # For payment alteration
            subtotal = payment.amount_remaining
            processing = int(ceil(subtotal * process_percentage) + process_fee)
            total = int(ceil(subtotal + processing))
            return {
                "error":            error,
                "method":           method,
                "subtotal":         self.format_price(subtotal),
                "processing":       self.format_price(processing),
                "total":            self.format_price(total),
                "org_name":         organisation_name,
                "contact_email":    contact_email,
                "stripe_pub_key":   pub_api_key,
                "penny_total":      total,
                "pay_description":  str(len(payment.tickets)) + " Ticket(s)",
                "alteration":       (payment_id != None),
                "payment":          payment
            }
