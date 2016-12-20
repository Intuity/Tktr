from datetime import datetime
import stripe
import os
from pyramid.httpexceptions import HTTPFound
from pyramid.response import FileResponse, Response
from pyramid.security import forget
from pyramid.view import view_config

from ticketing.boxoffice.coding import Coding
from ticketing.boxoffice.issue import Issuer
from ticketing.boxoffice.models import Payment, PaymentStage
from ticketing.email.templates import GenericEmail
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import Ticketing, salt_password, PROP_KEYS
from ticketing.profile.models import UserProfile, PostalAddress
from ticketing.profile.process import ProcessAndValidate
from ticketing.boxoffice.download import TicketDownload

import logging
logging = logging.getLogger("ticketing")

class ProfileEditing(BaseLayout):

    @view_config(
        route_name="user_profile_edit",
        renderer="templates/user_profile.pt",
        context=Ticketing,
        permission="basic"
    )
    def edit_profile_view(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))
        # Check if the user is allowed to edit their profile
        if self.account_lock_down:
            self.request.session.flash("Account details have been locked down, therefore editing is disabled.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))

        user = self.user
        if user.profile == None:
            user.profile = UserProfile()
            user.profile.__parent__ = user
        profile = user.profile
        # Grab the address
        lineone = linetwo = city = county = country = postal_code = None
        address = profile.address
        if address != None:
            lineone = address.line_one
            linetwo = address.line_two
            city = address.city
            county = address.county
            country = address.country
            postal_code = address.postal_code
        # Sort out DOB
        dob_year = dob_month = dob_day = None
        if profile.dob != None:
            dob_year = profile.dob.year
            dob_month = profile.dob.month
            dob_day = profile.dob.day
        # Process into the profile
        return {
            "title": profile.title,
            "othertitle": (profile.title not in ["Mr", "Mrs", "Miss", "Ms", "Dr", "Prof", "Rev"] and len(profile.title) > 0),
            "forename": profile.forename,
            "surname": profile.surname,
            "email": profile.email,
            "phone_number": profile.phone_number,
            "dob_year": dob_year,
            "dob_month": dob_month,
            "dob_day": dob_day,
            "crsid": profile.crsid,
            "college": profile.college,
            "grad_status": profile.grad_status,
            # Address stuff
            "lineone": lineone,
            "linetwo": linetwo,
            "city": city,
            "county": county,
            "country": country,
            "postal_code": postal_code,
        }
        

    @view_config(
        route_name="user_profile_edit",
        renderer="templates/user_profile.pt",
        context=Ticketing,
        permission="basic",
        request_method="POST"
    )
    def edit_profile_view_do(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))
        # Check if the user is allowed to edit their profile
        if self.account_lock_down:
            self.request.session.flash("Account details have been locked down, therefore editing is disabled.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))

        user = self.user
        if user.profile == None:
            user.profile = UserProfile()
            user.profile.__parent__ = user
        if not user.profile.raven_user and user.profile.address == None:
            user.profile.address = PostalAddress()
            user.profile.address.__parent__ = user.profile
        profile = user.profile
        # Ok - process the form and validate all details
        processor = ProcessAndValidate(
                        self.request.POST, 
                        self.request.registry._settings["base_dir"],
                        PROP_KEYS.getProperty(self.request, PROP_KEYS.MINIMUM_AGE),
                        PROP_KEYS.getProperty(self.request, PROP_KEYS.EVENT_DATE),
                        profile=profile, 
                        photo_required=PROP_KEYS.getProperty(self.request, PROP_KEYS.PHOTO_REQUIRED))
        try:
            data = processor.process()
            # Save profile details
            profile.title = data["title"]
            profile.forename = data["forename"]
            profile.surname = data["surname"]
            if not profile.raven_user:
                profile.email = data["email"]
                profile.crsid = data["crsid"]
            profile.phone_number = data["phone_number"]
            profile.photo_file = data["photofile"]
            profile.dob = data["dob"]
            profile.college = data["college"]
            profile.grad_status = data["grad_status"]
            if profile.address != None:
                profile.address.line_one = self.request.POST["lineone"]
                if len(profile.address.line_one) < 4:
                    raise ValueError("You must provide a full and valid address.")
                profile.address.line_two = self.request.POST["linetwo"]
                profile.address.city = self.request.POST["city"]
                if len(profile.address.city) < 2:
                    raise ValueError("You must enter a town or city.")
                profile.address.county = self.request.POST["county"]
                if not "country" in self.request.POST or len(self.request.POST["country"]) < 4:
                    raise ValueError("You must select a country of residence.")
                profile.address.country = self.request.POST["country"]
                profile.address.postal_code = self.request.POST["postal_code"]
                if len(profile.address.postal_code) < 4:
                    raise ValueError("You must provide a postal or zip code.")
            profile._p_changed = True
        except ValueError, e:
            logging.error("%s: Received a value error when processing profile: %s" % (self.user.username, e))
            message = str(e)
            self.request.session.flash(message, "error")
            title = self.request.POST["title"]
            if title == "Other":
                title = self.request.POST["othertitle"]
            forename = self.request.POST["forename"]
            surname = self.request.POST["surname"]
            email = None
            phone_number = self.request.POST["phone_number"]
            dob_year = self.request.POST["dob_year"]
            dob_month = self.request.POST["dob_month"]
            dob_day = self.request.POST["dob_day"]
            crsid = None
            college = None
            grad_status = None
            lineone = linetwo = city = county = country = postal_code = None
            if not profile.raven_user:
                email = self.request.POST["email"]
                # If not a raven user then fill in postal details
                if profile.address != None:
                    lineone = self.request.POST["lineone"]
                    linetwo = self.request.POST["linetwo"]
                    city = self.request.POST["city"]
                    county = self.request.POST["county"]
                    if "country" in self.request.POST:
                        country = self.request.POST["country"]
                    postal_code = self.request.POST["postal_code"]
            else:
                email = profile.crsid.replace(" ","") + "@cam.ac.uk"
                crsid = profile.crsid
                college = self.request.POST["college"]
                grad_status = self.request.POST["grad_status"]
            return {
                "title": title,
                "othertitle": (title not in ["Mr", "Mrs", "Miss", "Ms", "Dr", "Prof", "Rev"] and len(title) > 0),
                "forename": forename,
                "surname": surname,
                "email": email,
                "phone_number": phone_number,
                "dob_year": dob_year,
                "dob_month": dob_month,
                "dob_day": dob_day,
                "crsid": crsid,
                "college": college,
                "grad_status": grad_status,
                # Address stuff
                "lineone": lineone,
                "linetwo": linetwo,
                "city": city,
                "county": county,
                "country": country,
                "postal_code": postal_code,
            }
        # Select appropriate routing henceforth
        if len([x for x in user.tickets if x.payment != None]) > 0:
            return HTTPFound(location=self.request.route_path("user_profile"))
        else:
            return HTTPFound(location=self.request.route_path("buy_tickets"))

    @view_config(route_name="user_profile", renderer="templates/profile.pt", context=Ticketing, permission="basic")
    def profile_view(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))
        # Check we have a complete profile
        if not self.user_details_complete:
            self.request.session.flash("Some details of your profile appear to be incomplete, please correct these.", "info")
            return HTTPFound(location=self.request.route_path("user_profile_edit"))

        # Proceed
        user = self.user
        profile = user.profile

        # Make sure all of our unpurchased tickets have been returned
        issue = Issuer(self.request.root)
        try:
            issue.returnUnpurchasedTickets(user.__name__)
        except Exception:
            self.request.session.flash("Had an issue returning unpurchased tickets, please try again.", "error")

        return {"user": user, "profile": profile,}

    @view_config(
        route_name="user_password",
        context=Ticketing,
        permission="basic",
        renderer="templates/set_password.pt"
    )
    def set_password_view(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))
        # Check this user is allowed to set/change a password
        if self.user.profile == None:
            self.request.session.flash("You are not able to change your password as you haven't yet set up your profile", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        elif self.user.profile.raven_user:
            self.request.session.flash("You are not able to set a password as you are authenticated via Raven. Please change your password with the Raven service.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Ok all good, deal with any posted data
        if "submit" in self.request.POST:
            password_one = self.request.POST["password_one"]
            password_two = self.request.POST["password_two"]
            if password_one != password_two:
                self.request.session.flash("You have not entered the same password twice, please try again.", "error")
                return {}
            elif len(password_one) < 6:
                self.request.session.flash("For security reasons you must enter a password of 6 letters or more.", "error")
                return {}
            # Generate a new salt, salt the password and store it
            self.user.password_salt = Coding().generateUniqueCode(withdash=False)
            self.user.password = salt_password(password_one, self.user.password_salt)
            self.request.session.flash("Your password has been successfully changed.", "info")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Otherwise just pass to renderer
        return {}

    @view_config(route_name="user_profile_photo", context=Ticketing, permission="basic")
    @view_config(route_name="guest_profile_photo", context=Ticketing, permission="basic")
    def photo_view(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))
        base_path = self.request.registry._settings["base_dir"]
        if "tick_id" in self.request.matchdict:
            tick_id = self.request.matchdict["tick_id"]
            ticket = None
            # Find ticket
            for tick in self.user.tickets:
                if tick.__name__ == tick_id:
                    ticket = tick
                    break
            # Safety
            if ticket == None:
                return FileResponse(os.path.join(base_path, "data/profile_images", "blank.png"), request=self.request)
            else:
                file_name = ticket.guest_info.photo_file
                if os.path.isfile(os.path.join(base_path, "data/profile_images", file_name)):
                    return FileResponse(os.path.join(base_path, "data/profile_images", file_name), request=self.request)
                else:
                    return FileResponse(os.path.join(base_path, "data/profile_images", "blank.png"), request=self.request)
        else:
            file_name = self.user.profile.photo_file
            if os.path.isfile(os.path.join(base_path, "data/profile_images", file_name)):
                return FileResponse(os.path.join(base_path, "data/profile_images", file_name), request=self.request)
            else:
                return FileResponse(os.path.join(base_path, "data/profile_images", "blank.png"), request=self.request)

    @view_config(
        route_name="ticket_details",
        context=Ticketing,
        permission="basic",
        renderer="templates/details.pt"
    )
    def ticket_details_view(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))

        tick_id = self.request.matchdict["tick_id"]
        ticket = None
        # Find ticket
        for tick in self.user.tickets:
            if tick.__name__ == tick_id:
                ticket = tick
                break
        # Safety
        if ticket == None:
            self.request.session.flash("Ticket does not exist.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        return {
            "ticket": ticket
        }

    @view_config(
        route_name="ticket_payment_history",
        context=Ticketing,
        permission="basic",
        renderer="templates/payment_history.pt"
    )
    def ticket_payment_history_view(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))

        tick_id = self.request.matchdict["tick_id"]
        ticket = None
        # Find ticket
        for tick in self.user.tickets:
            if tick.__name__ == tick_id:
                ticket = tick
                break
        # Safety
        if ticket == None:
            self.request.session.flash("Ticket does not exist.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        return {
            "ticket": ticket
        }

    @view_config(
        route_name="ticket_download",
        context=Ticketing,
        permission="basic",
        renderer="templates/download.pt"
    )
    def ticket_download_view(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))
        elif not self.ticket_download_enabled:
            self.request.session.flash("Ticket download is currently not enabled.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))

        tick_id = self.request.matchdict["tick_id"]
        ticket = None
        # Find ticket
        for tick in self.user.tickets:
            if tick.__name__ == tick_id:
                ticket = tick
                break
        # Safety
        if ticket == None:
            self.request.session.flash("Ticket does not exist.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        return {
            "ticket": ticket
        }
    
    @view_config(
        route_name="ticket_download_payment_method",
        context=Ticketing,
        permission="basic"
    )
    @view_config(
        route_name="ticket_download_all_method",
        context=Ticketing,
        permission="basic"
    )    
    @view_config(
        route_name="ticket_download_method",
        context=Ticketing,
        permission="basic"
    )
    def ticket_download_method_view(self):
        method = self.request.matchdict["method"].lower()
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))
        elif not self.ticket_download_enabled:
            self.request.session.flash("Ticket download is currently not enabled.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        elif method not in ["pdf"]:
            self.request.session.flash("Ticket download method does not exist.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        
        if method == "pdf":
            pdf = None
            if "tick_id" in self.request.matchdict:
                tick_id = self.request.matchdict["tick_id"]
                ticket = None
                # Find ticket
                for tick in self.user.tickets:
                    if tick.__name__ == tick_id:
                        ticket = tick
                        break
                # Safety
                if ticket == None:
                    self.request.session.flash("Ticket does not exist.", "error")
                    return HTTPFound(location=self.request.route_path("user_profile"))
                # Prep the PDF
                pdf = TicketDownload(self.request).single_ticket_pdf(ticket)
            elif "payment_id" in self.request.matchdict:
                payments = [a for a in self.user.payments if a.__name__ == self.request.matchdict["payment_id"]]
                if len(payments) != 1:
                    self.request.session.flash("Payment does not exist.", "error")
                    return HTTPFound(location=self.request.route_path("user_profile"))
                pdf = TicketDownload(self.request).payment_tickets_pdf(payments[0])
            else:
                pdf = TicketDownload(self.request).user_tickets_pdf(self.user)
            
            resp = Response(
                content_type="application/pdf",
                content_encoding="binary",
                content_length=len(pdf),
                body=pdf
            )
            return resp

    @view_config(
        route_name="transfer_ticket",
        context=Ticketing,
        permission="basic",
        renderer="templates/transfer.pt"
    )
    def transfer_ticket_view(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))
        # Process
        tick_id = self.request.matchdict["tick_id"]
        ticket = None
        # Find ticket
        for tick in self.user.tickets:
            if tick.__name__ == tick_id:
                ticket = tick
                break
        # Safety
        if ticket == None:
            self.request.session.flash("Ticket does not exist.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Check that ticket is paid for
        elif not ticket.payment.paid:
            self.request.session.flash("The payment has not been completed for this ticket, therefore you cannot transfer it.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Also check that if they are exchanging their own ticket that they don't have guests
        elif ticket.guest_info == ticket.owner.profile and len(self.user.tickets) > 1:
            self.request.session.flash("You may not exchange your own ticket while you still have guest tickets.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Check whether ticket is locked down
        locked_down = ticket.tick_type.locked_down
        if not locked_down: # Check all addons as well
            for addon in ticket.addons.values():
                if addon.locked_down:
                    locked_down = True
                    break
        if locked_down:
            self.request.session.flash("This ticket has been locked down, therefore transfer is disabled.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Respond to form
        if "submit" in self.request.POST:
            if not "username" in self.request.POST:
                self.request.session.flash("You must enter a username to transfer the ticket to!", "error")
            elif not self.request.POST["username"].lower() in self.request.root.users or self.request.POST["username"].lower() == self.user.__name__:
                self.request.session.flash("You must enter a valid username (someone with an account) to transfer the ticket to!", "error")
            else:
                self.request.session["transfer_to"] = self.request.POST["username"].lower()
                return HTTPFound(location=self.request.route_path("transfer_ticket_pay", tick_id=tick_id))
        return {
            "ticket": ticket
        }

    @view_config(
        route_name="transfer_ticket_pay",
        context=Ticketing,
        permission="basic",
        renderer="templates/transfer_payment.pt"
    )
    def transfer_ticket_payment_view(self):
        # Check agreements
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif not self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))

        tick_id = self.request.matchdict["tick_id"]
        ticket = None
        # Find ticket
        for tick in self.user.tickets:
            if tick.__name__ == tick_id:
                ticket = tick
                break
        # Safety
        if ticket == None:
            self.request.session.flash("Ticket does not exist.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Check that ticket is paid for
        elif not ticket.payment.paid:
            self.request.session.flash("The payment has not been completed for this ticket, therefore you cannot transfer it.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Also check that if they are exchanging their own ticket that they don't have guests
        elif ticket.guest_info == ticket.owner.profile and len(self.user.tickets) > 1:
            self.request.session.flash("You may not exchange your own ticket while you still have guest tickets.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Now check we have received a valid posted username
        if not "transfer_to" in self.request.session:
            self.request.session.flash("You must enter a username to transfer the ticket to!", "error")
            return HTTPFound(location=self.request.route_path("transfer_ticket", tick_id=tick_id))
        elif not self.request.session["transfer_to"].lower() in self.request.root.users or self.request.session["transfer_to"].lower() == self.user.__name__:
            self.request.session.flash("You must enter a valid username (someone with an account) to transfer the ticket to!", "error")
            return HTTPFound(location=self.request.route_path("transfer_ticket", tick_id=tick_id))
        recipient = self.request.session["transfer_to"].lower()
        # OK, now if we have a payment deal with it
        if "stripeToken" in self.request.POST:
            # Double check the username
            username = self.request.POST["username"].lower().replace(" ","")
            if len(username) <= 2:
                self.request.session.flash("You must enter a valid username to transfer the ticket to. You have not been charged.", "error")
                return HTTPFound(location=self.request.route_path("transfer_ticket", tick_id=tick_id))
            if not username in self.request.root.users:
                self.request.session.flash("The username \"%s\" does not exist within the system, please check again. You have not been charged." % username, "error")
                return HTTPFound(location=self.request.route_path("transfer_ticket", tick_id=tick_id))
            elif self.request.root.users[username].profile == None or not self.request.root.users[username].profile.complete:
                self.request.session.flash("The username \"%s\" does not have a complete profile, please complete it before transferring. You have not been charged." % username, "error")
                return HTTPFound(location=self.request.route_path("transfer_ticket", tick_id=tick_id))
            # Run Stripe payment to authorise
            organisation_name = self.get_payment_method('stripe').settings[PROP_KEYS.ORGANISATION_NAME].value
            transfer_fee = PROP_KEYS.getProperty(self.request, PROP_KEYS.TRANSFER_FEE)
            token = self.request.POST["stripeToken"]
            stripe.api_key = self.get_payment_method('stripe').settings[PROP_KEYS.STRIPE_API_KEY].value
            charge = None
            error = None
            try:
                charge = stripe.Charge.create(
                    amount=transfer_fee,
                    currency="gbp",
                    source=token,
                    description=organisation_name,
                )
                if "paid" in charge and charge["paid"] == True:
                    # Ok, now exchange
                    new_user = self.request.root.users[username]
                    payment = ticket.payment
                    old_user = ticket.owner
                    
                    # Open a new payment for the new owner, deduct the value of money associated
                    # with this ticket from the original payment and add it to this payment, then
                    # open a transfer payment stage and move the ticket across. If the original payment
                    # was gifted then need to treat specially
                    
                    new_payment = Payment()
                    new_payment.__parent__ = new_user
                    new_payment.owner = new_user
                    
                    # Find out if it was gifted
                    gifted = (len([x for x in payment.history if x.method == "gifted"]) > 0)
                    
                    # Open the finance stage
                    finance_stage = PaymentStage()
                    finance_stage.__parent__ = new_payment
                    finance_stage.completed = finance_stage.received = finance_stage.cashed = True
                    finance_stage.stage_owner = old_user.__name__
                    finance_stage.date = datetime.now()
                    if gifted:
                        finance_stage.method = "gifted"
                    else:
                        finance_stage.method = "banktransfer"
                    finance_stage.amount_paid = ticket.total_cost
                    new_payment.history.append(finance_stage)
                    
                    # Open the ticket transfer stage
                    transfer_stage = PaymentStage()
                    transfer_stage.__parent__ = new_payment
                    transfer_stage.method_properties["last_four"] = charge["source"]["last4"]
                    transfer_stage.method_properties["ref_code"] = charge["id"]
                    transfer_stage.amount_paid = transfer_fee
                    transfer_stage.processing_charge = transfer_fee
                    transfer_stage.completed = transfer_stage.received = transfer_stage.cashed = True
                    transfer_stage.stage_owner = new_user.__name__
                    transfer_stage.date = datetime.now()
                    transfer_stage.method = "stripe"
                    transfer_stage.transfer = True
                    new_payment.history.append(transfer_stage)
                    
                    # Open the outgoing ticket transfer stage for the original owner
                    out_trans_stage = PaymentStage()
                    out_trans_stage.__parent__ = payment
                    if not gifted:
                        out_trans_stage.amount_paid = -ticket.total_cost # To make sure books balance!
                    out_trans_stage.completed = out_trans_stage.received = out_trans_stage.cashed = True
                    out_trans_stage.stage_owner = new_user.__name__
                    out_trans_stage.date = datetime.now()
                    out_trans_stage.method = "stripe"
                    out_trans_stage.method_properties["last_four"] = charge["source"]["last4"]
                    out_trans_stage.method_properties["ref_code"] = charge["id"]
                    out_trans_stage.transfer = True
                    payment.history.append(out_trans_stage)
                    
                    # Mark new payment as having been completed today
                    new_payment.completed_date = datetime.now()

                    # Move the ticket over to the new payment
                    new_payment.tickets.append(ticket)
                    payment.tickets.remove(ticket)
                    
                    # Move the ticket over to the new user (different to above)
                    new_user.tickets.append(ticket)
                    new_user.total_tickets += 1 # We increment, but don't decrement (stop scalpers)
                    old_user.tickets.remove(ticket)
                    ticket.__parent__ = new_user
                    ticket.payment = new_payment
                    ticket.owner = new_user
                    
                    # Register payment
                    new_user.payments.append(new_payment)
                    self.request.root.payments[new_payment.__name__] = new_payment
                    
                    # If the receiver only has one ticket, then make this their main ticket
                    if len(new_user.tickets) == 1:
                        ticket.guest_info = new_user.profile
                    # Else gift one free guest detail alteration and clear existing details
                    else:
                        ticket.guest_info = None
                        ticket.change_enabled = True
                        
                    # Transfer complete - notify
                    GenericEmail(self.request).compose_and_send(
                        "Ticket Transfer Complete",
                        "The ticket %s has been successfully transferred to %s. If you did not request this change, please get in touch with us by email or phone (details at the bottom of this message)."
                        % (ticket.__name__, new_user.profile.fullname),
                        old_user.__name__
                    )
                    GenericEmail(self.request).compose_and_send(
                        "Ticket Transfer from %s" % old_user.profile.fullname,
                        "You have been transferred a ticket (%s) from %s. If you think this is a mistake, please get in touch with us by email or phone (details at the bottom of this message)."
                        % (ticket.__name__, old_user.profile.fullname),
                        new_user.__name__
                    )
                    self.request.session.flash("Ticket transfer successful!", "info")
                    return HTTPFound(location=self.request.route_path("user_profile"))
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
                logging.error(self.user.username + ": Exception thrown in Stripe ticket transfer payment: %s" % e)
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
                "error":        error,
                "ticket":       ticket,
                "recipient":    recipient,
                "penny_total":  self.transfer_fee
            }
        return {
            "ticket": ticket,
            "recipient": recipient,
            "penny_total": self.transfer_fee
        }

    @view_config(
        route_name="purchase_agreement_act",
        context=Ticketing,
        permission="basic",
        renderer="templates/purchase_agreement.pt"
    )
    def purchase_agreement_view(self):
        if self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("privacy_policy_act"))
        agreement_doc = PROP_KEYS.getProperty(self.request, PROP_KEYS.PURCHASE_AGREEMENT)
        if "submit" in self.request.POST:
            # Verify the checkbox is checked
            chk_response = ("agreement" in self.request.POST and self.request.POST["agreement"] == "agreed")
            if chk_response:
                self.user.purchase_agreement = True
                return HTTPFound(location=self.request.route_path("privacy_policy_act"))
            else:
                self.request.session.flash("The form was submitted without you accepting the purchase agreement. Please first accept the agreement and then click submit.", "error")
        return {
            "document": agreement_doc
        }

    @view_config(
        route_name="privacy_policy_act",
        context=Ticketing,
        permission="basic",
        renderer="templates/privacy_policy.pt"
    )
    def privacy_policy_view(self):
        if not self.user.purchase_agreement:
            return HTTPFound(location=self.request.route_path("purchase_agreement_act"))
        elif self.user.privacy_agreement:
            return HTTPFound(location=self.request.route_path("user_profile"))
        agreement_doc = PROP_KEYS.getProperty(self.request, PROP_KEYS.PRIVACY_POLICY)
        if "submit" in self.request.POST:
            # Verify the checkbox is checked
            chk_response = ("agreement" in self.request.POST and self.request.POST["agreement"] == "agreed")
            if chk_response:
                self.user.privacy_agreement = True
                return HTTPFound(location=self.request.route_path("user_profile"))
            else:
                self.request.session.flash("The form was submitted without you accepting the privacy policy. Please first accept the agreement and then click submit.", "error")
        return {
            "document": agreement_doc
        }

    @view_config(
        route_name="refused_agreement",
        context=Ticketing,
        permission="basic"
    )
    def refuse_agreement_view(self):
        # Strip out the user from the system and log them out
        self.user.__parent__.members.remove(self.user)
        user_id = self.user.__name__
        self.request.root.users.pop(user_id, None)
        # Flash cleared message
        self.request.session.flash("As you refused the agreement, your account details have now been removed and you have been logged out.", "info")
        # Logout
        header = forget(self.request)
        self.request.session.pop("user_id", None)
        self.request.session.pop("active_id", None)
        self.request.session.pop("payment_id", None)
        return HTTPFound(location=self.request.route_path("welcome"), headers=header)
