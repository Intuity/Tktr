from datetime import datetime, timedelta
from persistent import Persistent
from persistent.list import PersistentList
from persistent.mapping import PersistentMapping

from ticketing.boxoffice.coding import Coding
from ticketing.models import PROP_KEYS as PROP


# Ticket pool houses all un-issued tickets for a type, only tickets
# pre-existent in the pool may be issued (i.e. no creation)
class TicketPool(Persistent):
    tick_type = None
    tickets = None
    groups = None # List of groups able to purchase from this pool

    def __init__(self):
        self.__name__ = "POOL-" + Coding().generateUniqueCode()
        self.tick_type = None
        self.tickets = PersistentList()
        self.groups = PersistentList()


# Information about the type of ticket issued
class TicketType(Persistent):
    name = None
    description = None
    cost = None # Stored in pennies!
    total_released = None
    addons = None
    purchase_limit = 0
    locked_down = False

    # __parent__ points at the pool
    def __init__(self, name="", description="", cost=0, total_released=0):
        self.__name__ = "TYPE-" + Coding().generateUniqueCode()
        self.name = name
        self.description = description
        self.cost = cost
        self.total_released = total_released
        self.addons = PersistentMapping()
        self.purchase_limit = 0
        self.locked_down = False

class TicketAddon(Persistent):
    name = None
    description = None
    cost = None
    total_released = None
    allocated = None
    exclusive = False # Only one "exclusive" addon may be purchased (i.e. queue jump and dining are exclusives)
    unlimited = False # For charitable donations etc.
    locked_down = False

    # __parent__ points at the type
    def __init__(self):
        coding = Coding()
        self.__name__ = coding.generateUniqueCode()
        self.name = self.description = None
        self.cost = 0
        self.total_released = 0
        self.allocated = PersistentList()
        self.exclusive = False
        self.unlimited = False
        self.locked_down = False

    @property
    def soldout(self):
        if self.unlimited:
            return False
        num_left = self.total_released - len(self.allocated)
        if num_left > 0:
            return False
        else:
            return True

    @property
    def remaining(self):
        if self.unlimited:
            return 10000
        else:
            return self.total_released - len(self.allocated)

# The ticket itself
class Ticket(Persistent):
    id_code = None
    owner = None
    payment = None
    issue_date = None
    creation_date = None
    # __parent__ points at the pool if un-issued, else at owner
    guest_info = None
    change_enabled = False # Whether or not the guest details can be changed for this ticket
    tick_type = None
    addons = None
    checked_in = None
    checkin_data = None
    notes = None

    def __init__(self):
        coding = Coding()
        self.__name__ = self.id_code = coding.generateUniqueCode()
        self.owner = None
        self.payment = None
        self.issue_date = None
        self.creation_date = datetime.now()
        self.guest_info = None
        self.change_enabled = False
        self.tick_type = None
        self.addons = PersistentMapping()
        self.checked_in = False
        self.checkin_data = None
        self.notes = ""

    def csv(self, admin=False):
        address = self.owner.profile.address
        str_address = "None"
        if address != None:
            str_address = '"%s, %s, %s, %s, %s, %s"' % (address.line_one, address.line_two, 
                                                        address.city, address.county, 
                                                        address.country, address.postal_code)
        addons_str = "None"
        if self.addons != None and len(self.addons) > 0:
            addon_names = [x.name for x in self.addons.values()]
            addons_str = " + ".join(addon_names)
        if admin:
            return ",".join([
                self.id_code,
                self.payment.ref_code,
                self.owner.profile.title,
                self.owner.profile.fullname,
                self.owner.profile.email,
                self.guest_info.title,
                self.guest_info.fullname,
                self.guest_info.email,
                self.tick_type.name,
                addons_str,
                "%.02f" % (self.total_cost / 100.0),
                self.issue_date.strftime("%d/%m/%Y"),
                str_address
            ]) + "\n"
        else:
            return ",".join([
                self.id_code,
                self.payment.ref_code,
                self.owner.profile.title,
                self.owner.profile.fullname,
                "HIDDEN",
                self.guest_info.title,
                self.guest_info.fullname,
                "HIDDEN",
                self.tick_type.name,
                addons_str,
                "%.02f" % (self.total_cost / 100.0),
                self.issue_date.strftime("%d/%m/%Y"),
                "HIDDEN"
            ]) + "\n"

    # Release all add-ons that this ticket holds
    def release_addons(self):
        if self.addons == None:
            self.addons = PersistentMapping()
            return
        to_remove = []
        for addon_key in self.addons:
            addon = self.addons[addon_key]
            addon.allocated.remove(self)
            to_remove.append(addon_key)
        for addon_key in to_remove:
            self.addons.pop(addon_key, None)

    @property
    def addon_cost(self):
        total = 0
        if self.addons != None:
            for addon in self.addons.values():
                total += addon.cost
        return total

    @property
    def total_cost(self):
        return (self.tick_type.cost + self.addon_cost)

    @property
    def checkin_status(self):
        return (hasattr(self, "checked_in") and self.checked_in == True)

    @property
    def locked_down(self):
        locked = self.tick_type.locked_down
        if not locked and self.addons:
            for addon in self.addons.values():
                if addon.locked_down:
                    locked = True
                    break
        return locked

