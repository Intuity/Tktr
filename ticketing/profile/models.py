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

# Class: UserProfile
# 
#   Describes a single person's identity - re-used for both customers and their
#   guests. This is also attached to tickets to provide the ticket's details.
# 
class UserProfile(Persistent):
    title = None                # Person's salutation (e.g. Ms/Mrs/Mr...)
    forename = None             # Person's forename
    surname = None              # Person's surname
    raven_user = None           # Whether this user authenticated via Raven
    raven_alumnus = None        # Whether Raven flagged this account as an alumnus (not 'current')
    email = None                # Person's email address
    photo_file = None           # Path to photo for the person
    dob = None                  # Date object describing the date of birth of the person
    address = None              # Postal address (for non-student accounts) of person
    phone_number = None         # Phone number of person
    # Cam specific
    crsid = None                # CRSid of person
    college = None              # College (Sidney/etc.) of person
    grad_status = None          # Status (e.g. student/staff/post-grad/graduate/etc.)
    # Ticket - one to one relationship, always
    ticket = None               # The ticket of this person (if populated)
    
    def __init__(self):
        # Set instance default values
        self.title = ""
        self.forename = ""
        self.surname = ""
        self.raven_user = False
        self.raven_alumnus = False
        self.email = ""
        self.photo_file = ""
        self.dob = None
        self.address = None
        self.phone_number = ""
        self.crsid = ""
        self.college = ""
        self.grad_status = ""
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
            # All current members should use "@cam.ac.uk" emails, prefixed by their CRSid
            if not self.raven_alumnus and self.email.lower() != self.crsid.replace(" ","").lower() + "@cam.ac.uk":
                return False
            # All alunni should should use an email address that doesn't contain "@cam.ac.uk"
            elif self.raven_alumnus and "@cam.ac.uk" in self.email.lower():
                return False
            # Check a valid college and graduate status has been specified
            from ticketing.macros.baselayout import BaseLayout
            if self.college == None or self.college not in BaseLayout.college_keys:
                return False
            if self.grad_status == None or self.grad_status not in BaseLayout.grad_status_keys:
                return False
        # If all tests past - woohoo!
        return True
