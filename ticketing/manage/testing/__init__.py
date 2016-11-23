def includeme(config):
    config.add_route("tests_page", "/")
    config.add_route("tests_setup_tickets", "/tickets")
    config.add_route("tests_setup_payments", "/payments")