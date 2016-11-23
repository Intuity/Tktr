from pyramid.httpexceptions import HTTPFound
from pyramid.security import remember, forget
from pyramid.view import view_config
from datetime import datetime

from ticketing.macros.baselayout import BaseLayout
from ticketing.manage.sales import Sales
from ticketing.models import salt_password
from ticketing.boxoffice.issue import Issuer

class Admin(BaseLayout):

    @view_config(
        route_name="admin_login",
        context="ticketing.models.Ticketing",
        permission="public",
        renderer="templates/login.pt"
    )
    def login_view(self):
        # Allow the username field to be pre-entered
        prep_user = ""
        if "user" in self.request.GET:
            prep_user = self.request.GET["user"]
        # Deal with an actual login
        if 'submit' in self.request.POST:
            try:
                username = self.request.POST["username"].lower()
                password = self.request.POST["password"]
                user_key = [x for x in self.context.users if self.context.users[x].username == username][0]
                user = self.context.users[user_key]
                # Check group
                if not "admin" in user.__parent__.privileges and not "committee" in user.__parent__.privileges:
                    return {
                        "error": "validation_error",
                        "prep_user": username
                    }
                # Check credentials
                elif username == user.username and user.password == salt_password(password, user.password_salt):
                    self.request.session["user_id"] = user.__name__
                    header = remember(self.request, str(user.__name__))
                    return HTTPFound(location=self.request.route_path("admin_summary"), headers=header)
                else:
                    return {
                        "error": "validation_error",
                        "prep_user": username
                    }
            except Exception:
                return {
                    "error": "validation_error",
                    "prep_user": ""
                }
        
        return {
            "prep_user": prep_user
        }

    @view_config(
        route_name="admin_logout",
        context="ticketing.models.Ticketing",
        permission="committee",
    )
    def logout_view(self):
        header = forget(self.request)
        self.request.session.pop("user_id", None)
        return HTTPFound(location=self.request.route_path("admin_login"), headers=header)

    @view_config(
        route_name="admin_catch",
        context="ticketing.models.Ticketing"
    )
    def catch_view(self):
        if "user_id" in self.request.session:
            user_id = self.request.session["user_id"]
            user = self.request.root.users[user_id]
            if "admin" in user.__parent__.privileges or "committee" in user.__parent__.privileges:
                return HTTPFound(location=self.request.route_path("admin_summary"))
        return HTTPFound(location=self.request.route_path("admin_login"))

    @view_config(
        route_name="admin_summary",
        context="ticketing.models.Ticketing",
        permission="committee",
        renderer="templates/summary.pt"
    )
    def summary_view(self):
        users = self.request.root.users.values()
        # Fix negative ticket counts
        if "action" in self.request.GET:
            if self.request.GET["action"] == "fixnegatives":
                negative = [x for x in self.request.root.users.values() if x.total_tickets < 0]
                for user in negative:
                    user.total_tickets = len(user.tickets)
                self.request.session.flash("Fixed negative counts on the %i usernames: %s" % (len(negative),[x.username for x in negative]), "info")
            elif self.request.GET["action"] == "cleardead":
                # Check for tickets released but not attached to a payment
                issue = Issuer(self.request.root)
                count = 0;
                for user in users:
                    ticks = [x for x in user.tickets if x.payment == None]
                    for tick in ticks:
                        # Don't bounce tickets out if only allocated in the last five minutes
                        if (datetime.now() - tick.issue_date).total_seconds() > 300:
                            issue.returnTicket(tick)
                            count += 1
        sales = Sales(None, None)
        lc_data = sales.line_graph_data(self.request.root)
        json_data = sales.json_line_graph_data(self.request.root, data=lc_data)
        lc_min_data = sales.minute_line_graph_data(self.request.root)
        json_lc_min = sales.json_line_graph_data(self.request.root, data=lc_min_data)
        # User Statistics
        users = self.request.root.users.values()
        # Return stats
        user_stats = {
            "total": len(users),
            "withtickets": len([x for x in users if len(x.tickets) > 0]),
            "undergrad": len([x for x in users if x.profile != None and x.profile.grad_status == "undergrad"]),
            "postgrad": len([x for x in users if x.profile != None and x.profile.grad_status == "postgrad"]),
            "fellow": len([x for x in users if x.profile != None and x.profile.grad_status == "fellow"]),
            "alumni": len([x for x in users if x.profile != None and x.profile.grad_status == "alumni"]),
        }
        # Get all of the ticket types
        totalreleased = purchased = remaining = revenue = 0
        for tick_pool in self.request.root.ticket_pools.values():
            tick_type = tick_pool.tick_type
            totalreleased += tick_type.total_released
            purchased += (tick_type.total_released - len(tick_pool.tickets))
            remaining += len(tick_pool.tickets)
        for payment in self.request.root.payments.values():
            revenue += payment.total
        # Ticket Statistics
        tick_stats = {
            "totalreleased": totalreleased,
            "purchased": purchased,
            "remaining": remaining,
            "revenue": revenue,
        }
        return {
            "lc_titles":    json_data["lc_titles"],
            "lc_sales":     json_data["lc_sales"],
            "lc_revenue":   json_data["lc_revenue"],
            "lc_minute_titles": json_lc_min["lc_titles"],
            "lc_minute_sales": json_lc_min["lc_sales"],
            "lc_minute_revenue": json_lc_min["lc_revenue"],
            "sales_exist":  (len(lc_data["lc_sales"]) > 0),
            # User Statistics
            "user_stats":   user_stats,
            # Ticket Statistics
            "tick_stats":   tick_stats,
        }

    @classmethod
    def notfound_view(context, request):
        return HTTPFound(location=request.route_path("admin_summary"))

    @classmethod
    def forbidden_view(context, request):
        if "user_id" in request.session:
            user_id = request.session["user_id"]
            user = request.root.users[user_id]
            if "admin" in user.__parent__.privileges or "committee" in user.__parent__.privileges:
                request.session.flash("You do not have the privileges required to access the page you requested.","error")
                return HTTPFound(location=request.route_path("admin_summary"))
        return HTTPFound(location=request.route_path("admin_login"))
