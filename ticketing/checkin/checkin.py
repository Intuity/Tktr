from pyramid.view import view_config
from ticketing.models import Ticketing
from ticketing.macros.baselayout import BaseLayout
from pyramid.httpexceptions import HTTPFound

class CheckInViews(BaseLayout):

    @view_config(
        route_name='checkin',
        context=Ticketing,
        permission='staff',
        renderer='templates/lookup.pt'
    )
    def lookup_view(self):
        if not self.checkin_active:
            self.request.session.flash("Check-in is not currently available as it has been disabled in settings.")
            return HTTPFound(location=self.request.route_path('user_profile'))
        if 'submit' in self.request.POST:
            # Get parameters for lookup
            filter_type  = self.request.POST['filtertype'].lower() if 'filtertype' in self.request.POST else None
            filter_value = self.request.POST['filtervalue'].lower() if 'filtervalue' in self.request.POST and len(self.request.POST['filtervalue'].strip()) > 0 else None
            if None in [filter_type, filter_value]:
                self.request.session.flash('Please select a filter type and end a valid search criteria', 'error')
                return {
                    "filtertype": filter_type,
                    "filtervalue": filter_value
                }
            # Lookup tickets matching the query provided
            payments = []
            tickets  = []
            # Different lookups based on the filter selected
            if filter_type == 'payment_id':
                payments = [x for x in self.request.root.payments.values() if filter_value in x.__name__.lower()]
            elif filter_type == 'ticket_id':
                payments = [x for x in self.request.root.payments.values() if filter_value in [y.__name__.lower() for y in x.tickets]]
            elif filter_type == 'ownercrsid':
                for tkt_set in [x.tickets for x in self.request.root.users.values() if x.profile != None and x.profile.crsid != None and filter_value in x.profile.crsid.lower()]:
                    tickets += tkt_set
            elif filter_type == 'ownername':
                for tkt_set in [x.tickets for x in self.request.root.users.values() if x.profile != None and x.profile.fullname != None and filter_value in x.profile.fullname.lower()]:
                    tickets += tkt_set
            elif filter_type == 'owneremail':
                for tkt_set in [x.tickets for x in self.request.root.users.values() if x.profile != None and x.profile.email != None and filter_value in x.profile.email.lower()]:
                    tickets += tkt_set
            elif filter_type == 'ownerusername':
                for tkt_set in [x.tickets for x in self.request.root.users.values() if filter_value in x.username.lower()]:
                    tickets += tkt_set
            elif filter_type == 'guestname':
                payments = [x for x in self.request.root.payments.values() if len([y.guest_info.fullname.lower() for y in x.tickets if y.guest_info != None and y.guest_info.fullname != None and filter_value in y.guest_info.fullname.lower()]) > 0]
            elif filter_type == 'guestcrsid':
                payments = [x for x in self.request.root.payments.values() if len([y.guest_info.fullname.lower() for y in x.tickets if y.guest_info != None and y.guest_info.crsid != None and filter_value in y.guest_info.crsid.lower()]) > 0]
            elif filter_type == 'guestemail':
                payments = [x for x in self.request.root.payments.values() if len([y.guest_info.fullname.lower() for y in x.tickets if y.guest_info != None and y.guest_info.email != None and filter_value in y.guest_info.email.lower()]) > 0]
            # Exclude tickets without payments, or with incomplete payments
            tickets = [x for x in tickets if x.payment != None and x.payment.paid == True]
            # Extract the payments from the tickets
            for tkt in tickets:
                if not tkt.payment.__name__ in [x.__name__ for x in payments]:
                    payments.append(tkt.payment)
            # Remove any payments with empty ticket lists or no payment
            payments = [x for x in payments if len(x.tickets) > 0 and x.paid == True]
            # Return the tickets to be rendered
            return {
                "payments": payments,
                "filtertype": filter_type,
                "filtervalue": filter_value
            }
        return {}
