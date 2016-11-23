def includeme(config):
    config.add_route("queue", "/queue")
    config.add_route("queue_information", "/queue_information")
    config.add_route("queue_front", "/queue_front")
    config.add_route("timeleft", "/timeleft")
    config.add_route("purchase_timeout", "/timedout")
