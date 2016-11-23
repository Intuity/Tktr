from datetime import timedelta
from .mail import Mail
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import PROP_KEYS
from ticketing.boxoffice.download import TicketDownload

import logging
logging = logging.getLogger("ticketing") 

class BaseEmail(object):

    def __init__(self, request):
        self.request = request

class PurchaseConfirmationEmail(BaseEmail):

    def compose_and_send(self, purchase_id):
        if not purchase_id in self.request.root.payments:
            logging.error("Composing purchase confirmation email, purchase ID %s does not exist" % purchase_id)
            return False
        payment = self.request.root.payments[purchase_id]
        if not payment.owner.profile or not payment.owner.profile.email:
            logging.error("Composing purchase confirmation email, profile does not exist or email missing for payment %s" % purchase_id)
            return False
        paid = "No"
        if payment.paid: paid = "Yes"
        table_data = ""
        plain_tickets = ""
        base = BaseLayout(None, None)
        # Run through tickets
        for ticket in payment.tickets:
            price = base.format_price(ticket.total_cost) # Total cost takes into account the add-ons
            addon_str = ""
            plain_addon_str = ""
            if ticket.addons != None and len(ticket.addons) > 0:
                for addon in ticket.addons.values():
                    addon_str += addon.name + "<br />"
                    plain_addon_str += addon.name + ", "
            else:
                addon_str = "No Addons"
                plain_addon_str = "No Addons"
            if ticket.guest_info != None:
                table_data += "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (ticket.tick_type.name, addon_str, ticket.guest_info.fullname, price)
                plain_tickets += "%s (%s - total: %s) : %s\n" % (ticket.tick_type.name, plain_addon_str, price, ticket.guest_info.fullname)
            else:
                table_data += "<tr><td>%s</td><td>%s</td><td>-</td><td>%s</td></tr>" % (ticket.tick_type.name, addon_str, price)
                plain_tickets += "%s (%s - total: %s)\n" % (ticket.tick_type.name, plain_addon_str, price)
        # Composing
        payment_window = PROP_KEYS.getProperty(self.request, PROP_KEYS.PAYMENT_WINDOW)
        methods = PROP_KEYS.getProperty(self.request, PROP_KEYS.PAYMENT_METHODS)
        method = [x for x in methods if x.__name__.lower() == payment.current_method]
        method_name = "Unknown"
        if len(method) > 0:
            method = method[0]
            method_name = method.short_name
        else:
            method = None
        data = {
            "EVENTNAME": PROP_KEYS.getProperty(self.request, PROP_KEYS.EVENT_NAME),
            "NAME": (payment.owner.profile.fullname if payment.owner.profile and payment.owner.profile.fullname else "-"),
            "REFERENCE": payment.ref_code,
            "DATE": payment.opened_date.strftime("%d/%m/%Y at %H:%M"),
            "METHOD": method_name,
            "PAID": paid,
            "COUNT": str(len(payment.tickets)),
            "TOTAL": base.format_price(payment.total),
            "PROCESSING": base.format_price(payment.processing),
            "TICKETS": table_data,
            "PLAINTICKETS": plain_tickets,
            "DUEDATE": (payment.opened_date + timedelta(days=payment_window)).strftime("%d/%m/%Y"),
            "TICKETINSTRUCTIONS": ""
        }
        if PROP_KEYS.getProperty(self.request, PROP_KEYS.TICKET_DOWNLOAD_ENABLED):
            data["TICKETINSTRUCTIONS"] = "Your tickets are attached to this email as a PDF, please print them out and present them when you arrive at the event."
        # Prepare from template
        mailer = Mail(self.request)
        message = mailer.compose_from_template("confirmation", data)
        # If necessary attach a PDF with the tickets in
        if PROP_KEYS.getProperty(self.request, PROP_KEYS.TICKET_DOWNLOAD_ENABLED):
            pdf = TicketDownload(self.request).payment_tickets_pdf(payment)
            return mailer.send_email(payment.owner.__name__, "Order Confirmation", message, pdf_attachment=pdf)
        else:
            return mailer.send_email(payment.owner.__name__, "Order Confirmation", message)

