
def includeme(config):
    config.add_route("setup", "/setup")
    config.add_route("setup_stageone", "/setup/one")
    config.add_route("setup_stagetwo", "/setup/two")
    config.add_route("setup_stagethree", "/setup/three")
    config.add_route("setup_done", "/setup/done")