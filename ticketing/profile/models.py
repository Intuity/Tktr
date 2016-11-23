from datetime import datetime
from lepl.apps.rfc3696 import Email
from persistent import Persistent
import re

class PostalAddress(Persistent):
    line_one = None
    line_two = None
    city = None
    county = None
    country = None
    postal_code = None

    def __init__(self):
        self.line_one = ""
        self.line_two = ""
        self.city = ""
        self.county = ""
        self.country = ""
        self.postal_code = ""

    def export(self):
        fields = [self.line_one, self.line_two, self.city, self.county, self.country, self.postal_code]
        for i in range(len(fields)):
            if fields[i] == None:
                fields[i] = ""
        return ", ".join(fields)

class UserProfile(Persistent):
    title = None
    forename = None
    surname = None
    raven_user = None
    email = None
    photo_file = None
    dob = None
    address = None # For Alumni/system accounts
    phone_number = None
    # Cam specific
    crsid = None
    college = None
    grad_status = None
    # Ticket - one to one relationship, always
    ticket = None
    
    def __init__(self):
        self.title = ""
        self.forename = ""
        self.surname = ""
        self.raven_user = False
        self.email = ""
        self.photo_file = ""
        self.dob = None # Date of birth
        self.address = None
        self.phone_number = ""
        # Cam specific
        self.crsid = ""
        self.college = ""
        self.grad_status = ""
        # ticket - one to one relationship, always
        self.ticket = None

    @property
    def fullname(self):
        return self.forename + " " + self.surname

    # Check all profile details are valid
    @property
    def complete(self):
        # Check name first
        pattern = re.compile(r"([\W])", re.UNICODE)
        fullname_stripped = self.fullname.replace(" ","").replace("-","")
        if self.fullname == None or len(fullname_stripped) < 4 or pattern.match(fullname_stripped) != None:
            return False
        # Also check name to see it has at least two parts
        parts = self.fullname.split(" ")
        if len(parts) < 2: # Must have a firstname and a surname
            return False
        #else:
        #    found_longer = False
        #    for part in parts: # Check if each part is acceptable
        #        if len(part) > 0 and len(part) < 3 and part.lower() not in ["li","su","ng","de","si","en"]:
        #            found_longer = True
        #            break
        #    if not found_longer:
        #        return False
        # Check email
        validator = Email()
        if self.email == None or not validator(self.email):
            return False
        # Check for photo
        #if self.photo_file == None or len(self.photo_file) < 5 or self.photo_file.split(".")[-1] not in ["jpg", "jpeg", "png", "bmp", "gif"]:
        #    return False
        # Check DOB - not an age check, just validity
        if self.dob == None or self.dob > datetime.now():
            return False
        # Check Cambridge related properties
        if self.raven_user:
            if self.crsid == None or len(self.crsid) < 3 or re.match(r"[a-zA-Z]+[0-9]+", self.crsid) == None:
                return False
            if self.email.lower() != self.crsid.replace(" ","").lower() + "@cam.ac.uk":
                return False
            from ticketing.macros.baselayout import BaseLayout
            if self.college == None or self.college not in BaseLayout.college_keys:
                return False
            if self.grad_status == None or self.grad_status not in BaseLayout.grad_status_keys:
                return False
        # If all tests past - woohoo!
        return True
