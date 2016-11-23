def includeme(config):
    config.add_route("checkin","/checkin")
    config.add_route("checkin_data","/checkin/data")
    config.add_static_view("/checkin/static","static",cache_max_age=3600)