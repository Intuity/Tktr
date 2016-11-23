from ticketing_layer import TicketingBase
from random import randint
from selenium.webdriver.common.by import By
from ticketing.raven import Raven
from time import sleep

class RavenBase(TicketingBase):

    @classmethod
    def raven_login(cls, crsid=None, password=None, fill_details=True):
        if crsid == None:
            crsid = "test0%03d" % ( randint(0, 400) )
            password = "test"
        # First ensure we are logged out
        cls.logout()
        # Now login
        cls.browser.get("http://localhost:%i/" % cls.port_num)
        # Click the raven link
        link = cls.browser.find_element(By.ID, "ravenbutton")
        link.click()
        sleep(1)
        # We should now be at the Raven testing login page
        assert "Demonstration Authentication Service" in cls.browser.page_source
        assert Raven.our_description in cls.browser.page_source
        # Fill in the login details
        user = cls.browser.find_element(By.ID, "userid")
        user.send_keys(crsid)
        pwd = cls.browser.find_element(By.ID, "pwd")
        pwd.send_keys(password)
        cls.browser.find_element(By.NAME, "credentials").submit()
        # Fill details automatically fills the profile
        if fill_details:
            filled_state = {
                "fullname": "Automated Test User",
                "dob_day": "15",
                "dob_month": "3",
                "dob_year": "1987",
                "photofile": cls.root_path() + "/data/profile_images/dummy.png",
                "college": "sidney-sussex",
                "grad_status": "undergrad",
            }
            # Now run a full valid fill and check for no validation fault
            cls.browser.get(cls.route_path("user_profile_edit"))
            for key in filled_state:
                cls.browser.find_element(By.ID, key).send_keys(filled_state[key])
            # Submit
            cls.browser.find_element(By.ID, "submit").click()
        # Return credentials used
        return (crsid, password)
