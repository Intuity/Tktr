from datetime import datetime
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config
from random import randint

from ticketing.boxoffice.models import TicketPool, TicketType, TicketAddon, Ticket, Payment, PaymentStage
from ticketing.macros.baselayout import BaseLayout

class AdminTests(BaseLayout):

    @view_config(
        route_name="tests_page",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/tests.pt"
    )
    @view_config(
        route_name="tests_root",
        context="ticketing.models.Ticketing",
        permission="admin",
        renderer="templates/tests.pt"
    )
    def tests_view(self):
        return {}

    @view_config(
        route_name="tests_setup_tickets",
        context="ticketing.models.Ticketing",
        permission="admin"
    )
    def setup_tickets_test(self):
        # Get all group keys
        group_keys = self.request.root.groups.keys()
        for i in range(1, 10):
            pool = TicketPool()
            pool.__parent__ = self.request.root
            pool.name = "tick_pool_" + str(i)
            ticktype = TicketType(name="Type %i" % i, 
                                description="Description for type %i" % i, 
                                cost=int(8000 + 1000 * i))
            ticktype.__parent__ = pool
            if (i % 2) == 0:
                ticktype.purchase_limit = 5
            pool.tick_type = ticktype
            # Add the valid purchasers
            for key in group_keys:
                pool.groups.append(key)
            self.request.root.ticket_pools[pool.__name__] = pool
            # Now need to issue a load of tickets to the pool
            for i in range(50 + i * 10):
                new_tick = Ticket()
                new_tick.__parent__ = pool
                new_tick.tick_type = ticktype
                pool.tickets.append(new_tick)
            ticktype.total_released = len(pool.tickets)
        self.request.session.flash("Test ticket types setup successfully!", "info")
        return HTTPFound(location=self.request.route_path('tests_page'))

    @view_config(
        route_name="tests_setup_payments",
        context="ticketing.models.Ticketing",
        permission="admin"
    )
    def setup_payments_test(self):
        counting = 0
        for key in self.request.root.ticket_pools:
            pool = self.request.root.ticket_pools[key]
            ticks_left = len(pool.tickets)
            while (ticks_left > 0):
                # Whilst tickets are left, purchase random quantities of tickets
                payment = Payment()
                payment.owner = self.user
                payment.__parent__ = self.user
                
                stage = PaymentStage()
                stage.__parent__ = payment
                stage.stage_owner = self.user.__name__
                stage.date = datetime.now()
                stage.method = ["banktransfer", "cheque", "stripe", "collegebill"][counting % 4]
                if stage.method == "stripe":
                    stage.method_properties["last_four"] = "1234"
                    stage.method_properties["ref_code"] = "TESTINGSTRIPEREFCODE"
                counting += 1
                payment.history.append(stage)
                
                # To issue
                total_to_issue = randint(1,10)
                if total_to_issue > ticks_left:
                    total_to_issue = ticks_left
                ticks_left -= total_to_issue
                for i in range(0,total_to_issue):
                    tick = pool.tickets[0]
                    payment.tickets.append(tick)
                    self.user.tickets.append(tick)
                    pool.tickets.remove(tick)
                    tick.__parent__ = tick.owner = self.user
                    tick.guest_info = self.user.profile
                    tick.issue_date = datetime.now()
                    tick.payment = payment
                    self.user.total_tickets += 1
                    
                # Enter a certain amount of payment
                stage.amount_paid = (counting % 3) * 0.5 * payment.total
                if stage.amount_paid > 0:
                    stage.received = stage.cashed = stage.completed = True
                    
                # If the payment calculates it has been paid then add date
                if payment.paid:
                    payment.completed_date = datetime.now()
                elif stage.amount_paid > 0:
                    # Append a second blank payment stage on
                    stage_2 = PaymentStage()
                    stage_2.__parent__ = payment
                    stage_2.stage_owner = self.user.__name__
                    stage_2.date = datetime.now()
                    stage_2.method = ["banktransfer", "cheque", "collegebill"][counting % 3]
                    payment.history.append(stage_2)
                    
                self.user.payments.append(payment)
                self.request.root.payments[payment.__name__] = payment
        self.request.session.flash("Test payments setup successfully!", "info")
        return HTTPFound(location=self.request.route_path('tests_page'))
