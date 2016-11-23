from random import randrange
from datetime import datetime
from persistent.mapping import PersistentMapping
from ticketing.models import PROP_KEYS as PROP
from ticketing.boxoffice.models import Payment

import logging
logging = logging.getLogger("ticketing")

class OutOfStock(Exception):
    pass

class InvalidType(Exception):
    pass

class InvalidUser(Exception):
    pass

class InvalidTicket(Exception):
    pass

class UserAtLimit(Exception):
    pass

class UserAtTypeLimit(Exception):
    tick_type = ""
    limit = 0

class InvalidOrder(Exception):
    pass

class MultipleExclusives(Exception):
    pass

class IssuanceFailed(Exception):
    pass

class Issuer(object):
    
    def __init__(self, root_context):
        self.root = root_context
    
    def issueTickets(self, user_id, ticket_type, quantity):
        if quantity <= 0:
            raise InvalidOrder("Ordering %i tickets is invalid" % quantity)
        if not user_id in self.root.users:
            raise InvalidUser("User %s does not exist" % user_id)
        user = self.root.users[user_id]
        # Check system wide max limits
        if self.root.properties[PROP.LIMIT_ENABLED] and user.total_tickets >= self.root.properties[PROP.MAX_TICKETS]:
            raise UserAtLimit("User already has %i tickets" % user.total_tickets)
        elif self.root.properties[PROP.LIMIT_ENABLED] and (user.total_tickets + quantity) > self.root.properties[PROP.MAX_TICKETS]:
            raise UserAtLimit("Purchasing %i will put user over limit" % quantity)
        try:
            tick_pool = [x for x in self.root.ticket_pools.values() if x.tick_type.__name__ == ticket_type][0]
        except Exception, e:
            raise InvalidType("Ticket type %s does not exist" % ticket_type)
        # Check ticket type max limit
        if tick_pool.tick_type.purchase_limit > 0:
            of_type = [x for x in user.tickets if x.tick_type.__name__ == tick_pool.tick_type.__name__]
            if (len(of_type) + quantity) > tick_pool.tick_type.purchase_limit:
                e = UserAtTypeLimit("User already has %i of limited type %s" % (len(of_type), tick_pool.tick_type.__name__))
                e.tick_type = tick_pool.tick_type.name
                e.limit = tick_pool.tick_type.purchase_limit
                raise e
        # Check the group permissions allow us to issue this ticket
        if user.__parent__.__name__ not in tick_pool.groups: raise InvalidType("Ticket type is not available for this group!")
        # Check quantities
        if len(tick_pool.tickets) < quantity:
            raise OutOfStock("There is not enough stock (%i) left in pool %s for purchase of %i tickets" % 
                        (len(tick_pool.tickets), tick_pool.tick_type.name, quantity))
        try:
            # Ok now we have cleared all the checks, lets push on to allocation
            our_tick_pos = []
            full_range = len(tick_pool.tickets)
            for i in range(quantity):
                index = -1
                tries = 0
                while (index == -1 or index in our_tick_pos): # Try to reduce collisions a bit
                    index = randrange(full_range)
                    tries += 1
                    if tries > 10: # If it gets ridiculous then shortcut
                        our_tick_pos = range(quantity)
                        break
                # Also need to check for tries here, otherwise if we just allocated a range
                # We are going to end up appending extra values we don't need!
                if tries > 10:
                    break
                our_tick_pos.append(index)
            # Pop the allocated tickets back out
            got_ticks = []
            for tick_pos in our_tick_pos:
                tick = tick_pool.tickets[tick_pos]
                user.tickets.append(tick)
                got_ticks.append(tick)
                tick.__parent__ = user
                tick.owner = user
                tick.issue_date = datetime.now()
                # Don't increment total tickets yet as just a provisional issuance
            # Remove the allocated tickets from the overall pool
            for tick in got_ticks:
                tick_pool.tickets.remove(tick)
            logging.info(user_id + ": issued %i session tickets out of requested %i" % (len(got_ticks), quantity))
        except Exception, e:
            logging.error(user_id + ": failed to issue tickets to user: %s" % e)
            raise IssuanceFailed("Failed to issue tickets")
        return True

    def issueAddon(self, user_id, ticket, addon_id):
        if not user_id in self.root.users:
            raise InvalidUser("User %s does not exist" % user_id)
        user = self.root.users[user_id]
        if not ticket in user.tickets:
            raise InvalidTicket("Ticket %s does not exist" % ticket.__name__)
        # Check this addon exists
        if not addon_id in ticket.tick_type.addons:
            raise InvalidType("Addon %s does not exist under ticket %s" % (addon_id, ticket.__name__))
        addon = ticket.tick_type.addons[addon_id]
        # Check the addon stock
        if addon.remaining <= 0:
            raise OutOfStock("Addon %s is out of stock" % addon_id)
        # Check this ticket hasn't already got this add-on
        if ticket.addons == None:
            ticket.addons = PersistentMapping()
        elif addon_id in ticket.addons:
            raise InvalidOrder("Ticket %s already has add-on %s" % (ticket.__name__, addon_id))
        # Check if this type is exclusive, if it is then check exclusitivity is OK
        if addon.exclusive:
            for chk_addon in ticket.addons.values():
                if chk_addon.exclusive:
                    raise MultipleExclusives("Ticket %s already has an exclusive add-on" % ticket.__name__)
        # Ready to now issue the addon
        ticket.addons[addon.__name__] = addon
        addon.allocated.append(ticket)

    def returnUnpurchasedTickets(self, user_id):
        if not user_id in self.root.users:
            logging.info(user_id + " user does not exist")
            raise InvalidUser("User %s does not exist" % user_id)
        user = self.root.users[user_id]
        inv_tickets = [x for x in user.tickets if x.payment == None]
        for ticket in inv_tickets:
            self.returnTicket(ticket)

    def returnTicket(self, ticket):
        # Get pool and user
        pool_search = [x for x in self.root.ticket_pools.values() if x.tick_type.__name__ == ticket.tick_type.__name__]
        tick_pool = None
        if len(pool_search) > 0:
            tick_pool = pool_search[0]
        user = ticket.owner
        # Return ticket
        ticket.__parent__ = tick_pool
        if ticket.payment != None:
            user.total_tickets -= 1
        ticket.payment = None
        ticket.issue_date = None
        ticket.guest_info = None
        ticket.owner = None
        ticket.release_addons()
        user.tickets.remove(ticket)
        user.tickets._p_changed = True
        if tick_pool != None:
            tick_pool.tickets.append(ticket)

    def constructPayment(self, user_id, paid=False, ref_code=None):
        if not user_id in self.root.users:
            logging.info(user_id + " user does not exist")
            raise InvalidUser("User %s does not exist" % user_id)
        user = self.root.users[user_id]
        ticks = [x for x in user.tickets if x.payment == None]
        #if self.root.properties[PROP.LIMIT_ENABLED] and (len(ticks) + user.total_tickets) > self.root.properties[PROP.MAX_TICKETS]:
        #    raise InvalidOrder("User is trying to order %i tickets, this is above the limit!" % len(ticks))
        #el
        if len(ticks) <= 0:
            logging.info(user_id + " user is trying to purchase no tickets")
            raise InvalidOrder("User is trying to purchase no tickets!")
        # First open a payment for the tickets
        payment = Payment()
        if ref_code != None:
            payment.__name__ = payment.ref_code = ref_code
        payment.owner = user
        payment.__parent__ = user
        # Shift the tickets into the payment
        for tick in ticks:
            payment.tickets.append(tick)
            tick.payment = payment
        user.total_tickets += len(payment.tickets)
        # - Note we don't add a payment stage here as that depends on payment method
        # Store
        user.payments.append(payment)
        self.root.payments[payment.__name__] = payment
        return payment

    def cancelPayment(self, ref_code, return_to_session=False):
        payment = self.root.payments[ref_code]
        user = payment.owner
        # Cancel the payment, return all tickets
        for ticket in payment.tickets:
            if return_to_session:
                ticket.payment = None
            else:
                self.returnTicket(ticket)
        user.tickets._p_changed = True
        # Remove payment from user
        user.payments.remove(payment)
        user.payments._p_changed = True
        # Remove payment from root
        self.root.payments.pop(payment.__name__, None)
        self.root.payments._p_changed = True
