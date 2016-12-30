import base64, cgi, hashlib, os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from lepl.apps.rfc3696 import Email
import re

from ticketing.macros.baselayout import BaseLayout

class ProcessAndValidate(object):

    def __init__(self, new_data, base_dir, minimum_age, event_date, profile=None, photo_required=False, phone_number_required=True):
        self.new_data = new_data
        self.profile = profile
        self.base_dir = base_dir
        self.minimum_age = minimum_age
        self.event_date = event_date
        self.photo_required = photo_required
        self.phone_number_required = phone_number_required

    def process(self):
        # Check the salutation exists
        if "title" not in self.new_data or self.new_data["title"] not in ["Mr", "Mrs", "Miss", "Ms", "Dr", "Prof", "Rev", "Other"]:
            raise ValueError("Please check that you have selected a valid salutation.")
        elif self.new_data["title"] == "Other" and ("othertitle" not in self.new_data or len(self.new_data["othertitle"].strip()) == 0):
            raise ValueError("Please check that you have entered a valid salutation.")
        # Process the name
        forename = self.new_data["forename"]
        forename = re.sub(r"[^a-zA-Z\- ]+", "", forename)
        surname = self.new_data["surname"]
        surname = re.sub(r"[^a-zA-Z\- ]+", "", surname)
        # - Check it is a reasonable length
        if (len(forename.replace(" ","")) < 2) or (len(surname.replace(" ","")) < 2):
            raise ValueError("Please check that you have entered a valid name")
        # Now the title
        if not "title" in self.new_data:
            raise ValueError("You must select a salutation.")
        title = self.new_data["title"]
        if title == "Other":
            title = self.new_data["othertitle"]
        if len(title) < 2:
            raise ValueError("You must specify a salutation.")
        # Now the email address
        atcambridge = ((self.profile != None and self.profile.raven_user) or ("atcambridge" in self.new_data and self.new_data["atcambridge"] == "yes"))
        email = None
        if "email" in self.new_data:
            email = self.new_data["email"]
            if atcambridge and not self.profile.raven_alumnus:
                email = self.new_data["crsid"].replace(" ","") + "@cam.ac.uk"
            validator = Email()
            if not validator(email):
                raise ValueError("You have not entered a valid email address, please provide one.")
            elif self.profile.raven_alumnus and (self.profile.crsid.lower() + "@cam.ac.uk") in email:
                raise ValueError("Alumni Raven accounts are not allowed to use an '@cam.ac.uk' email address as you will be unable to access it")
        # Now the date of birth
        day = int(float(self.new_data["dob_day"]))
        month = int(float(self.new_data["dob_month"]))
        year = int(float(self.new_data["dob_year"]))
        if day < 1 or day > 31 or month < 1 or month > 12:
            raise ValueError("You have entered an invalid date of birth.")
        dob = datetime(year, month, day)
        if dob > datetime.now():
            raise ValueError("The date of birth you have entered is in the future, please change it.")
        elif relativedelta(self.event_date, dob).years < self.minimum_age: # This needs to be changeable - and the day needs to be the event date
            raise ValueError("Guest's must be aged %i years or older to attend the event." % self.minimum_age)
        # Now the photo!
        new_filename = None
        if self.photo_required:
            if "photofile" in self.new_data and isinstance(self.new_data["photofile"], cgi.FieldStorage):
                file_name = self.new_data["photofile"].filename
                file_data = self.new_data["photofile"].file
                # Read all data in
                read_data = None
                while 1:
                    chunk = file_data.read(2<<16)
                    if not chunk:
                        break
                    if read_data == None:
                        read_data = chunk
                    else:
                        read_data += chunk
                # Check type
                extension = file_name.split(".")[-1].lower()
                if extension not in ["jpg","jpeg","gif","bmp","png","psd","tif"]:
                    raise ValueError("Please upload a photo in JPEG, bitmap or PNG format.")
                # Generate hashed name
                base64_file = base64.urlsafe_b64encode(read_data)
                m = hashlib.md5(base64_file)
                b64_name = base64.b64encode(m.digest()).replace("/","-")
                new_filename = b64_name + "." + extension
                path = os.path.join(self.base_dir, "data/profile_images/%s" % new_filename)
                # Save it out
                if not os.path.isfile(path):
                    output = open(path, "wb")
                    output.seek(0)
                    output.write(read_data)
                    output.close()
            # Check we have a photo stored
            if (self.profile != None and (self.profile.photo_file == None or len(self.profile.photo_file) < 5)  and ("photofile" not in self.new_data or not isinstance(self.new_data["photofile"], cgi.FieldStorage))):
                raise ValueError("You must upload a photo as it is required for security at the event.")
            elif (self.profile == None and ("photofile" not in self.new_data or not isinstance(self.new_data["photofile"], cgi.FieldStorage))):
                raise ValueError("You must upload a photo as it is required for security at the event.")
        # Phone number
        phone_number = None
        if self.phone_number_required:
            if "phone_number" in self.new_data:
                phone_number = self.new_data["phone_number"]
                if len(phone_number) < 10:
                    raise ValueError("You have not entered a valid phone number, please correct this.")
            else:
                raise ValueError("You have not entered a phone number, please provide one.")
        # Now the Cambridge specific checks
        college = grad_status = crsid = None
        if atcambridge:
            # CRSid
            if "crsid" in self.new_data:
                crsid = self.new_data["crsid"]
                if re.match(r"[a-zA-Z]+[0-9]+", crsid) == None:
                    raise ValueError("The CRSid you entered is invalid, please try again")
            # College and status
            college_keys = BaseLayout.college_keys
            grad_status_keys = BaseLayout.grad_status_keys
            college = self.new_data["college"]
            grad_status = self.new_data["grad_status"]
            if college not in college_keys:
                raise ValueError("You have not selected a valid college, please try again.")
            elif grad_status not in grad_status_keys:
                raise ValueError("You have not selected a valid graduate status, please try again.")
        # Return the data back
        return {
            "title": title,
            "forename": forename,
            "surname": surname,
            "email": email,
            "phone_number": phone_number,
            "dob": dob,
            "photofile": new_filename,
            "atcambridge": atcambridge,
            "crsid": crsid,
            "college": college,
            "grad_status": grad_status,
        }
        