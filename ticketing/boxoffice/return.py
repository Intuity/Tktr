# Return ticket views
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from ticketing.macros.baselayout import BaseLayout
from ticketing.models import Ticketing

class ReturnTickets(BaseLayout):

    @view_config(
        route_name="return_tickets", 
        context=Ticketing, 
        permission="basic", 
        renderer="templates/return.pt"
    )
    def return_view(self):
        tick_id = self.request.matchdict["tick_id"]
        user = self.user
        ticket = None
        # Find ticket
        for tick in user.tickets:
            if tick.__name__ == tick_id:
                ticket = tick
                break
        # If not found, user doesn't own it!
        if ticket == None:
            self.request.session.flash("The requested ticket does not exist.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Check this is not a purchased ticket
        if ticket.payment.paid:
            self.request.session.flash("The requested ticket has already been paid for and cannot be returned.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # If this is their ticket, check they have no others
        if ticket.guest_info == ticket.owner.profile and len(user.tickets) > 1 and self.guest_details_required:
            self.request.session.flash("You may not return your own ticket whilst you still hold guest tickets.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        return {
            "ticket" : ticket,
        }

    @view_config(
        route_name="return_tickets",
        context=Ticketing,
        permission="basic",
        request_method="POST"
    )
    def return_view_do(self):
        tick_id = self.request.matchdict["tick_id"]
        user = self.user
        ticket = None
        # Find ticket
        for tick in user.tickets:
            if tick.__name__ == tick_id:
                ticket = tick
                break
        # If not found, user doesn't own it!
        if ticket == None:
            self.request.session.flash("The requested ticket does not exist.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Check this is not a purchased ticket
        if ticket.payment.paid:
            self.request.session.flash("The requested ticket has already been paid for and cannot be returned.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # If this is their ticket, check they have no others
        if ticket.guest_info == ticket.owner.profile and len(user.tickets) > 1 and self.guest_details_required:
            self.request.session.flash("You may not return your own ticket whilst you still hold guest tickets.", "error")
            return HTTPFound(location=self.request.route_path("user_profile"))
        # Return the ticket to the pool
        pool = ticket.tick_type.__parent__
        payment = ticket.payment
        # Release all addons
        ticket.release_addons()
        # Remove from the user
        self.user.tickets.remove(ticket)
        self.user.total_tickets -= 1
        payment.tickets.remove(ticket)
        pool.tickets.append(ticket)
        ticket.__parent__ = pool
        # Blank out user details
        ticket.owner = None
        ticket.payment = None
        ticket.issue_date = None
        ticket.guest_info = None
        # Check if the payment is now empty, and close it if so
        if len(payment.tickets) == 0:
            self.user.payments.remove(payment)
            self.request.root.payments.pop(payment.__name__, None)
        self.request.session.flash("The ticket has been successfully returned.", "info")
        return HTTPFound(location=self.request.route_path("user_profile"))
