import jwt
import time

class APIAuthenticationException(Exception):
    pass

class APIPrivilegeException(Exception):
    pass

class APIBaseView(object):

    is_authenticated = None
    auth_user = None
    auth_privilege = None
    token_expiry_date = None

    def __init__(self, context, request):
        self.context = context
        self.request = request
        # Set auth variables locally
        self.is_authenticated = False
        self.auth_user = None
        self.auth_privilege = None
        self.token_expiry_date = 0
        # Run authentication check
        self.check_authentication()

    def check_authentication(self):
        if self.is_authenticated == True:
            return self.is_authenticated
        try:
            self.authenticate_user()
            return self.is_authenticated
        except APIAuthenticationException:
            return self.is_authenticated
        except Exception:
            return self.is_authenticated

    def verify_privileges(self, required_level):
        if not self.is_authenticated or self.auth_user == None or self.auth_privilege == None:
            raise APIAuthenticationException("No user is authenticated")
        # Verify the user's privilege level is at or above the required level
        levels = ["public","raven","basic","staff","committee","admin"]
        try:
            if levels.index(self.auth_privilege) >= levels.index(required_level):
                return True
            else:
                raise APIPrivilegeException("Insufficient privilege level")
        except APIPrivilegeException as e:
            raise e # Pass it upwards
        except ValueError:
            raise APIPrivilegeException("Invalid privilege level presented")

    def authenticate_user(self):
        if "HTTP_AUTHORIZATION" not in self.request.headers.environ or self.request.headers.environ["HTTP_AUTHORIZATION"] == None:
            self.is_authenticated = False
            self.auth_user = None
            self.auth_privilege = None
            self.token_expiry_date = 0
            raise APIAuthenticationException("Authorization headers not set in request")
        # Attempt to decode the request
        try:
            decoded = jwt.decode(
                self.request.headers.environ["HTTP_AUTHORIZATION"],
                self.request.registry._settings["api.session_secret"],
                algorithms=['HS512']
            )
            # Get user
            if "user_id" not in decoded or decoded["user_id"] not in self.request.root.users:
                self.is_authenticated = False
                self.auth_user = None
                self.auth_privilege = None
                self.token_expiry_date = 0
                raise APIAuthenticationException("Malformed authorization header provided")
            user = self.request.root.users[decoded["user_id"]]
            token_expiry = int(self.request.registry._settings["api.session_expiry"])
            # Check token expiry
            if (
                user.api_token != self.request.headers.environ["HTTP_AUTHORIZATION"] or
                (int(decoded["auth_date"]) + token_expiry) < int(round(time.time() * 1000.0))
                ):
                raise APIAuthenticationException("Authentication token has expired")
            else:
                self.is_authenticated = True
                self.auth_user = user
                self.token_expiry_date = int(decoded["auth_date"]) + token_expiry
                # Lookup and store the users privilege level
                self.auth_privilege = user.__parent__.privileges[0]
                return True
        except APIAuthenticationException as e:
            self.is_authenticated = False
            self.auth_user = None
            self.auth_privilege = None
            self.token_expiry_date = 0
            raise e # Pass this upwards!
        except Exception:
            self.is_authenticated = False
            self.auth_user = None
            self.auth_privilege = None
            self.token_expiry_date = 0
            raise APIAuthenticationException("Invalid authorization header provided")