# Payments
class Payment(Persistent):
    ref_code = None
    owner = None
    opened_date = None
    completed_date = None
    tickets = None
    notes = None
    history = None

    def __init__(self):
        self.__name__ = self.ref_code = Coding().generateUniqueCode(short=True,withdash=False)
        self.owner = self.method = None
        self.opened_date = datetime.now()
        self.tickets = PersistentList()
        self.notes = ""
        self.history = PersistentList()

    def expiring(self, window):
        return ((datetime.now() - self.opened_date) > timedelta(days=(window - 4))) and not self.paid
            
    def expired(self, window):
        return ((datetime.now() - self.opened_date) > timedelta(days=window)) and not self.paid

    def due_date(self, window):
        return self.opened_date + timedelta(days=window)

    @property
    def total(self):
        total = self.item_total
        for stage in self.history:
            total += stage.processing_charge
        return total

    @property
    def processing(self):
        processing = 0
        for stage in self.history:
            processing += stage.processing_charge
        return processing

    @property
    def item_total(self):
        total = 0
        for ticket in self.tickets:
            total += ticket.total_cost
        return total

    @property
    def amount_remaining(self):
        remaining = self.item_total
        for stage in self.history:
            remaining = (remaining - stage.amount_paid) + stage.processing_charge
        return remaining

    @property
    def amount_paid(self):
        paid = 0
        for stage in self.history:
            paid += stage.amount_paid
        return paid
        
    @property
    def paid(self):
        if not self.history or len(self.history) == 0:
            return False
        return (self.amount_remaining <= 0)

    @property
    def current_method(self):
        if len(self.history) == 0:
            return None
        return self.history[-1].method

    @property
    def current_stage(self):
        if len(self.history) == 0:
            return None
        return self.history[-1]

    def csv(self):
        completed_date_str = "Not Completed"
        if self.completed_date: completed_date_str = self.completed_date.strftime("%d/%M/%Y")
        paid_str = "Unpaid"
        if self.paid: paid_str = "Paid"
        transfer_str = "No"
        if self.transfer: transfer_str = "Yes"
        return ",".join([
            self.ref_code,
            self.owner.profile.title,
            self.owner.profile.fullname,
            self.owner.profile.email,
            self.method,
            self.opened_date.strftime("%d/%m/%Y %H:%M:%S"),
            completed_date_str,
            paid_str,
            str(len(self.tickets)),
            transfer_str,
            "%.02f" % (self.processing / 100.0),
            "%.02f" % (self.total / 100.0)
        ]) + "\n"

