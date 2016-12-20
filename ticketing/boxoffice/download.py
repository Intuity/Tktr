# -*- coding: utf-8 -*- 

import fpdf
import qrcode
import os
import locale
from ticketing.models import PROP_KEYS
from datetime import datetime

class TicketDownload(object):
    request = None
    
    def __init__(self, request):
        self.request = request

    def single_ticket_pdf(self, ticket):
        pdf = self.setup_pdf()
        self.add_ticket_to_pdf(pdf, ticket, 0)
        return pdf.output(name="",dest="S")

    def payment_tickets_pdf(self, payment):
        pdf = self.setup_pdf()
        ticket_count = 0
        for ticket in payment.tickets:
            self.add_ticket_to_pdf(pdf, ticket, (ticket_count % 3))
            ticket_count += 1
            if (ticket_count % 3) == 0 and len(payment.tickets) > ticket_count:
                self.add_pdf_page(pdf)
        return pdf.output(name="",dest="S")

    def user_tickets_pdf(self, user):
        pdf = self.setup_pdf()
        ticket_count = 0
        for ticket in user.tickets:
            self.add_ticket_to_pdf(pdf, ticket, (ticket_count % 3))
            ticket_count += 1
            if (ticket_count % 3) == 0 and len(user.tickets) > ticket_count:
                self.add_pdf_page(pdf)
        return pdf.output(name="",dest="S")

    def setup_pdf(self):
        pdf = fpdf.FPDF()
        self.add_pdf_page(pdf)
        return pdf
    
    def add_pdf_page(self, pdf):
        pdf.add_page()
        pdf.set_fill_color(255,255,255)
        pdf.rect(0,0,210,297,'F')
        pdf.set_font('Arial', '', 12)
        pdf.set_text_color(150, 150, 150)
        pdf.text(2, 5, self.event_name + ", Produced on " + datetime.now().strftime('%A %d %B %Y'))

    def add_ticket_to_pdf(self, pdf, ticket, offset=0):
        if offset < 10:
            offset = offset * 75
        # Generate and save the QR code temporarily
        tmp_path = self.request.registry._settings["base_dir"] + "/data/tmp/"
        qr_img = qrcode.make("id:" + ticket.__name__ + ":pay:" + ticket.payment.__name__ + ":owner:" + ticket.owner.profile.fullname + ":price:" + str(ticket.tick_type.cost) + ":type:" + ticket.tick_type.name)
        qr_tmp_path = tmp_path + ticket.__name__ + ".png"
        qr_img.save(qr_tmp_path, "PNG")
        
        # Draw a ticket background if it exists
        bg_path = self.request.registry._settings["base_dir"] + "/data/ticket_backer.png"
        if os.path.isfile(bg_path):
            pdf.image(bg_path, x=10, y=10 + offset, w=190, h=70, type='PNG')
        
        # Draw the QR Code
        pdf.image(qr_tmp_path, x=12, y=12 + offset, w=66, h=66, type='PNG')
        
        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(0,0,0)
        title = self.event_name
        if len(title) > 30:
            title = title[:30] + "..."
        pdf.text(x=80, y=23 + offset, txt=title)
        pdf.set_font('Arial', 'I', 13)
        pdf.text(x=80, y=30 + offset, txt=PROP_KEYS.getProperty(self.request, PROP_KEYS.EVENT_DATE).strftime('%A %d %B %Y'))
        pdf.set_font('Arial', '', 16)
        pdf.text(x=80, y=37 + offset, txt=ticket.guest_info.fullname)
        pdf.text(x=80, y=44 + offset, txt=ticket.tick_type.name)
        pdf.text(x=80, y=52 + offset, txt=self.format_price(ticket.tick_type.cost))
        pdf.set_font('Arial', '', 16)
        pdf.set_text_color(150,150,150)
        pdf.text(x=80, y=60 + offset, txt="Ticket ID: " + ticket.__name__)
        pdf.text(x=80, y=68 + offset, txt="Payment ID:" + ticket.payment.__name__)
        
        # Draw the ticket box outline
        pdf.set_draw_color(100, 100, 100)
        pdf.set_line_width(0.1)
        pdf.rect(10, 10 + offset, 190, 70)

    @property
    def event_name(self):
        return PROP_KEYS.getProperty(self.request, PROP_KEYS.EVENT_NAME)

    def format_price(self, price, symbol=True):
        locale.setlocale(locale.LC_ALL, "en_GB")
        pricetext = None
        if symbol:
            pricetext = locale.currency((price/100.0))
        else:
            pricetext = locale.currency((price/100.0)).replace("\xa3","")
        # Return the price formatted
        decoded = None
        try:
            decoded = pricetext.decode("utf-8")
        except Exception:
            decoded = pricetext.decode("latin-1")
        return decoded

