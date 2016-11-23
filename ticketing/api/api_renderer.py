import json
import time

class APIRenderer(object):

    def __init__(self, info):
        pass

    def __call__(self, value, system):
        request = system.get("request")
        # Set the content type
        if request is not None:
            response = request.response
            content_type = response.content_type
            if content_type == response.default_content_type:
                response.content_type = 'application/json'
        # Add some extra parameters to the response
        value["method"] = request.matched_route.name
        if "error" not in value or value["error"] == None:
            value["result"] = "success"
        else:
            value["result"] = "error"
        value["date"] = int(round(time.time() * 1000.0))
        return json.dumps(value, sort_keys=True)
