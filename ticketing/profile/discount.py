from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from ticketing.macros.baselayout import BaseLayout
from ticketing.models import Ticketing

class Discount(BaseLayout):
    
    @view_config(
        route_name="discount",
        renderer="templates/discount.pt",
        context=Ticketing,
        permission="basic"
    )
    def discount_view(self):
        discount_code = None
        if "submit" in self.request.POST:
            discount_code = (self.request.POST["discount_code"] if "discount_code" in self.request.POST and len(self.request.POST["discount_code"]) > 0 else None)
            if discount_code == None:
                self.request.session.flash("You must enter a valid discount code before clicking 'Check Discount'.", "error")
                return {
                    "discount_code": discount_code
                }
            group = None
            for group_key in self.request.root.groups:
                test_group = self.request.root.groups[group_key]
                if test_group.access_code != None and len(test_group.access_code) > 0 and test_group.access_code == discount_code:
                    group = test_group
                    break
            if group == None:
                self.request.session.flash("The discount code entered is not valid, please check it and try again.", "error")
                return {
                    "discount_code": discount_code
                }
            # So we have found the discount group, move the user into the right group
            current = self.user.__parent__
            # De-register from one and put into the other
            group.members.append(self.user)
            self.user.__parent__ = group
            current.members.remove(self.user)
            # Clear the filter on any groups that have this user
            for grp in self.request.root.groups.values():
                if self.user.username in grp.user_filter:
                    grp.user_filter.remove(self.user.username)
            self.request.session.flash("Discount code applied successfully.", "info")
            return HTTPFound(location=self.request.route_path('user_profile'))
        return {
            "discount_code": discount_code
        }