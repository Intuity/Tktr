from pyramid.view import view_config

from ticketing.models import Ticketing
from ticketing.api.api_baseview import APIBaseView

class APIRoot(APIBaseView):

    @view_config(
        route_name="api_root",
        context=Ticketing,
        permission="public",
        renderer="json"
    )
    def api_root_view(self):
        return {
            "api_status":       "available",
            "api_version":      1.0,
            "authenticated":    self.is_authenticated
        }
