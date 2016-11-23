from persistent import Persistent
from ticketing.boxoffice.coding import Coding

class CheckIn(Persistent):
    date = None
    enacted_by = None # Points at the enacting user
    overriden = False
    override_id = None

    def __init__(self):
        self.__name__ = Coding().generateUniqueCode()
        self.date = None
        self.enacted_by = None
        self.overriden = False
        self.override_id = None

    def export(self):
        return {
            "id": self.__name__,
            "date": self.date.strftime("%d/%m/%Y - %H:%M:%S"),
            "enactor": self.enacted_by.username,
            "overriden": self.overriden,
            "override_id": self.override_id
        }