class PaymentStage(Persistent):
    method = None
    method_properties = None
    method_change = False
    amount_paid = 0
    processing_charge = 0
    received = False # e.g. physically received the cheque
    cashed = False # e.g. cheque cashed and not bounced
    completed = False
    transfer = False
    stage_owner = None
    date = None

    def __init__(self):
        self.__name__ = Coding().generateUniqueCode(short=True,withdash=False)
        self.method = None
        self.method_properties = PersistentMapping()
        self.method_change = False
        self.amount_paid = 0
        self.processing_charge = 0
        self.received = False
        self.cashed = False
        self.completed = False
        self.transfer = False
        self.stage_owner = None
        self.date = datetime.now()

    # How much is remaining before this stage is paid
    @property
    def amount_remaining(self):
        sum_to_point = 0
        transfer_sum = 0
        # First seach for any transfers out
        for i in range(len(self.__parent__.history)):
            stage = self.__parent__.history[i]
            if stage.transfer and stage.amount_paid < 0:
                transfer_sum -= stage.amount_paid
        # Now search for actual payments
        for i in range(len(self.__parent__.history)):
            stage = self.__parent__.history[i]
            if stage.transfer:
                continue
            elif stage == self:
                break
            sum_to_point += stage.amount_paid - stage.processing_charge
        return (self.__parent__.item_total + transfer_sum - sum_to_point)

    @property
    def status(self):
        most_recent = (self.__parent__.current_stage == self)
        sum_to_point = 0
        for stage in self.__parent__.history:
            sum_to_point += stage.amount_paid - stage.processing_charge
            if stage == self:
                break
        if self.transfer and self.amount_paid > 0:
            return "Transfer In"
        elif self.transfer and self.amount_paid < 0:
            return "Transfer Out"
        elif self.completed and sum_to_point >= self.__parent__.item_total:
            return "Paid"
        elif self.completed and self.amount_paid < self.amount_remaining:
            return "Partial Payment"
        elif self.cashed:
            return "Cashed"
        elif self.received and not self.cashed:
            return "Received"
        elif most_recent:
            return "Pending"
        else:
            return "Method Changed"


class PaymentMethod(Persistent):
    name = None
    short_name = None
    description = None
    customer_description = None
    settings = None
    enabled = False
    public = True
    deadlined = False
    groups = None
    # Dict maps plain text names for properties to their keys
    transaction_properties = None

    def __init__(self):
        self.name = "New Method"
        self.short_name = "New Method"
        self.description = ""
        self.__name__ = Coding().generateUniqueCode(short=True,withdash=False)
        self.settings = PersistentMapping()
        self.enabled = False
        self.public = True
        self.deadlined = False
        self.transaction_properties = PersistentMapping()
        self.groups = PersistentList()

    @property
    def customer_description(self):
        if not PROP.PAYMENT_METHOD_DESCRIPTION in self.settings:
            return ""
        else:
            return self.settings[PROP.PAYMENT_METHOD_DESCRIPTION].value

    def get_value(self, key):
        if not key in self.settings:
            return None
        else:
            return self.settings[key].value

    def update_value(self, key, new_value):
        if not key in self.settings:
            return False
        else:
            self.settings[key].update_value(new_value)
            return True


class PaymentProperty(Persistent):
    name = None
    description = None
    confidential = False # Whether to disguise or not - i.e API keys
    percentage = False
    monetary = False
    long_value = False
    value = None

    def __init__(self, key=Coding().generateUniqueCode(short=True,withdash=False), name="New Property", description="", confidential=False, percentage=False, value="-", parent=None, monetary=False):
        self.__name__ = key
        self.name = name
        self.description = description
        self.confidential = confidential
        self.percentage = percentage
        self.monetary = monetary
        self.long_value = False
        self.value = value
        self.__parent__ = parent

    @property
    def display_value(self):
        if self.confidential:
            return "********"
        elif self.percentage:
            return 100*float(self.value)
        elif self.monetary:
            return "{0:.2f}".format(self.value/100.0)
        else:
            return self.value

    def update_value(self, new_value):
        # Deal with percentages
        if self.percentage:
            perc_value = float(new_value) / 100.0
            if perc_value > 1.0 or perc_value < 0.0:
                return False
            else:
                self.value = perc_value
                return True
        elif self.confidential and "*" in new_value:
            return True
        elif self.monetary:
            pennie_value = int(float(new_value) * 100.0) # Store as pennies
            if pennie_value < 0:
                return False
            else:
                self.value = pennie_value
                return True
        # Otherwise just store
        else:
            self.value = new_value
            return True
