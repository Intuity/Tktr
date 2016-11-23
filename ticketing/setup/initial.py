from datetime import datetime
from persistent.mapping import PersistentMapping
from persistent.list import PersistentList
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from ticketing.boxoffice.coding import Coding
from ticketing.boxoffice.models import PaymentMethod, PaymentProperty
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import User, Group, Document
from ticketing.models import PROP_KEYS as PROP
from ticketing.models import salt_password
from ticketing.profile.models import UserProfile, PostalAddress


class Initial(BaseLayout):

    @view_config(
        route_name="setup",
        context="ticketing.models.Ticketing",
        renderer="templates/setup.pt"
    )
    def start_setup_view(self):
        if "properties" in self.request.root.__dict__ and (PROP.getProperty(self.request, PROP.SITE_SETUP) == True):
            return HTTPFound(location=self.request.route_path("welcome"))
        return {}

    @view_config(
        route_name="setup_stageone",
        context="ticketing.models.Ticketing",
        renderer="templates/stageone.pt"
    )
    def setup_one_view(self):
        if (PROP.getProperty(self.request, PROP.SITE_SETUP) == True):
            return HTTPFound(location=self.request.route_path("welcome"))
        
        setup = False
        if (PROP.getProperty(self.request, PROP.VERSION) != None):
            print "Database already setup!"
        else:
            # Setup the database
            self.db_run_setup(self.request.root)
            setup = True
        
        return {
            "setup": setup
        }

    @view_config(
        route_name="setup_stagetwo",
        context="ticketing.models.Ticketing",
        renderer="templates/stagetwo.pt"
    )
    def setup_two_view(self):
        if (PROP.getProperty(self.request, PROP.SITE_SETUP) == True):
            return HTTPFound(location=self.request.route_path("welcome"))
        elif (PROP.getProperty(self.request, PROP.VERSION) == None):
            return HTTPFound(location=self.request.route_path("setup_stageone"))
        # Check if the password has already been changed, default is 'password'
        admin_usr = self.request.root.users["admin"]
        test_password = salt_password("password", admin_usr.password_salt)
        if test_password != admin_usr.password:
            self.request.session.flash("It looks like someone has already changed the default password on the account, if this wasn't you then contact support!", "info")
            return HTTPFound(location=self.request.route_path("setup_stagethree"))
        # Get password for admin user and double check
        if "password_one" in self.request.POST and  "password_two" in self.request.POST:
            pwd_1 = self.request.POST["password_one"]
            pwd_2 = self.request.POST["password_two"]
            if len(pwd_1) < 5:
                self.request.session.flash("The passwords entered are too short, they must be of 5 characters or longer.", "error")
                return {}
            elif pwd_1 != pwd_2:
                self.request.session.flash("The passwords entered do not match.", "error")
                return {}
            # Set the administrator password
            admin_usr.password_salt = Coding().generateUniqueCode()
            admin_usr.password = salt_password(pwd_1, admin_usr.password_salt)
            return HTTPFound(location=self.request.route_path("setup_stagethree"))
        return {}

    @view_config(
        route_name="setup_stagethree",
        context="ticketing.models.Ticketing",
        renderer="templates/stagethree.pt"
    )
    def setup_three_view(self):
        if (PROP.getProperty(self.request, PROP.SITE_SETUP) == True):
            return HTTPFound(location=self.request.route_path("welcome"))
        elif (PROP.getProperty(self.request, PROP.VERSION) == None):
            return HTTPFound(location=self.request.route_path("setup_stageone"))
        event_date = PROP.getProperty(self.request, PROP.EVENT_DATE)
        
        if "submit" in self.request.POST:
            # Save the event details
            day = int(float(self.request.POST["event_day"]))
            month = int(float(self.request.POST["event_month"]))
            year = int(float(self.request.POST["event_year"]))
            event_name = self.request.POST["event_name"]
            min_age = int(float(self.request.POST["min_age"]))
            self.request.root.properties[PROP.EVENT_DATE] = datetime(year, month, day)
            self.request.root.properties[PROP.EVENT_NAME] = event_name
            self.request.root.properties[PROP.MINIMUM_AGE] = min_age
            return HTTPFound(location=self.request.route_path("setup_done"))
        return {
            "event_day": event_date.day,
            "event_month": event_date.month,
            "event_year": event_date.year,
            "event_name": PROP.getProperty(self.request, PROP.EVENT_NAME),
            "min_age": PROP.getProperty(self.request, PROP.MINIMUM_AGE)
        }
    
    @view_config(
        route_name="setup_done",
        context="ticketing.models.Ticketing",
        renderer="templates/done.pt"
    )
    def setup_done_view(self):
        if (PROP.getProperty(self.request, PROP.SITE_SETUP) == True):
            return HTTPFound(location=self.request.route_path("welcome"))
        elif (PROP.getProperty(self.request, PROP.VERSION) == None):
            return HTTPFound(location=self.request.route_path("setup_stageone"))
        self.request.root.properties[PROP.SITE_SETUP] = True
        return {}

    # -- Database Setup Functions -- #

    def db_run_setup(self, root):
        self.db_setup_properties(root)
        self.db_setup_documents(root)
        self.db_setup_tickets(root)
        self.db_setup_pay_methods(root)
        self.db_setup_accounts(root)

    def db_setup_properties(self, root):
        # Run the population
        root.properties = PersistentMapping()
        # Register a bunch of default properties
        root.properties[PROP.SITE_SETUP] = False
        root.properties[PROP.VERSION] = 1.0
        root.properties[PROP.QUEUE_ENABLED] = False
        root.properties[PROP.MAX_SESSION_TIME] = 15
        root.properties[PROP.CONCURRENT_NUM] = 10
        root.properties[PROP.CUSTOMER_CONTROL_ENABLED] = False
        root.properties[PROP.CONTROL_GROUPS] = PersistentList()
        root.properties[PROP.LIMIT_ENABLED] = False
        root.properties[PROP.MAX_TICKETS] = 2
        root.properties[PROP.PAYMENT_WINDOW] = 21
        root.properties[PROP.PHOTO_REQUIRED] = False
        root.properties[PROP.MINIMUM_AGE] = 18
        root.properties[PROP.EVENT_DATE] = datetime.now()
        root.properties[PROP.EVENT_NAME] = ""
        root.properties[PROP.TRANSFER_FEE_ENABLED] = True
        root.properties[PROP.TRANSFER_FEE] = 500 # Defaults to 5 quid
        root.properties[PROP.DETAILS_FEE_ENABLED] = False
        root.properties[PROP.DETAILS_FEE] = 500 # Defaults to 5 quid
        root.properties[PROP.CHECKIN_ACTIVE] = False
        root.properties[PROP.CHECKIN_SHOW_ALL] = False
        root.properties[PROP.CHECKIN_OVERRIDE_ONE] = ""
        root.properties[PROP.CHECKIN_OVERRIDE_TWO] = ""
        root.properties[PROP.CHECKIN_OVERRIDE_THREE] = ""
        root.properties[PROP.PAYMENT_METHODS] = PersistentList()
        root.properties[PROP.SIGNUP_ENABLED] = False
        root.properties[PROP.ACCOUNT_LOCK_DOWN] = False
        root.properties[PROP.TICKET_DOWNLOAD_ENABLED] = False
        root.properties[PROP.GUEST_DETAILS_REQUIRED] = True
        # Setup some basic automated email texts
        root.properties[PROP.AUTO_EMAIL_INCLUDED_TEXT] = "Thanks, The Committee"
        root.properties[PROP.AUTO_EMAIL_CONTACT_DETAILS] = ""
        root.properties[PROP.ERROR_BOX_CONTACT_INFO] = ""

    def db_setup_documents(self, root):
        purchase_agreement = Document()
        purchase_agreement.__parent__ = root
        purchase_agreement.title = "Purchase Agreement"
        purchase_agreement.help_text = "The purchase agreement is the contract a customer enters into with you, the business,"
        purchase_agreement.help_text += " that dictates all of the conditions of sale. All customers will be required to agree to this "
        purchase_agreement.help_text += "contract before they are allowed to purchase tickets."
        root.properties[PROP.PURCHASE_AGREEMENT] = purchase_agreement
        privacy_policy = Document()
        privacy_policy.__parent__ = root
        privacy_policy.title = "Privacy Policy"
        privacy_policy.help_text = "The privacy policy is a document that sets out how you will handle, store and process customers' data. "
        privacy_policy.help_text += "Privacy policies should be written in accordance with the Data Protection Act and hence should only detail"
        privacy_policy.help_text += " fair and lawful data actions. Customers will be required to agree to the policy before they are allowed to"
        privacy_policy.help_text += " enter or store any details within the system."
        root.properties[PROP.PRIVACY_POLICY] = privacy_policy
        cookie_policy = Document()
        cookie_policy.__parent__ = root
        cookie_policy.title = "Cookie Policy"
        cookie_policy.help_text = "The cookie policy should detail why and how you use cookies to store information during the checkout"
        cookie_policy.help_text += " procedure. The policy should be written in accordance with the e-Privacy Directive and will need you "
        cookie_policy.help_text += "to conduct a full cookie audit of your site."
        root.properties[PROP.COOKIE_POLICY] = cookie_policy
        root.properties._p_changed = True

    def db_setup_tickets(self, root):
        # Tickets
        root.ticket_pools = PersistentMapping()
        # Payments
        root.payments = PersistentMapping()
        # Queue
        root.queue = PersistentList()
        root.active = PersistentMapping()

    def db_setup_pay_methods(self, root):
        # Get the dict
        methods = root.properties[PROP.PAYMENT_METHODS]
        # Start adding methods, first Stripe
        stripe = PaymentMethod()
        stripe.name = "Stripe Debit/Credit Card"
        stripe.short_name = "Stripe"
        stripe.description = "Stripe allows you to receive payments via credit or debit cards for a transaction fee of 2.4% + 20p, this will give your customers much greater flexibility in terms of payment for tickets. Please note Stripe must be enabled in order for customer ticket transfers to be enabled (you can still conduct manual transfers through the administration interface)."
        stripe.__name__ = "stripe"
        stripe.__parent__ = methods
        # - Settings
        stripe.settings[PROP.ORGANISATION_NAME] = PaymentProperty(PROP.ORGANISATION_NAME, 
            "Organisation Name", 
            "The name of your organisation, this will appear on the account statement of the customer as the company charging.", 
            False, False, "My Organisation Name", stripe)
        stripe.settings[PROP.STRIPE_CONTACT_EMAIL] = PaymentProperty(PROP.STRIPE_CONTACT_EMAIL, "Contact Email", "The email address customers can contact to query purchases.", False, False, "stripe@example.com", stripe)
        stripe.settings[PROP.STRIPE_API_KEY] = PaymentProperty(PROP.STRIPE_API_KEY, "API Private Key", "The private API key provided by Stripe.", True, False, "", stripe)
        stripe.settings[PROP.STRIPE_PUBLIC_KEY] = PaymentProperty(PROP.STRIPE_PUBLIC_KEY, "API Public Key", "The public API key provided by Stripe.", False, False, "", stripe)
        stripe.settings[PROP.PAYMENT_METHOD_DESCRIPTION] = PaymentProperty(PROP.PAYMENT_METHOD_DESCRIPTION,
            "Customer Description",
            "The description of the payment type that the customer sees when checking out",
            False, False,
            "Pay for your tickets online using a credit or debit card (Visa or MasterCard). Completing your order this way will mean your tickets are verified immediately. An additional 1.5% processing fee will be charged. All debit and credit card details are handled by Stripe and we do not store your full card details, more information on Stripe can be found at www.stripe.com.",
            stripe)
        stripe.settings[PROP.PAYMENT_METHOD_DESCRIPTION].long_value = True
        stripe.settings[PROP.PAYMENT_PROCESSING_PERCENTAGE] = PaymentProperty(PROP.PAYMENT_PROCESSING_PERCENTAGE, 
            "Processing Percentage", 
            "You can opt to add a processing charge as a percentage of the payment when customers choose to pay by Stripe, set to '0' to disable.", 
            False, True, 0.015, stripe)
        stripe.settings[PROP.PAYMENT_PROCESSING_FEE] = PaymentProperty(PROP.PAYMENT_PROCESSING_FEE, 
            "Processing Fee", 
            "You can opt to add a flat rate processing fee when customers choose to pay by Stripe, set to '0' to disable.", 
            False, False, 0, stripe, monetary=True)
        # - Transaction properties
        stripe.transaction_properties["last_four"] = "Last 4 Card Digits"
        stripe.transaction_properties["ref_code"] = "Stripe Reference Code"
        methods.append(stripe)
        # College bill
        college = PaymentMethod()
        college.name = college.short_name = "College Bill"
        college.description = "Customers choosing to pay by college bill will have their payments marked as such, their details must then be manually processed. Exports of expected payments can be made from the 'Sales' tab."
        college.__name__ = "collegebill"
        college.__parent__ = methods
        # - Settings
        college.settings[PROP.PAYMENT_METHOD_DESCRIPTION] = PaymentProperty(PROP.PAYMENT_METHOD_DESCRIPTION,
            "Customer Description",
            "The description of the payment type that the customer sees when checking out",
            False, False,
            "By selecting to pay by college bill the price of the ticket will be added to your next college bill. This option is only available to members of the college.",
            college)
        college.settings[PROP.PAYMENT_METHOD_DESCRIPTION].long_value = True
        college.settings[PROP.COLLEGE_BILL_DETAILS] = PaymentProperty(PROP.COLLEGE_BILL_DETAILS,
            "Additional Details",
            "These additional details will be shown to the customer if they select to pay by college bill.",
            False, False,
            "Payments by college bill will be charged on the next bill you receive. This option requires you to be a current member of the college, you must not choose this option unless you meet this criteria.",
            college)
        college.settings[PROP.COLLEGE_BILL_DETAILS].long_value = True
        college.settings[PROP.PAYMENT_PROCESSING_FEE] = PaymentProperty(PROP.PAYMENT_PROCESSING_FEE, 
            "Processing Fee", 
            "You can opt to add a flat rate processing fee when customers choose to pay by college bill, set to '0' to disable.", 
            False, False, 0, college, monetary=True)
        methods.append(college)
        # Bank transfer
        bank = PaymentMethod()
        bank.name = bank.short_name = "Bank Transfer"
        bank.description = "Customers choosing to pay by bank transfer will be issued a unique payment reference code that they must quote when making payment, you can then later use this payment reference to link payments with individuals."
        bank.deadlined = True
        bank.__name__ = "banktransfer"
        bank.__parent__ = methods
        # - Settings
        bank.settings[PROP.ORGANISATION_NAME] = PaymentProperty(PROP.ORGANISATION_NAME, 
            "Organisation Name", 
            "The name of your organisation associated with your bank account.", 
            False, False, "My Organisation Name", bank)
        bank.settings[PROP.BANK_ACCOUNT] = PaymentProperty(PROP.BANK_ACCOUNT, "Bank Account Number", "The account number of your bank account.", False, False, "12345678", bank)
        bank.settings[PROP.BANK_SORT_CODE] = PaymentProperty(PROP.BANK_SORT_CODE, "Account Sort Code", "The account sort code of your bank account.", False, False, "12-45-67", bank)
        bank.settings[PROP.PAYMENT_METHOD_DESCRIPTION] = PaymentProperty(PROP.PAYMENT_METHOD_DESCRIPTION,
            "Customer Description",
            "The description of the payment type that the customer sees when checking out",
            False, False,
            "Pay for your tickets via a direct bank transfer. You must quote the provided reference code when making the transfer so that the payment can be linked to your account. Your tickets will be verified after payment has been received.",
            bank)
        bank.settings[PROP.PAYMENT_METHOD_DESCRIPTION].long_value = True
        bank.settings[PROP.PAYMENT_PROCESSING_FEE] = PaymentProperty(PROP.PAYMENT_PROCESSING_FEE, 
            "Processing Fee", 
            "You can opt to add a flat rate processing fee when customers choose to pay by bank transfer, set to '0' to disable.", 
            False, False, 0, bank, monetary=True)
        methods.append(bank)
        # Cheque
        cheque = PaymentMethod()
        cheque.name = cheque.short_name = "Cheque"
        cheque.description = "Customers choosing to pay by cheque will be issued a unique payment reference code that they must write on the reverse of the cheque, you can then later use this payment reference to link payments with individuals."
        cheque.deadlined = True
        cheque.__name__ = "cheque"
        cheque.__parent__ = methods
        # - Settings
        cheque.settings[PROP.ORGANISATION_NAME] = PaymentProperty(PROP.ORGANISATION_NAME, 
            "Organisation Name", 
            "The name of your organisation associated with your bank account.", 
            False, False, "My Organisation Name", cheque)
        cheque.settings[PROP.PAYMENT_METHOD_DESCRIPTION] = PaymentProperty(PROP.PAYMENT_METHOD_DESCRIPTION,
            "Customer Description",
            "The description of the payment type that the customer sees when checking out",
            False, False,
            "Pay for your tickets by handing in a check to the porters' lodge. You must write the provided reference code on the reverse of the cheque so that the payment can be linked to your account. Your tickets will be verified after the cheque has cleared.",
            cheque)
        cheque.settings[PROP.PAYMENT_METHOD_DESCRIPTION].long_value = True
        cheque.settings[PROP.PAYMENT_PROCESSING_FEE] = PaymentProperty(PROP.PAYMENT_PROCESSING_FEE, 
            "Processing Fee", 
            "You can opt to add a flat rate processing fee when customers choose to pay by cheque, set to '0' to disable.", 
            False, False, 0, cheque, monetary=True)
        methods.append(cheque)
        # Gift method
        gifted = PaymentMethod()
        gifted.name = gifted.short_name = "Gifted"
        gifted.description = "This payment method is used when gifting tickets to individuals, the tickets will be allocated for free. This method never appears publicly as a method for payment."
        gifted.__name__ = "gifted"
        gifted.__parent__ = methods
        gifted.public = False
        gifted.enabled = True
        methods.append(gifted)

    def db_setup_accounts(self, root):
        # Groups & users
        root.groups = PersistentMapping()
        root.users = PersistentMapping()
        # admin
        admin = Group()
        admin.__name__ = "admin"
        admin.__parent__ = root
        admin.can_delete = False
        admin.name = "Administrators"
        admin.privileges = ["admin"]
        admin._p_changed = True
        root.groups[admin.__name__] = admin
        # committee
        committee = Group()
        committee.__name__ = "committee"
        committee.__parent__ = root
        committee.name = "Committee Members"
        committee.privileges = ["committee"]
        committee._p_changed = True
        root.groups[committee.__name__] = committee
        # Raven authentications
        raven_grp = Group()
        raven_grp.__name__ = "raven"
        raven_grp.__parent__ = root
        raven_grp.name = "Customers (Raven)"
        raven_grp.privileges = ["basic"]
        raven_grp._p_changed = True
        root.groups[raven_grp.__name__] = raven_grp
        # Alumnus authentications
        alumni_grp = Group()
        alumni_grp.__name__ = "alumni"
        alumni_grp.__parent__ = root
        alumni_grp.name = "Customers (Alumni)"
        alumni_grp.privileges = ["basic"]
        alumni_grp._p_changed = True
        root.groups[alumni_grp.__name__] = alumni_grp
        # Ungrouped
        ungrouped = Group()
        ungrouped.__name__ = "ungrouped"
        ungrouped.__parent__ = root
        ungrouped.name = "Ungrouped"
        ungrouped.privileges = ["basic"]
        ungrouped.can_delete = False
        ungrouped._p_changed = True
        root.groups[ungrouped.__name__] = ungrouped
        # Setup an admin user
        admin_usr = User()
        admin_usr.username = "admin"
        admin_usr.password_salt = Coding().generateUniqueCode()
        admin_usr.password = salt_password("password", admin_usr.password_salt)
        admin_usr.__name__ = admin_usr.username
        admin_usr.__parent__ = admin
        root.users[admin_usr.__name__] = admin_usr
        admin.members.append(admin_usr)
        admin.members._p_changed = True
        admin_usr.privacy_agreement = True
        admin_usr.purchase_agreement = True
        admin_prof = UserProfile()
        admin_usr.profile = admin_prof
        admin_prof.__parent__ = admin_usr
        admin_prof.title = "Admin"
        admin_prof.forename = "Super"
        admin_prof.surname = "Administrator"
        admin_prof.email = "ticketingadmin@lightlogic.co.uk"
        admin_prof.dob = datetime(year=1990, month=1, day=1)
        admin_prof.photo_file = "blank.png"
        admin_prof.address = PostalAddress()
        admin_prof.address.__parent__ = admin_prof
        admin_prof.address.line_one = "Admin Address"
        admin_prof.address.line_two = "Admin Address"
        admin_prof.address.city = "Cambridge"
        admin_prof.address.county = "Cambridgeshire"
        admin_prof.address.country = "United Kingdom"
        admin_prof.address.postal_code = "CB1 1AA"
        admin_prof.phone_number = "01234 567890"
