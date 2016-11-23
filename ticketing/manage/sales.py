# -*- coding: utf-8 -*- 

from datetime import datetime, timedelta
import json
from math import ceil, floor
from pyramid.httpexceptions import HTTPFound
from pyramid.response import Response
from pyramid.view import view_config
import time

from ticketing.boxoffice.issue import Issuer
from ticketing.boxoffice.models import PaymentStage
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import PROP_KEYS
from ticketing.email.templates import GenericEmail, PurchaseConfirmationEmail
from ticketing.boxoffice.download import TicketDownload

import logging
logging = logging.getLogger("ticketing")

class Sales(BaseLayout):

    @view_config(
        route_name="admin_sales",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/sales.pt"
    )
    def sales_view(self):
        # User Statistics
        users = self.request.root.users.values()
        # Respond to actions
        if "action" in self.request.GET:
            if self.request.GET["action"] == "cleardead":
                # Check for tickets released but not attached to a payment
                issue = Issuer(self.request.root)
                count = 0;
                for user in users:
                    ticks = [x for x in user.tickets if x.payment == None]
                    for tick in ticks:
                        # Don't bounce tickets out if only allocated in the last five minutes
                        if (datetime.now() - tick.issue_date).total_seconds() > 300:
                            issue.returnTicket(tick)
                            count += 1
        # Get date to present
        lc_data = self.line_graph_data(self.request.root)
        json_lc = self.json_line_graph_data(self.request.root, data=lc_data)
        lc_min_data = self.minute_line_graph_data(self.request.root)
        json_lc_min = self.json_line_graph_data(self.request.root, data=lc_min_data)
        bc_data = self.bar_chart_data(self.request.root)
        return {
            "sales_exist": (len(lc_data["lc_titles"]) > 0),
            "lc_titles": json_lc["lc_titles"],
            "lc_sales": json_lc["lc_sales"],
            "lc_revenue": json_lc["lc_revenue"],
            "lc_minute_titles": json_lc_min["lc_titles"],
            "lc_minute_sales": json_lc_min["lc_sales"],
            "lc_minute_revenue": json_lc_min["lc_revenue"],
            # For bar chart
            "bc_titles": bc_data["bc_titles"],
            "bc_sold": bc_data["bc_sold"],
            "bc_unsold": bc_data["bc_unsold"],
            "bc_step_val": bc_data["bc_step_val"],
            # Pie chart
            "basicbreakdown": self.pie_chart_data(self.request.root),
        }

    def json_line_graph_data(self, root, data=None):
        if data == None:
            data = self.line_graph_data(root)
        return {
            "lc_titles":    json.dumps(data["lc_titles"]),
            "lc_sales":     json.dumps(data["lc_sales"]),
            "lc_revenue":   json.dumps(data["lc_revenue"])
        }

    def line_graph_data(self, root):
        payments_by_date = {}
        all_payments = root.payments.values()
        for payment in all_payments:
            day_stamp = time.mktime(payment.opened_date.replace(hour=0, minute=0, second=0, microsecond=0).timetuple())
            if not day_stamp in payments_by_date:
                payments_by_date[day_stamp] = [0, 0] # Index 0 -> number of tickets, index 1 -> sum total
            payments_by_date[day_stamp][0] += len(payment.tickets)
            payments_by_date[day_stamp][1] += payment.total
        # Order by date
        sorted_stamps = sorted(payments_by_date.keys())
        # Cut-down to the last 14 entries (if that many exist)
        cutdown = sorted_stamps
        if len(sorted_stamps) >= 14:
            cutdown = sorted_stamps[-14:]
        # Make sure we are date-spacing the last 14 entries
        lc_dates = []; lc_sales = []; lc_revenue = []
        if len(cutdown) > 0:
            most_recent_date = datetime.fromtimestamp(cutdown[-1])
            for i in range(0, 14):
                check_date = (most_recent_date - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
                check_stamp = time.mktime(check_date.timetuple())
                lc_dates.append(check_date.strftime("%d/%m"))
                if not check_stamp in cutdown:
                    lc_sales.append(0)
                    lc_revenue.append(0)
                else:
                    lc_sales.append(payments_by_date[check_stamp][0])
                    lc_revenue.append(payments_by_date[check_stamp][1] / 100.0)
        return {
            "lc_titles": lc_dates[::-1],
            "lc_sales": lc_sales[::-1],
            "lc_revenue": lc_revenue[::-1],
        }

    def minute_line_graph_data(self, root):
        payments_by_date = {}
        all_payments = root.payments.values()
        for payment in all_payments:
            day_stamp = time.mktime(payment.opened_date.replace(minute=int(floor(payment.opened_date.minute / 30) * 30), second=0, microsecond=0).timetuple())
            if not day_stamp in payments_by_date:
                payments_by_date[day_stamp] = [0, 0] # Index 0 -> number of tickets, index 1 -> sum total
            payments_by_date[day_stamp][0] += len(payment.tickets)
            payments_by_date[day_stamp][1] += payment.total
        # Order by date
        sorted_stamps = sorted(payments_by_date.keys())
        # Cut-down to the last 1440 entries (the last day in minutes, if that many exist)
        cutdown = sorted_stamps
        if len(sorted_stamps) >= 50:
            cutdown = sorted_stamps[-50:]
        # Make sure we are date-spacing the last 14 entries
        lc_dates = []; lc_sales = []; lc_revenue = []
        if len(cutdown) > 0:
            most_recent_date = datetime.fromtimestamp(cutdown[-1])
            for i in range(0, 24):
                check_date = (most_recent_date - timedelta(minutes=i*30)).replace(second=0, microsecond=0)
                check_stamp = time.mktime(check_date.timetuple())
                lc_dates.append(check_date.strftime("%H:%M"))
                if not check_stamp in cutdown:
                    lc_sales.append(0)
                    lc_revenue.append(0)
                else:
                    lc_sales.append(payments_by_date[check_stamp][0])
                    lc_revenue.append(payments_by_date[check_stamp][1] / 100.0)
        return {
            "lc_titles": lc_dates[::-1],
            "lc_sales": lc_sales[::-1],
            "lc_revenue": lc_revenue[::-1],
        }

    def pie_chart_data(self, root):
        pools = root.ticket_pools.values()
        basicbreakdown = {
            "sold": 0,
            "unsold": 0,
            "total": 0,
        }
        for pool in pools:
            in_pool = len(pool.tickets)
            released = pool.tick_type.total_released
            sold = released - in_pool
            basicbreakdown["sold"] += sold
            basicbreakdown["unsold"] += in_pool
            basicbreakdown["total"] += released
        return basicbreakdown

    def bar_chart_data(self, root):
        pools = root.ticket_pools.values()
        bc_titles = []
        bc_sold = []
        bc_unsold = []
        bc_max = 0
        bc_step_val = 0
        for pool in pools:
            in_pool = len(pool.tickets)
            released = pool.tick_type.total_released
            sold = released - in_pool
            bc_titles.append(pool.tick_type.name[:10])
            bc_sold.append(sold)
            bc_unsold.append(in_pool)
            if sold > bc_max:
                bc_max = sold
            if in_pool > bc_max:
                bc_max = in_pool
        bc_step_val = int(bc_step_val) / 10 + 10
        return {
            "bc_titles": json.dumps(bc_titles),
            "bc_sold": json.dumps(bc_sold),
            "bc_unsold": json.dumps(bc_unsold),
            "bc_step_val": bc_step_val,
        }

    @view_config(
        route_name="admin_payments",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/payments.pt"
    )
    def payments_view(self):
        users = self.request.root.users.values()
        payments = []
        filter_type = None
        filter_value = None
        if "filter" in self.request.GET and len(self.request.GET["filter"]) > 0:
            filter_type = self.request.GET["filter"]
            filter_value = self.request.GET["filtervalue"].lower()
            if filter_type == "status":
                payments = self.request.root.payments.values()
                if "filtervalue-status" in self.request.GET:
                    filter_value = self.request.GET["filtervalue-status"]
                window = PROP_KEYS.getProperty(self.request, PROP_KEYS.PAYMENT_WINDOW)
                # Now filter for payment status
                if filter_value == "paid":
                    payments = [x for x in payments if x.paid]
                elif filter_value == "unpaid":
                    payments = [x for x in payments if not x.paid]
                elif filter_value == "expiring":
                    payments = [x for x in payments if x.expiring(window) and not x.expired(window) and not x.paid]
                elif filter_value == "expired":
                    payments = [x for x in payments if x.expired(window) and not x.paid]

            elif filter_type == "refcode":
                for user in users:
                    for payment in user.payments:
                        if filter_value in payment.ref_code.lower():
                            payments.append(payment)

            else:
                # For these details, filter by user then extract tickets
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
                # After filtering run through all of the users
                for user in users:
                    for payment in user.payments:
                        payments.append(payment)
        else:
            payments = self.request.root.payments.values()

        # All results are sorted date ascending
        payments = sorted(payments, key=lambda x: x.opened_date, reverse=True)

        # Paginate the data
        total_pages = ceil((len(payments) - 1) / 75.0)
        current_page = 1
        start_index = end_index = 0
        if len(payments) > 0:
            if "page" in self.request.GET:
                current_page = int(float(self.request.GET["page"]))
                if current_page <= 0:
                    current_page = 1
            start_index = (current_page - 1) * 75
            end_index = start_index + 75
            if start_index >= len(payments):
                start_index = 0
                end_index = 75
                self.request.session.flash("You requested a page that was unavailable", "error")
                current_page = 1
            if end_index >= len(payments):
                end_index = len(payments)

        if filter_type == None:
            filter_type = ""
            filter_value = ""

        return {
            "payments": payments[start_index:end_index],
            "total_pages": int(total_pages),
            "current_page": int(current_page),
            "filter": filter_type,
            "value": filter_value
        }

    @view_config(
        route_name="admin_single_payment",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/view_payment.pt"
    )
    def single_payment_view(self):
        payments = self.request.root.payments
        # Get payment if possible
        if not self.request.matchdict["ref_code"] in self.request.root.payments:
            return HTTPFound(location=self.request.route_path("admin_payments"))
        payment = payments[self.request.matchdict["ref_code"]]
        if "action" in self.request.GET:
            if self.request.GET["action"] == "recalculate":
                if payment.method == "stripe":
                    payment.processing = int(payment.item_total * self.stripe_percentage)
                    payment.total = int(payment.item_total * (1 + self.stripe_percentage))
                else:
                    payment.processing = 0
                    payment.total = payment.item_total
                self.request.session.flash("Recalculated the payment total.", "info")
            elif self.request.GET["action"] == "emailconfirm":
                PurchaseConfirmationEmail(self.request).compose_and_send(payment.ref_code)
                self.request.session.flash("A payment confirmation has been sent via email.", "info")
            elif self.request.GET["action"] == "sendtickets":
                emailer = GenericEmail(self.request)
                emailer.compose_and_send(
                    "Event Tickets",
                    """Please find the tickets you purchased in payment %s attached as a PDF to this email. Please download and print-out the tickets and bring them with you to the event.""" % (payment.ref_code),
                    payment.owner.__name__,
                    pdf_attachment=TicketDownload(self.request).payment_tickets_pdf(payment)
                )
                self.request.session.flash("The tickets in this payment have been sent via email.", "info")
        
        return {
            "payment": payment,
        }

    @view_config(
        route_name="admin_payment_stage",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/view_stage.pt"
    )
    def payment_stage_view(self):
        if not self.request.matchdict["ref_code"] in self.request.root.payments:
            return HTTPFound(location=self.request.route_path("admin_payments"))
        payment = self.request.root.payments[self.request.matchdict["ref_code"]]
        stage_index = int(float(self.request.matchdict["stage_index"]))
        if stage_index < 0 or stage_index >= len(payment.history):
            return HTTPFound(location=self.request.route_path("admin_single_payment", ref_code=payment.__name__))
        if "action" in self.request.GET and self.request.GET["action"] == "delete":
            if len(payment.history) <= 1:
                self.request.session.flash("Must have at least one payment left undeleted", "error")
            else:
                del payment.history[stage_index]
                # Need to work out if still paid?
                if payment.amount_remaining > 0:
                    payment.completed_date = None
                    # Check if the latest stage has been paid into yet?
                    latest = payment.history[-1]
                    if latest.completed:
                        # Add a new payment stage of the same type as the latest
                        new_stage = PaymentStage()
                        new_stage.__parent__ = payment
                        new_stage.method = latest.method
                        new_stage.stage_owner = payment.owner.__name__
                        payment.history.append(new_stage)
                self.request.session.flash("Removed payment stage successfully", "info")
                return HTTPFound(location=self.request.route_path("admin_single_payment", ref_code=payment.__name__))
        return {
            "payment": payment,
            "stage": payment.history[stage_index]
        }

    @view_config(
        route_name="admin_ticket_remove",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/remove_ticket.pt"
    )
    def remove_ticket_view(self):
        payments = self.request.root.payments
        # Get payment if possible
        if not self.request.matchdict["ref_code"] in self.request.root.payments:
            return HTTPFound(location=self.request.route_path("admin_payments"))
        payment = payments[self.request.matchdict["ref_code"]]
        #if payment.paid:
        #    self.request.session.flash("This payment has already been confirmed, you cannot remove a ticket anymore.", "error")
        #    return HTTPFound(location=self.request.route_path('admin_single_payment', ref_code=payment.__name__))
        ticket = [x for x in payment.tickets if x.__name__ == self.request.matchdict["tick_id"]][0]
        if "submit" in self.request.POST:
            if not "reason" in self.request.POST or len(self.request.POST["reason"]) < 10:
                self.request.session.flash("You must enter a reason for the ticket to be removed from the payment.", "error")
                return {
                    "payment": payment,
                    "ticket": ticket
                }
            else:
                reason = self.request.POST["reason"]
                pool = ticket.tick_type.__parent__
                owner = ticket.owner
                # Release all addons
                ticket.release_addons()
                # Remove from the user
                owner.tickets.remove(ticket)
                owner.total_tickets -= 1
                payment.tickets.remove(ticket)
                pool.tickets.append(ticket)
                ticket.__parent__ = pool
                # Blank out user details
                ticket.owner = None
                ticket.payment = None
                ticket.issue_date = None
                ticket.guest_info = None
                logging.info("%s: Removed ticket %s from payment %s of user %s" % (self.user.username, ticket.__name__, payment.__name__, owner.username))
                # Check if the payment is now empty, and close it if so
                if len(payment.tickets) == 0:
                    owner.payments.remove(payment)
                    self.request.root.payments.pop(payment.__name__, None)
                    logging.info("%s: Closed payment %s of user %s" % (self.user.username, payment.__name__, owner.username))
                # The amount due from the payment is automatically recalculated
                self.request.session.flash("The ticket has been removed from the payment and returned to the pool.", "info")
                emailer = GenericEmail(self.request)
                emailer.compose_and_send(
                    "Ticket Cancellation",
                    """A ticket has been removed from payment %s for the following reason:<br /><br />%s""" % (payment.ref_code, reason),
                    payment.owner.__name__
                )
                return HTTPFound(location=self.request.route_path('admin_single_payment', ref_code=payment.__name__))
        return {
            "payment": payment,
            "ticket": ticket
        }

    @view_config(
        route_name="admin_payment_reject",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/reject_payment.pt"
    )
    def reject_payment_view(self):
        payments = self.request.root.payments
        # Get payment if possible
        if not self.request.matchdict["ref_code"] in self.request.root.payments:
            return HTTPFound(location=self.request.route_path("admin_payments"))
        payment = payments[self.request.matchdict["ref_code"]]
        return {
            "payment": payment
        }

    @view_config(
        route_name="admin_payment_reject",
        context="ticketing.models.Ticketing",
        permission="committee",
        request_method="POST"
    )
    def reject_payment_view_do(self):
        payments = self.request.root.payments
        # Get payment if possible
        if not self.request.matchdict["ref_code"] in self.request.root.payments:
            return HTTPFound(location=self.request.route_path("admin_payments"))
        payment = payments[self.request.matchdict["ref_code"]]
        # Process form
        reason = self.request.POST["reason"]
        if len(reason) < 5:
            self.request.session.flash("You did not provide a full reason for payment rejection.", "error")
            return HTTPFound(location=self.request.route_path("admin_payment_reject", ref_code=payment.__name__))
        # Remove payment and return all tickets
        issuer = Issuer(self.request.root)
        issuer.cancelPayment(payment.__name__)
        # Forward on
        self.request.session.flash("The payment has been rejected successfully.", "info")
        logging.info("%s: Rejected payment %s for user %s with reason %s" % (self.user.username, payment.__name__, payment.owner.username, reason))
        # Inform customer of the reason
        if payment.owner.profile != None:
            emailer = GenericEmail(self.request)
            emailer.compose_and_send(
                "Payment Rejection",
                """Your ticket purchase (reference code %s) has been rejected for the following reason:<br /><br />%s""" % (payment.ref_code, reason),
                payment.owner.__name__
            )
        return HTTPFound(location=self.request.route_path("admin_payments"))

    @view_config(
        route_name="admin_payment_change",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/change_payment_method.pt"
    )
    def change_payment_method_view(self):
        payments = self.request.root.payments
        # Get payment if possible
        if not self.request.matchdict["ref_code"] in self.request.root.payments:
            return HTTPFound(location=self.request.route_path("admin_payments"))
        payment = payments[self.request.matchdict["ref_code"]]
        active_stage = (payment.history[len(payment.history) - 1] if (len(payment.history) > 0) else None)
        # Check if already marked as paid
        if payment.paid:
            return HTTPFound(location=self.request.route_path('admin_single_payment', ref_code=payment.__name__))
        # Deal with post request
        if "submit" in self.request.POST:
            if not "method" in self.request.POST:
                self.request.session.flash("Make sure to select a new payment method.", "error")
            else:
                method = self.request.POST["method"]
                # - First check if the active stage is the current method
                if active_stage.method != method:
                    # Update payment method to match that entered
                    active_stage = PaymentStage()
                    active_stage.__parent__ = payment
                    active_stage.method = method
                    active_stage.stage_owner = payment.owner.__name__
                    active_stage.amount_paid = 0
                    active_stage.processing_charge = 0
                    active_stage.completed = False
                    payment.history.append(active_stage)
                self.request.session.flash("Payment details have been updated.", "info")
                return HTTPFound(location=self.request.route_path('admin_single_payment', ref_code=payment.__name__))
        return {
            "payment": payment,
            "active_stage": active_stage,
            "methods": PROP_KEYS.getProperty(self.request, PROP_KEYS.PAYMENT_METHODS)
        }

    @view_config(
        route_name="admin_payment_enter",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/enter_payment.pt"
    )
    def enter_payment_view(self):
        payments = self.request.root.payments
        # Get payment if possible
        if not self.request.matchdict["ref_code"] in self.request.root.payments:
            return HTTPFound(location=self.request.route_path("admin_payments"))
        payment = payments[self.request.matchdict["ref_code"]]
        active_stage = (payment.history[len(payment.history) - 1] if (len(payment.history) > 0) else None)
        # Check if already marked as paid
        if payment.paid:
            return HTTPFound(location=self.request.route_path('admin_single_payment', ref_code=payment.__name__))
        # Process form
        error = None
        if "submit" in self.request.POST:
            try:
                if not "amount" in self.request.POST or float(self.request.POST['amount']) <= 0: error = "An amount of money greater than zero must be specified"
                elif not "method" in self.request.POST or self.get_payment_method(self.request.POST["method"]) == None: error = "A valid payment method must be specified"
                elif not "year" in self.request.POST or not "month" in self.request.POST or not "day" in self.request.POST: error = "A valid date must be entered"
                elif int(self.request.POST["year"]) < 2000 or int(self.request.POST["month"]) < 1 or int(self.request.POST["month"]) > 12 or int(self.request.POST["day"]) < 1 or int(self.request.POST["day"]) > 31: error = "A valid date must be entered"
                # elif not "status" in self.request.POST or self.request.POST["status"] not in ["cashed", "received"]: error = "You must select a valid payment status"
                if not error:
                    # Process this payment stage through
                    amount = floor(float(self.request.POST["amount"]) * 100.0)
                    method = self.request.POST["method"]
                    year = int(self.request.POST["year"])
                    month = int(self.request.POST["month"])
                    day = int(self.request.POST["day"])
                    transaction_date = datetime(year=year, month=month, day=day)
                    # - First check if the active stage is the current method
                    if active_stage.method != method:
                        # Update payment method to match that entered
                        active_stage = PaymentStage()
                        active_stage.__parent__ = payment
                        active_stage.method = method
                        active_stage.stage_owner = payment.owner.__name__
                        payment.history.append(active_stage)
                    # Update amount paid
                    active_stage.amount_paid = amount
                    active_stage.completed = True # Doesn't mean 'fully paid' just something has happened at this stage
                    
                    # Check for a complete sale
                    if active_stage.amount_remaining <= active_stage.amount_paid:
                        payment.completed_date = transaction_date
                        # Send payment confirmation email
                        emailer = GenericEmail(self.request)
                        emailer.compose_and_send(
                            "Ticket Payment Completed",
                            """Your ticket purchase (reference code %s) has now been confirmed as a result of your complete payment being received on %s and there is no 
                            further action required.""" 
                            % (payment.ref_code, payment.completed_date.strftime("%d/%m/%Y")), 
                            payment.owner.__name__
                        )
                    else:
                        # We need to open up a new stage with the same type as the previous
                        new_stage = PaymentStage()
                        new_stage.__parent__ = payment
                        new_stage.method = method
                        new_stage.stage_owner = payment.owner.__name__
                        payment.history.append(new_stage)
                        # Send partial payment confirmation email
                        emailer = GenericEmail(self.request)
                        emailer.compose_and_send(
                            "Partial Ticket Payment Received",
                            """A payment of %s for your tickets with reference code %s has now been received on %s. Please remember to complete the remainder of your
                            payment (%s) in order for your tickets to the event to be confirmed.""" 
                            % (self.format_price(amount), payment.ref_code, transaction_date.strftime("%d/%m/%Y"), self.format_price(payment.amount_remaining)), 
                            payment.owner.__name__
                        )
                    logging.info("%s: Created a new payment stage for payment %s for user %s" % (self.user.username, payment.__name__, payment.owner.username))
                    self.request.session.flash("Payment entered successfully", "info")
                    return HTTPFound(location=self.request.route_path("admin_single_payment", ref_code=payment.__name__))
            except Exception:
                logging.exception("%s: An error occurred adding a payment stage to payment %s" % (self.user.username, payment.__name__))
                error = "An unknown error has occurred"
        return {
            "payment": payment,
            "date": datetime.now(),
            "active_stage": active_stage,
            "error": error
        }

    @view_config(
        route_name="admin_sales_export",
        context="ticketing.models.Ticketing",
        renderer="templates/payments_report.pt",
        permission="committee"
    )
    def sales_export_view(self):
        
        if "submit" in self.request.POST:
            # The export fields we go through
            field_names = {
                "payref":"Payment Reference", 
                "salutation":"Salutation", "fullname":"Fullname", "crsid":"CRSid", 
                "email":"Email", "phone_num":"Phone Number", "dob":"Date of Birth", 
                "college":"College", "grad":"Graduate Status", "tickets": "Number of Tickets",
                "total_cost":"Total Cost", "opened_date":"Opened Date", "pay_date": "Date Paid",
                "pay_complete":"Paid", "payment_method": "Payment Method"
            }
            field_order = [
                "payref", "salutation", "fullname", "crsid", "email",
                "phone_num", "dob", "college", "grad", "total_cost",
                "tickets", "opened_date", "pay_date", "pay_complete", "payment_method"
            ]
            # Form controls
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
            file += "Payment Status," + payment_status + "\n\n"
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
            # + For each of the filtered tickets print out the relevant data
            for payment in payments:
                data = []
                if "payref" in export_fields: 
                    if payment and payment.ref_code:
                        data.append(payment.ref_code)
                    else:
                        data.append("-")
                if "salutation" in export_fields: 
                    if payment.owner.profile and payment.owner.profile.title:
                        data.append(payment.owner.profile.title)
                    else:
                        data.append("-")
                if "fullname" in export_fields: 
                    if payment.owner.profile and payment.owner.profile.fullname:
                        data.append(payment.owner.profile.fullname)
                    else:
                        data.append("-")
                if "crsid" in export_fields: 
                    if payment.owner.profile and payment.owner.profile.crsid:
                        data.append(payment.owner.profile.crsid)
                    else:
                        data.append("-")
                if "email" in export_fields:  
                    if payment.owner.profile and payment.owner.profile.email:
                        data.append(payment.owner.profile.email)
                    else:
                        data.append("-")
                if "phone_num" in export_fields:  
                    if payment.owner.profile and payment.owner.profile.phone_number:
                        data.append("P "+payment.owner.profile.phone_number) # Append the P to force excel to treat as a string
                    else:
                        data.append("-")
                if "dob" in export_fields:  
                    if payment.owner.profile and payment.owner.profile.dob:
                        data.append(payment.owner.profile.dob.strftime("%d/%m/%Y"))
                    else:
                        data.append("-")
                if "college" in export_fields:  
                    if payment.owner.profile and payment.owner.profile.college:
                        data.append(payment.owner.profile.college)
                    else:
                        data.append("-")
                if "grad" in export_fields:  
                    if payment.owner.profile and payment.owner.profile.grad_status:
                        data.append(payment.owner.profile.grad_status)
                    else:
                        data.append("-")
                if "total_cost" in export_fields: data.append(str(payment.total / 100.00))
                if "tickets" in export_fields: data.append(str(len(payment.tickets)))
                if "opened_date" in export_fields: data.append(payment.opened_date.strftime("%d/%m/%Y"))
                if "pay_date" in export_fields: 
                    if payment.completed_date:
                        data.append(payment.completed_date.strftime("%d/%m/%Y"))
                    else:
                        data.append("-")
                if "pay_complete" in export_fields:
                    if payment.paid: data.append("Yes")
                    else: data.append("No")
                if "payment_method" in export_fields:
                    current_method = payment.current_method
                    methods = PROP_KEYS.getProperty(self.request, PROP_KEYS.PAYMENT_METHODS)
                    method = [a for a in methods if a.__name__ == current_method]
                    method = (method[0] if len(method) > 0 else None)
                    if method != None: data.append(method.name)
                    else: data.append("-")
                file += ",".join(data) + "\n"
            filename = "payments-report-%s.csv" % datetime.now().isoformat()
            return Response(
                body=file,
                status=200,
                content_type="text/csv",
                content_disposition="attachment; filename=\"%s\"" % filename,
            )
        return {}

    def due_date(self, due_date, window):
        #TODO: Need to make this a property
        return due_date + timedelta(days=window)
