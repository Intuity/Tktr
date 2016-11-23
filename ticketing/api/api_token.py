import jwt
import logging
from pyramid.view import view_config
import time

from ticketing.models import Ticketing
from ticketing.api.api_baseview import APIBaseView, APIAuthenticationException
from ticketing.boxoffice.coding import Coding

logging = logging.getLogger("ticketing")

class APITokenManagement(APIBaseView):

    @view_config(
        route_name="api_token_issue",
        context=Ticketing,
        permission="public",
        renderer="api_renderer"
    )
    def api_token_issue_view(self):
        if  (
            "user_id" not in self.request.session or 
            self.request.session["user_id"] == None or 
            self.request.session["user_id"] not in self.request.root.users or 
            self.request.root.users[self.request.session["user_id"]] == None
            ):
            return {
                "error": "No valid authenticated session present, cannot issue token."
            }
        else:
            user = self.request.root.users[self.request.session["user_id"]]
            coder = Coding()
            token = jwt.encode({
                'user_id':      user.__name__,
                'username':     user.username,
                'auth_date':    str(int(round(time.time() * 1000.0))),
                'unique_id':    coder.generateUniqueCode()
            }, 
            self.request.registry._settings["api.session_secret"], 
            algorithm='HS512')
            user.api_token = token
            logging.info("API: Issued authentication token to %s" % user.username)
            return {
                "token": token
            }

    @view_config(
        route_name="api_token_verify",
        context=Ticketing,
        permission="public",
        renderer="api_renderer"
    )
    def api_token_verify_view(self):
        # Attempt to decode the request
        try:
            # Run the authentication
            self.authenticate_user()
            if self.is_authenticated:
                logging.info("API: Validated authentication token for %s" % self.auth_user.username)
                return {
                    "token_status": "valid",
                    "expiry_date": self.token_expiry_date
                }
            else:
                return {
                    "token_status": "invalid",
                    "error": "Token is invalid"
                }
        except APIAuthenticationException as e:
            logging.error("API: Failed to validate authentication token: %s" % str(e))
            return {
                "token_status": "invalid",
                "error": str(e)
            }
        except Exception:
            logging.error("API: Failed to validate authentication token: %s" % str(e))
            return {
                "error": "An unexpected error occured"
            }
