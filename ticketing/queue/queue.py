# Manages the queue
from datetime import datetime, timedelta
from ticketing.boxoffice.issue import Issuer
from ticketing.models import PROP_KEYS

class Queue(object):

    last_checked = None
    last_active_check = None

    def __init__(self, request):
        self.root = request.root
        self.request = request

    def position(self, queue_id=None):
        if queue_id == None:
            if not "queue_id" in self.request.session:
                return -1
            queue_id = self.request.session["queue_id"]
        # Run timeouts check
        self.check_for_timeouts()
        # Check our status
        items = [x for x in self.root.queue if x.queue_id == queue_id]
        if len(items) <= 0:
            return -1
        elif len(items) > 0:
            # Take the earliest position in the queue - remove others
            for item in items[1:]:
                self.root.queue.remove(item)
        # Check the person in.MAX_SESSION_TIME
        items[0].last_checkin_time = datetime.now()
        return self.root.queue.index(items[0])

    def timed_out(self, active_id=None):
        # Check queue is actually enabled
        if not self.request.root.properties[PROP_KEYS.QUEUE_ENABLED]:
            return False
        # Otherwise we need to check
        return self.purchase_time_left(active_id) <= 0

    def remove_from_active(self, active_id):
        if not active_id in self.request.root.active: return
        # Get active object
        active = self.request.root.active[active_id]
        if active.user_id != None:
            # First check that the active user hasn't got multiple queue items, if so kill all but the latest
            items = [x for x in self.request.root.active.values() if x.user_id == active.user_id]
            if len(items) <= 1:
                # Clear the user's unpurchased tickets
                issue = Issuer(self.request.root)
                try:
                    issue.returnUnpurchasedTickets(active.user_id)
                except Exception:
                    self.request.session.flash("Had an issue returning unpurchased tickets, please try again.", "error")
        self.request.root.active.pop(active_id, None)

    def purchase_time_left(self, active_id=None):
        if active_id == None:
            if not "active_id" in self.request.session:
                return -1
            active_id = self.request.session["active_id"]
        # Check for active
        self.check_active()
        # Check our status
        if not active_id in self.root.active:
            self.remove_from_active(active_id)
            return -1
        # Work out time left from entry time in seconds
        try:
            item = self.root.active[active_id]
            # Don't check in for queue monitoring
            if "active_id" in self.request.session and self.request.session["active_id"] == active_id:
                item.last_checkin_time = datetime.now()
                item._p_changed = True
            expire_at = item.purchase_entry_time + timedelta(minutes=int(self.root.properties[PROP_KEYS.MAX_SESSION_TIME]))
            if datetime.now() > expire_at:
                self.remove_from_active(active_id)
                return -1
            else:
                return (expire_at - datetime.now()).seconds
        except Exception:
            self.remove_from_active(active_id)
            return -1

    def check_for_timeouts(self):
        # Also check active sessions
        self.check_active()
        if Queue.last_checked != None and (datetime.now() - Queue.last_checked).seconds < 5:
            return
        # Update last check
        Queue.last_checked = datetime.now()
        # Remove 'em
        to_remove = []
        for item in self.root.queue:
            if item.last_checkin_time == None or item.last_checkin_time.__class__ is not datetime:
                item.last_checkin_time = datetime.now() 
            # If a minute has passed then time them out!
            elif (datetime.now() - item.last_checkin_time).seconds > 60:
                to_remove.append(item)
        # Clear them out of the queue
        for item in to_remove:
            self.root.queue.remove(item)
        # Print
        #if len(to_remove) > 0:
        #    print "Just kicked %i from queue for timeouts" % len(to_remove)

    def check_active(self):
        if Queue.last_active_check != None and (datetime.now() - Queue.last_active_check).seconds < 30:
            return
        Queue.last_active_check = datetime.now()
        # Run through the active queue
        to_remove = []
        for key in self.root.active.keys():
            item = self.root.active[key]
            # If the purchase time runs out or the client has not pinged recently then remove
            if self.purchase_time_left(active_id=key) <= 0 or (datetime.now() - item.last_checkin_time).seconds > 90:
                to_remove.append(key)
        # Remove them from the queue
        for key in to_remove:
            self.remove_from_active(key)
        # Print
        #if len(to_remove) > 0:
        #    print "Just kicked %i people from active for session timeouts! %s" % (len(to_remove), to_remove)
