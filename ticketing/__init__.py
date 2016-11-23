from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
from pyramid_beaker import session_factory_from_settings
from pyramid.config import Configurator
from pyramid_zodbconn import get_connection
import logging

from .models import appmaker


def checkGroups(userid, request):
    # Check for ticketing timeouts
    # Permissions checks
    if "raven" in request.session:
        return ["group:raven"]
    elif "user_id" in request.session:
        try:
            user = request.root.users[request.session['user_id']]
            return ["group:" + user.__parent__.privileges[0]]
        except Exception, e:
            logging.error("Couldn't find user %s: %s" % (request.session["user_id"], e))
            return ["group:public"]
    return ["group:public"]


def root_factory(request):
    conn = get_connection(request)
    return appmaker(conn.root())


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    session_factory = session_factory_from_settings(settings)
    config = Configurator(
        root_factory=root_factory,
        session_factory=session_factory,
        settings=settings,
    )
    config.add_static_view('static', 'static', cache_max_age=3600)
    config.include('ticketing.setup')
    config.include('ticketing.mainviews')
    config.include('ticketing.raven')
    config.include('ticketing.profile')
    config.include('ticketing.boxoffice')
    config.include('ticketing.queue')
    config.include('ticketing.manage', route_prefix="/admin")
    config.include('ticketing.checkin')
    config.add_renderer('api_renderer', 'ticketing.api.api_renderer.APIRenderer')
    config.include('ticketing.api')
    config.add_route("admin_catch","/admin")
    
    # Add authentication policies
    authentication_policy = AuthTktAuthenticationPolicy('ticketing', callback=checkGroups, hashalg='sha512')
    authorization_policy = ACLAuthorizationPolicy()
    config.set_authentication_policy(authentication_policy)
    config.set_authorization_policy(authorization_policy)
    config.set_default_permission("public")

    # Scan for views
    config.scan()
    
    return config.make_wsgi_app()