class PurchaseAlterationEmail(BaseEmail):

    def compose_and_send(self, purchase_id):
        if not purchase_id in self.request.root.payments: return False
        payment = self.request.root.payments[purchase_id]
        if not payment.owner.profile or not payment.owner.profile.email:
            logging.error("Composing purchase alteration email, profile does not exist or email missing for payment %s" % purchase_id)
            return False
        paid = "No"
        if payment.paid: paid = "Yes"
        table_data = ""
        plain_tickets = ""
        base = BaseLayout(None, None)
        # Run through tickets
        for ticket in payment.tickets:
            price = base.format_price(ticket.total_cost) # Total cost takes into account the add-ons
            addon_str = ""
            plain_addon_str = ""
            if ticket.addons != None and len(ticket.addons) > 0:
                for addon in ticket.addons.values():
                    addon_str += addon.name + "<br />"
                    plain_addon_str += addon.name + ", "
            else:
                addon_str = "No Addons"
                plain_addon_str = "No Addons"
            if ticket.guest_info != None:
                table_data += "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (ticket.tick_type.name, addon_str, ticket.guest_info.fullname, price)
                plain_tickets += "%s (%s - total: %s) : %s\n" % (ticket.tick_type.name, plain_addon_str, price, ticket.guest_info.fullname)
            else:
                table_data += "<tr><td>%s</td><td>%s</td><td>-</td><td>%s</td></tr>" % (ticket.tick_type.name, addon_str, price)
                plain_tickets += "%s (%s - total: %s)\n" % (ticket.tick_type.name, plain_addon_str, price)
        # Composing
        payment_window = PROP_KEYS.getProperty(self.request, PROP_KEYS.PAYMENT_WINDOW)
        methods = PROP_KEYS.getProperty(self.request, PROP_KEYS.PAYMENT_METHODS)
        method = [x for x in methods if x.__name__.lower() == payment.current_method]
        method_name = "Unknown"
        if len(method) > 0:
            method = method[0]
            method_name = method.short_name
        else:
            method = None
        data = {
            "EVENTNAME": PROP_KEYS.getProperty(self.request, PROP_KEYS.EVENT_NAME),
            "NAME": (payment.owner.profile.fullname if payment.owner.profile and payment.owner.profile.fullname else "-"),
            "REFERENCE": payment.ref_code,
            "DATE": payment.opened_date.strftime("%d/%m/%Y at %H:%M"),
            "METHOD": method_name,
            "PAID": paid,
            "COUNT": str(len(payment.tickets)),
            "TOTAL": base.format_price(payment.total),
            "PROCESSING": base.format_price(payment.processing),
            "TICKETS": table_data,
            "PLAINTICKETS": plain_tickets,
            "DUEDATE": (payment.opened_date + timedelta(days=payment_window)).strftime("%d/%m/%Y")
        }
        # Send
        mailer = Mail(self.request)
        message = mailer.compose_from_template("alter_payment", data)
        return mailer.send_email(payment.owner.__name__, "Payment Alteration", message)

class GenericEmail(BaseEmail):

    def compose_and_send(self, subject, raw_message, user_id, pdf_attachment=None):
        if not user_id in self.request.root.users: return False
        user = self.request.root.users[user_id]
        data = {
            "EVENTNAME": PROP_KEYS.getProperty(self.request, PROP_KEYS.EVENT_NAME),
            "NAME": (user.profile.fullname if user.profile and user.profile.fullname else "-"),
            "MESSAGE": raw_message
        }
        # Send
        mailer = Mail(self.request)
        message = mailer.compose_from_template("generic", data)
        return mailer.send_email(user_id, subject, message, pdf_attachment=pdf_attachment)
