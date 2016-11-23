from datetime import datetime
import os
from selenium.webdriver.common.by import By
from time import sleep
import urllib
from unittest import TestCase

from ticketing.tests.layers.raven import RavenBase
from ticketing.raven import Raven

class TestRaven(TestCase):

    layer = RavenBase

    def setUp(self):
        self.layer.make_browser()
        self.browser = self.layer.browser

    def tearDown(self):
        self.layer.close_browser()

    def test_raven_login(self):
        creds = self.layer.raven_login()
        sleep(1)
        # Go to the profile editing page
        self.layer.browser.get(self.layer.route_path("user_profile_edit"))
        # Now check we actually managed a login!
        email = self.browser.find_element(By.ID, "email")
        self.assertIn(creds[0], email.get_attribute("value"))

    def test_raven_profile(self):
        creds = self.layer.raven_login(fill_details=False)
        # Test out field validation by always leaving one field blank
        # - Test Data
        blank_state = {
            "fullname": "",
            "dob_day": str(datetime.now().day),
            "dob_month": str(datetime.now().month),
            "dob_year": str(datetime.now().year),
            "photofile": "",
            "college": "pleaseselect",
            "grad_status": "pleaseselect",
        }
        filled_state = {
            "fullname": "Automated Test User",
            "dob_day": "15",
            "dob_month": "3",
            "dob_year": "1987",
            "photofile": self.layer.root_path() + "/data/profile_images/dummy.png",
            "college": "sidney-sussex",
            "grad_status": "undergrad",
        }
        # - Run test
        for drop_key in filled_state:
            self.layer.browser.get(self.layer.route_path("user_profile_edit"))
            for key in filled_state:
                if key == drop_key or ("dob" in drop_key and "dob" in key):
                    self.browser.find_element(By.ID, key).send_keys(blank_state[key])
                else:
                    self.browser.find_element(By.ID, key).send_keys(filled_state[key])
            # Submit
            self.browser.find_element(By.ID, "submit").click()
            # Check for validation fault
            elem = self.layer.browser.find_element(By.XPATH, "//div[contains(@id, 'alert')]/strong")
            self.assertIn("Whoops", elem.text)
            self.assertIn("/profile/edit", self.browser.current_url)
        # Now run a full valid fill and check for no validation fault
        self.layer.browser.get(self.layer.route_path("user_profile_edit"))
        for key in filled_state:
            self.layer.browser.find_element(By.ID, key).send_keys(filled_state[key])
        # Submit
        self.layer.browser.find_element(By.ID, "submit").click()
        # Check for no validation fault
        self.assertNotIn("/profile/edit", self.browser.current_url)
        # Check we can access profile view without being forwarded back to edit
        self.layer.browser.get(self.layer.route_path("user_profile"))
        sleep(3)
        self.assertNotIn("/profile/edit", self.browser.current_url)

    def test_raven_purchase_flow(self):
        # First we need to make sure we have a ticket type
        details = self.layer.create_ticket_type()
        # Now login
        creds = self.layer.raven_login()
        # Now start purchase process
