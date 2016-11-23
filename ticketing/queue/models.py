from datetime import datetime
from persistent import Persistent
from ticketing.boxoffice.coding import Coding

class QueueItem(Persistent):

    queue_entry_time = None
    queue_exit_time = None
    purchase_entry_time = None
    purchase_exit_time = None
    last_checkin_time = None
    queue_id = None
    user_id = None # Populated once logged in

    def __init__(self):
        self.queue_entry_time = datetime.now()
        self.__name__ = self.queue_id = self.last_checkin_time = Coding().generateUniqueCode()
