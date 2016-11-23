from datetime import datetime
import json
from .models import QueueItem
from pyramid.httpexceptions import HTTPFound
from pyramid.response import Response
from pyramid.security import remember
from pyramid.view import view_config
from .queue import Queue
from ticketing.macros.baselayout import BaseLayout
from ticketing.models import PROP_KEYS

class QueueViews(BaseLayout):

    @view_config(route_name="queue", permission="public", renderer="templates/queue.pt")
    def queue_view(self):
        if not self.request.root.properties[PROP_KEYS.QUEUE_ENABLED]:
            return HTTPFound(location=self.request.route_path("welcome"))
        queue_item = None
        # Get or create the queue item if required
        if not "queue_id" in self.request.session or self.queue_item == None:
            queue_item = QueueItem()
            self.request.root.queue.append(queue_item)
            queue_item.__parent__ = self.request.root.queue
            # Register it
            self.request.session["queue_id"] = queue_item.__name__
            header = remember(self.request, str(queue_item.__name__))
            return HTTPFound(location=self.request.route_path('queue'), headers=header)
        # Return the current queue position
        return {
            "position": Queue(self.request).position(self.request.session["queue_id"]),
        }

    @view_config(route_name="queue_information", permission="public")
    def queue_information_view(self):
        # Get stock check
        tick_pools = self.request.root.ticket_pools.values()
        ticket_stock = sum([len(x.tickets) for x in tick_pools])
        stock_list = {}
        """for pool in tick_pools:
            for addon in pool.tick_type.addons.values():
                if addon.name in stock_list:
                    stock_list["Addon: " + addon.name] += addon.remaining
                else:
                    stock_list["Addon: " + addon.name] = addon.remaining"""
        stock_list["All Tickets"] = ticket_stock
        return_list = {}
        for key in stock_list:
            number = stock_list[key]
            if number <= 0:
                return_list[key] = "Out of Stock"
            elif number < 20:
                return_list[key] = "Only %i left" % number
            else:
                return_list[key] = "Available"
        # Get queue position
        position = Queue(self.request).position(self.request.session["queue_id"])
        total_slots = self.request.root.properties[PROP_KEYS.CONCURRENT_NUM]
        open_slots = total_slots - len(self.request.root.active)
        position_string = ""
        if position == 0:
            if open_slots > 0:
                position_string = "ready"
            else:
                position_string = "waiting"
        else:
            # Check there aren't spaces to fill
            if position < open_slots:
                position_string = "ready"
            else:
                position_string = str(position)
        # Put together a response
        response_dict = {
            "position": position_string,
            "stock": return_list,
        }
        response = Response("application/json")
        response.body = json.dumps(response_dict)
        return response

    @view_config(route_name="queue_front", permission="public")
    def at_front_view(self):
        if not self.request.root.properties[PROP_KEYS.QUEUE_ENABLED]:
            return HTTPFound(location=self.request.route_path("welcome"))
        # Find open slots
        total_slots = self.request.root.properties[PROP_KEYS.CONCURRENT_NUM]
        open_slots = total_slots - len(self.request.root.active)
        # Continue
        position = Queue(self.request).position(self.request.session["queue_id"])
        if position < open_slots:
            queue_id = self.request.session["queue_id"]
            items = [x for x in self.request.root.queue if x.queue_id == queue_id]
            if len(items) <= 0:
                self.request.session.flash("You are not yet at the front of the queue, please wait.", "info")
                return HTTPFound(location=self.request.route_path("queue"))
            else:
                # Check if there are too many people in "active" state
                if open_slots <= 0:
                    return HTTPFound(location=self.request.route_path("queue"))
                # Shift the person from being in queue to being active
                item = items[0]
                self.request.root.queue.remove(item)
                self.request.root.active[item.__name__] = item
                item.__parent__ = self.request.root.active
                item.queue_exit_time = item.purchase_entry_time = datetime.now()
                # Make active
                self.request.session.pop("queue_id", None)
                self.request.session["active_id"] = item.__name__
                header = remember(self.request, str(item.__name__))
                return HTTPFound(location=self.request.route_path('welcome'), headers=header)
        else:
            self.request.session.flash("You are not yet at the front of the queue, please wait.", "info")
            return HTTPFound(location=self.request.route_path("queue"))


    @view_config(route_name="timeleft", permission="public")
    def timeleft_view(self):
        if not self.request.root.properties[PROP_KEYS.QUEUE_ENABLED]:
            return 1
        response = Response("text/plain")
        queue = Queue(self.request)
        response.body = str(queue.purchase_time_left())
        return response

    @view_config(
        route_name="purchase_timeout", 
        renderer="templates/timeout.pt", 
        permission="public"
    )
    def timeout_view(self):
        # Make sure there are no bits of queue stuff hanging around
        if "active_id" in self.request.session:
            Queue(self.request).remove_from_active(self.request.session["active_id"])
        elif "queue_id" in self.request.session:
            Queue(self.request).remove_from_active(self.request.session["queue_id"])
        # Make sure no cached values
        self.request.session.pop("queue_id", None)
        self.request.session.pop("active_id", None)
        return {}
