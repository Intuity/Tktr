def includeme(config):
    config.add_route("api_root", "/api")
    # Authentication token management
    # - Login views
    config.add_route("api_login", "/api/login")
    config.add_route("api_login_raven", "/api/login/raven")
    config.add_route("api_login_raven_return", "/api/login/return")
    # - Token issue and management
    config.add_route("api_token_issue", "/api/token/issue")
    config.add_route("api_token_verify", "/api/token/verify")
    # Check-in functionality
    config.add_route("api_checkin_query", "/api/checkin/query")
    config.add_route("api_checkin_enact", "/api/checkin/enact")
