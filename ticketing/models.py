import base64, hashlib, re
from persistent import Persistent
from persistent.mapping import PersistentMapping
from persistent.list import PersistentList
from pyramid.security import Everyone, Allow, ALL_PERMISSIONS

# Property keys
class PROP_KEYS(object):
    SITE_SETUP = "SITESETUP"
    QUEUE_ENABLED = "QUEUEENABLED"
    MAX_SESSION_TIME = "MAXSESSIONTIME"
    CONCURRENT_NUM = "CONCURRENTCUSTOMERS"
    CUSTOMER_CONTROL_ENABLED = "CUSTOMERCONROL_ENABLED"
    CONTROL_GROUPS = "CONTROL_GROUPS"
    LIMIT_ENABLED = "PURCHASELIMITENABLED"
    MAX_TICKETS = "MAXTICKETNUMBER"
    PAYMENT_WINDOW = "PAYMENTWINDOW"
    VERSION = "VERSIONCODE"
    PURCHASE_AGREEMENT = "PURCHASEAGREEMENT"
    PRIVACY_POLICY = "PRIVACYPOLICY"
    COOKIE_POLICY = "COOKIEPOLICY"
    PHOTO_REQUIRED = "PHOTOREQUIRED"
    MINIMUM_AGE = "MINIMUMAGE"
    EVENT_DATE = "EVENTDATE"
    EVENT_NAME = "EVENTNAME"
    # Whether & how much to charge for ticket ownership transfers
    TRANSFER_FEE_ENABLED = "TRANSFER_FEE_ENABLED"
    TRANSFER_FEE = "TRANSFERFEE"
    # Whether & how much to chage for guest detail changes
    DETAILS_FEE_ENABLED = "DETAILS_FEE_ENABLED"
    DETAILS_FEE = "DETAILS_FEE"
    # Ticket check in parameters
    CHECKIN_ACTIVE = "CHECKINACTIVE"
    CHECKIN_SHOW_ALL = "CHECKINSHOWALL"
    CHECKIN_OVERRIDE_ONE = "CHECKINOVER1"
    CHECKIN_OVERRIDE_TWO = "CHECKINOVER2"
    CHECKIN_OVERRIDE_THREE = "CHECKINOVER3"
    PAYMENT_METHODS = "PAYMENTMETHODS"
    SIGNUP_ENABLED = "SIGNUPENABLED"
    ALUMNI_RAVEN_ENABLED = "ALUMNIRAVENENABLED"
    ACCOUNT_LOCK_DOWN = "ACCOUNTLOCKDOWN"
    TICKET_DOWNLOAD_ENABLED = "TICKETDOWNLOADENABLED"
    GUEST_DETAILS_REQUIRED = "GUESTDETAILSREQUIRED"

    # Payment settings
    PAYMENT_METHOD_DESCRIPTION          = "PAYMENTMETHODDESCRIPTION"
    PAYMENT_PROCESSING_FEE              = "PAYMENTPROCESSINGFEE"
    PAYMENT_PROCESSING_PERCENTAGE       = "PAYMENTPROCESSINGPERCENTAGE"
    STRIPE_CONTACT_EMAIL                = "STRIPECONTACTEMAIL"
    STRIPE_API_KEY                      = "STRIPEAPIPRIVATEKEY"
    STRIPE_PUBLIC_KEY                   = "STRIPEAPIPUBLICKEY"
    STRIPE_ADDITIONAL_PERCENTAGE        = "STRIPEADDITIONALPERCENTAGE"
    ORGANISATION_NAME                   = "ORGNAME"
    BANK_ACCOUNT                        = "BANKACCOUNTNUMBER"
    BANK_SORT_CODE                      = "BANKSORTCODE"
    COLLEGE_BILL_DETAILS                = "COLLEGEBILLDETAILS"
    
    # Automated email settings
    AUTO_EMAIL_INCLUDED_TEXT = "AUTOEMAILINCLUDEDTEXT"
    AUTO_EMAIL_CONTACT_DETAILS = "AUTOEMAILCONTACTDETAILS"
    
    # Emergency contact details
    ERROR_BOX_CONTACT_INFO = "ERRORBOXCONTACTINFO"

    @classmethod
    def getProperty(cls, request, key):
        if not "properties" in request.root.__dict__:
            return None
        elif not key in request.root.properties:
            request.root.properties[key] = None
            #raise KeyError("Property key did not exist in dictionary!")
        return request.root.properties[key]


class Ticketing(PersistentMapping):
    __parent__ = __name__ = None
    # Setup ACL on root object
    __acl__ = [
            (Allow, Everyone, 'public'), # Deals with before queue
            
            (Allow, 'group:raven', 'raven'), # Only Raven auth level
            
            (Allow, 'group:basic', 'basic'),
            (Allow, 'group:committee', 'basic'),
            (Allow, 'group:admin', 'basic'),
            (Allow, 'group:staff', 'basic'),
            
            (Allow, 'group:staff', 'staff'),
            (Allow, 'group:committee', 'staff'),
            (Allow, 'group:admin', 'staff'),
            
            (Allow, 'group:committee', 'committee'),
            (Allow, 'group:admin', 'committee'),
            
            (Allow, 'group:admin', 'admin'),
            (Allow, 'group:admin', ALL_PERMISSIONS),
            ]

    properties = None
    ticket_pools = None
    groups = None
    users = None
    payments = None
    queue = None
    active = None # Active purchasers


class Group(Persistent):
    name = None
    privileges = None
    members = None
    can_delete = None
    user_filter = None # Filter CRSId users into this group if they match
    access_code = None

    def __init__(self):
        self.name = ""
        self.privileges = []
        self.members = PersistentList()
        self.can_delete = True
        self.user_filter = PersistentList()
        self.access_code = None


# User doesn't contain any personal information, that is
# stored in the profile - unified for guests and users
class User(Persistent):
    username = None
    password = None
    password_salt = None
    profile = None
    tickets = None # Not one-to-one
    payments = None
    total_tickets = 0 # Counts all tickets including those exchanged
    privacy_agreement = False
    purchase_agreement = False
    notes = None
    api_token = None

    def __init__(self):
        self.username = ""
        self.password = ""
        self.profile = None
        self.tickets = PersistentList() # Not one-to-one
        self.payments = PersistentList()
        self.total_tickets = 0
        self.notes = ""
        self.api_token = None

# Stores documents like the privacy policy and user agreement that must be agreed to.
class Document(Persistent):
    title = None
    headline_points = None
    main_body = None
    help_text = None

    def __init__(self):
        self.title = ""
        self.headline_points = PersistentList()
        self.main_body = ""
        self.help_text = None

    @property
    def plaintext_body(self):
        plain = self.main_body.replace("<br />", "\n\n")
        plain = re.sub(r"<.*?>", "", plain)
        plain = plain.replace("&ldquo;", "\"")
        plain = plain.replace("&rdquo;", "\"")
        plain = plain.replace("&rsquo;", "'")
        plain = plain.replace("&lsquo;", "'")
        plain = plain.replace("&amp;", "&")
        plain = plain.replace("&nbsp;", " ")
        plain = plain.replace("&pound;", u"\u00A3")
        return plain


def appmaker(zodb_root):
    if not 'app_root' in zodb_root:
        # Setup the application root
        app_root = Ticketing()
        zodb_root['app_root'] = app_root
        # Commit this
        import transaction
        transaction.commit()
    return zodb_root['app_root']

def salt_password(password, salt):
    salted = password[::-1] + salt
    return base64.urlsafe_b64encode(hashlib.md5(salted).digest())

