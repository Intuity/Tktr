# -*- coding: utf-8 -*- 

from datetime import datetime
import locale
import math
from pyramid.renderers import get_renderer
from pyramid.decorator import reify

from ticketing.models import PROP_KEYS as PROP
from ticketing.queue.queue import Queue

class BaseLayout(object):
    
    # Mutual data

    college_name_keys = [("christs", "Christ's"), ("churchill", "Churchill"), ("clare", "Clare"), 
                        ("clare-hall", "Clare Hall"), ("corpus-christi", "Corpus Christi"), 
                        ("darwin", "Darwin"), ("downing", "Downing"), ("emmanuel", "Emmanuel"), 
                        ("fitzwilliam", "Fitzwilliam"), ("girton", "Girton"), 
                        ("gonville-and-caius", "Gonville and Caius"), ("homerton", "Homerton"), 
                        ("hughes-hall", "Hughes Hall"), ("jesus", "Jesus"), ("kings", "King's"), 
                        ("lucy-cavendish", "Lucy Cavendish"), ("magdalene", "Magdalene"), 
                        ("murray-edwards", "Murray Edwards"), ("newnham", "Newnham"), ("pembroke", "Pembroke"), 
                        ("peterhouse", "Peterhouse"), ("queens", "Queens'"), ("robinson", "Robinson"), 
                        ("st-catharines", "St Catharine's"), ("st-edmunds", "St Edmund's"), 
                        ("st-johns", "St John's"), ("selwyn", "Selwyn"), ("sidney-sussex", "Sidney Sussex"), 
                        ("trinity", "Trinity"), ("trinity-hall", "Trinity Hall"), ("wolfson", "Wolfson"), ("other", "Other"), 
                        ("notaffil", "Not Affiliated")]

    college_dict =   {"christs": "Christ's", "churchill": "Churchill", "clare": "Clare", 
                                "clare-hall": "Clare Hall", "corpus-christi": "Corpus Christi", 
                                "darwin": "Darwin", "downing": "Downing", "emmanuel": "Emmanuel", 
                                "fitzwilliam": "Fitzwilliam", "girton": "Girton", 
                                "gonville-and-caius": "Gonville and Caius", "homerton": "Homerton", 
                                "hughes-hall": "Hughes Hall", "jesus": "Jesus", "kings": "King's", 
                                "lucy-cavendish": "Lucy Cavendish", "magdalene": "Magdalene", 
                                "murray-edwards": "Murray Edwards", "newnham": "Newnham", "pembroke": "Pembroke", 
                                "peterhouse": "Peterhouse", "queens": "Queens'", "robinson": "Robinson", 
                                "st-catharines": "St Catharine's", "st-edmunds": "St Edmund's", 
                                "st-johns": "St John's", "selwyn": "Selwyn", "sidney-sussex": "Sidney Sussex", 
                                "trinity": "Trinity", "trinity-hall": "Trinity Hall", "wolfson": "Wolfson", "other": "Other", 
                                "notaffil": "Not Affiliated"}

    college_keys = ["christs", "churchill", "clare", "clare-hall", "corpus-christi", "darwin", 
                    "downing", "emmanuel", "fitzwilliam", "girton", "gonville-and-caius", "homerton", 
                    "hughes-hall", "jesus", "kings", "lucy-cavendish", "magdalene", "murray-edwards", 
                    "newnham", "pembroke", "peterhouse", "queens", "robinson", "st-catharines", 
                    "st-edmunds", "st-johns", "selwyn", "sidney-sussex", "trinity", "trinity-hall", 
                    "wolfson", "other", "notaffil"]

    grad_status_keys = ["undergrad", "postgrad", "fellow", "alumni", "staff", "other"]

    grad_status_dict = {"undergrad": "Undergraduate", "postgrad": "Post Graduate", "fellow": "Fellow", "alumni":"Alumnus", "staff": "Staff", "other": "Other"}
    
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

    # Main functions
    
    def __init__(self, context, request):
        self.context = context
        self.request = request
    
    @reify
    def site_style(self):
        renderer = get_renderer("templates/site_style.pt")
        return renderer.implementation().macros["site_style"]

    @reify
    def ticket_pay_list(self):
        renderer = get_renderer("templates/ticket_pay_list.pt")
        return renderer.implementation().macros["ticket_pay_list"]
    
    @reify
    def current_year(self):
        return datetime.now().strftime("%Y")

    # Common functions
    @property
    def browser_cookies(self):
        return self.request.cookies

    @property
    def agreed_to_cookies(self):
        cookies = self.browser_cookies
        return ("cookie_policy" in cookies and cookies["cookie_policy"] == "cookie_agreed")

    @property
    def session_tickets(self):
        user = self.user
        return [x for x in user.tickets if x.payment == None]

    # Return only the types the user is allowed to purchase
    @property
    def ticket_types(self):
        return sorted([x.tick_type for x in self.context.ticket_pools.values() if self.group.__name__ in x.groups], key=lambda x: x.cost)

    # Return all of the configured ticket types
    @property
    def all_ticket_types(self):
        return sorted([x.tick_type for x in self.context.ticket_pools.values()], key=lambda x: x.cost)

    @property
    def user(self):
        if not "user_id" in self.request.session or self.request.session["user_id"] == None:
            return None
        return self.request.root.users[self.request.session["user_id"]]

    @property
    def can_buy(self):
        can_they_buy = (self.request.root.properties[PROP.CUSTOMER_CONTROL_ENABLED] == False)
        if not can_they_buy:
            can_they_buy = self.group.__name__ in self.request.root.properties[PROP.CONTROL_GROUPS]
        return can_they_buy

    @property
    def can_manage(self):
        user = self.user
        return ("admin" in user.__parent__.privileges or "committee" in user.__parent__.privileges)

    @property
    def public_signup_enabled(self):
        return (PROP.SIGNUP_ENABLED in self.request.root.properties and self.request.root.properties[PROP.SIGNUP_ENABLED])

    @property
    def alumni_raven_enabled(self):
        return (PROP.ALUMNI_RAVEN_ENABLED in self.request.root.properties and self.request.root.properties[PROP.ALUMNI_RAVEN_ENABLED])

    @property
    def account_lock_down(self):
        return (PROP.ACCOUNT_LOCK_DOWN in self.request.root.properties and self.request.root.properties[PROP.ACCOUNT_LOCK_DOWN])

    @property
    def ticket_download_enabled(self):
        return (PROP.TICKET_DOWNLOAD_ENABLED in self.request.root.properties and self.request.root.properties[PROP.TICKET_DOWNLOAD_ENABLED])

    @property
    def guest_details_required(self):
        return (PROP.GUEST_DETAILS_REQUIRED in self.request.root.properties and self.request.root.properties[PROP.GUEST_DETAILS_REQUIRED])

    @property
    def error_contact_info(self):
        return (self.request.root.properties[PROP.ERROR_BOX_CONTACT_INFO] if PROP.ERROR_BOX_CONTACT_INFO in self.request.root.properties else "")

    @property
    def can_checkin(self):
        user = self.user
        return ("admin" in user.__parent__.privileges or "committee" in user.__parent__.privileges or "staff" in user.__parent__.privileges)

    @property
    def is_admin(self):
        return ("admin" in self.user.__parent__.privileges)

    @property
    def group(self):
        return self.user.__parent__

    @property
    def purchase_limited(self):
        return PROP.getProperty(self.request, PROP.LIMIT_ENABLED)

    @property
    def purchase_max(self):
        return PROP.getProperty(self.request, PROP.MAX_TICKETS)

    @property
    def payment_window(self):
        return PROP.getProperty(self.request, PROP.PAYMENT_WINDOW)

    @property
    def transfer_fee_enabled(self):
        return PROP.getProperty(self.request, PROP.TRANSFER_FEE_ENABLED)

    @property
    def transfer_fee(self):
        return PROP.getProperty(self.request, PROP.TRANSFER_FEE)

    @property
    def details_fee_enabled(self):
        return PROP.getProperty(self.request, PROP.DETAILS_FEE_ENABLED)

    @property
    def details_fee(self):
        return PROP.getProperty(self.request, PROP.DETAILS_FEE)

    @property
    def photo_required(self):
        return PROP.getProperty(self.request, PROP.PHOTO_REQUIRED)

    @property
    def checkin_active(self):
        return (PROP.getProperty(self.request, PROP.CHECKIN_ACTIVE) == True)

    @property
    def event_name(self):
        return PROP.getProperty(self.request, PROP.EVENT_NAME)

    @property
    def site_title(self):
        event_name = self.event_name
        if event_name and len(event_name) > 0:
            return event_name + " Ticketing"
        else:
            return "Ticketing"

    @property
    def numeric_total(self):
        tickets = self.session_tickets
        total = 0
        for tick in tickets:
            total += tick.tick_type.cost
            if tick.addons != None:
                for addon in tick.addons.values():
                    total += addon.cost
        return total

    @property
    def total(self):
        total = self.numeric_total
        return self.format_price(total)

    @property
    def user_details_complete(self):
        return self.user.profile.complete

    def user_ticket(self, user=None):
        if user == None:
            user = self.user
        if user.tickets == None or len(user.tickets) <= 0:
            return None
        try:
            tick = [x for x in user.tickets if x.guest_info == x.owner.profile][0]
            if tick.payment == None:
                return None
            else:
                return tick
        except Exception:
            return None

    # Check whether (and how many) a user holds tickets of a particular type
    def user_check_owns_type(self, tick_type, user=None):
        if user == None:
            user = self.user
        if user.tickets == None or len(user.tickets) <= 0:
            return 0
        try:
            of_type = [x for x in user.tickets if x.tick_type.__name__ == tick_type]
            return len(of_type)
        except Exception:
            return 0

    def user_can_buy_type(self, tick_type, user=None):
        if user == None:
            user = self.user
        pools = [x for x in self.request.root.ticket_pools.values() if x.tick_type.__name__ == tick_type]
        # Can't buy it if it doesn't exist!
        if len(pools) <= 0:
            return False
        tick_pool = pools[0]
        # Check grouping allows us to purchase
        if user.__parent__.__name__ not in tick_pool.groups:
            return False
        # Check we aren't breaking max purchase limit
        if self.purchase_limited and user.total_tickets >= self.purchase_max:
            return False
        # Check we aren't breaking purchase limit of type
        if tick_pool.tick_type.purchase_limit > 0 and self.user_check_owns_type(tick_type, user) >= tick_pool.tick_type.purchase_limit:
            return False
        return True

    # Check that all the required guest and owner details have been satisified
    @property
    def details_complete(self):
        # First check user
        if not self.user_details_complete:
            return False
        # Now check all session tickets
        for ticket in self.session_tickets:
            if ticket.guest_info == None or not ticket.guest_info.complete:
                return False
        # Otherwise we good
        return True

    def format_price(self, price, symbol=True):
        try:
            locale.setlocale(locale.LC_ALL, "en_GB")
            pricetext = None
            if symbol:
                pricetext = locale.currency((price/100.0)).replace("\xa3","&pound;")
            else:
                pricetext = locale.currency((price/100.0)).replace("\xa3","")
            # Strip all non-ascii characters
            pricetext = "".join(i for i in pricetext if ord(i)<128)
            return pricetext
        except Exception:
            return "-"

    def college_name(self, key):
        if key in self.college_dict:
            return self.college_dict[key]
        else:
            return "-"

    def graduate_status(self, key):
        if key in self.grad_status_dict:
            return self.grad_status_dict[key]
        else:
            return "-"

    def get_payment_method(self, key):
        if key == None:
            return None
        methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method = [x for x in methods if x.__name__.lower() == key.lower()]
        if len(method) == 0:
            return None
        else:
            return method[0]

    @property
    def payment_methods_list(self):
        methods = PROP.getProperty(self.request, PROP.PAYMENT_METHODS)
        method_list = {}
        for method in methods:
            method_list[method.__name__] = method.name
        return method_list

    # Queuing
    @property
    def queue_enabled(self):
        value = PROP.getProperty(self.request, PROP.QUEUE_ENABLED)
        if value == None:
            return False
        return value 

    @property
    def queue_item(self):
        if not self.request.root.properties[PROP.QUEUE_ENABLED]:
            return None
        if "active_id" in self.request.session:
            active_id = self.request.session["active_id"]
            if active_id in self.request.root.active:
                return self.request.root.active[active_id]
            # Might be in queue instead?
            items = [x for x in self.request.root.queue if x.queue_id == active_id]
            if len(items) > 0:
                return items[0]
            else: # Nope, doesn't exist
                self.request.session.pop("active_id", None)
                self.request.session.pop("queue_id", None)
                return None
        elif "queue_id" in self.request.session:
            queue_id = self.request.session["queue_id"]
            items = [x for x in self.request.root.queue if x.queue_id == queue_id]
            if len(items) > 0:
                return items[0]
            else:
                return None
        else:
            return None

    @property
    def has_queued(self):
        if not self.request.root.properties[PROP.QUEUE_ENABLED]:
            return True
        elif "active_id" in self.request.session:
            active_id = self.request.session["active_id"]
            if active_id in self.request.root.active:
                #active = self.request.root.active[active_id]
                time_left = Queue(self.request).purchase_time_left(active_id=active_id)
                if time_left <= 0:
                    return False
                else:
                    return True
            else:
                return False
        else:
            return False

    @property
    def time_left(self):
        return Queue(self.request).purchase_time_left()

    @property
    def formatted_time(self):
        raw_seconds = self.time_left
        minutes = math.floor(raw_seconds / 60.0)
        seconds = raw_seconds - minutes * 60
        return "%i:%.2i" % (minutes, seconds)
