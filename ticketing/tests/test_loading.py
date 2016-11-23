from random import randint
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from threading import Thread
from time import sleep
from unittest import TestCase

from ticketing.tests.layers.raven import RavenBase
from ticketing.raven import Raven

class TestRaven(TestCase):

    layer = RavenBase
    count = 0

    def setUp(self):
        self.layer.make_browser()
        self.browser = self.layer.browser

    def tearDown(self):
        self.layer.close_browser()

    # Automatically runs a full system stress test
    def test_loading(self):
        #counts = {
        #    "basic": 300,
        #    "jump": 100,
        #    "dining": 50
        #}
        # First setup a some ticket types to purchase
        self.layer.create_ticket_type(
            name="Basic Type",
            description="Here is the basic type description",
            cost=13500,
            release=True,
            quantity=300
        )
        self.layer.create_ticket_type(
            name="Queue Jump Type",
            description="Here is the queue jump type description",
            cost=15000,
            release=True,
            quantity=100
        )
        self.layer.create_ticket_type(
            name="Dining Type",
            description="Here is the dining type description",
            cost=17500,
            release=True,
            quantity=50
        )
        # Enable the queuing system
        self.layer.admin_login()
        self.layer.browser.get(self.layer.route_path("admin_settings"))
        self.layer.browser.execute_script("Tick.admin.switch($('#switch_queue'), 'on');")
        sleep(1)
        self.layer.browser.find_element(By.ID, "concurrent").clear()
        self.layer.browser.find_element(By.ID, "concurrent").send_keys("10")
        self.layer.browser.find_element(By.ID, "sessiontime").clear()
        self.layer.browser.find_element(By.ID, "sessiontime").send_keys("15")
        self.layer.browser.find_element(By.ID, "submit").click()
        self.layer.logout()
        # Spawn many workers to stress the master
        threads = []
        self.run_process(1)
        #for i in range(0, 100):
        #    thread = Thread(target=self.run_process, args=(i+1))
        #    thread.start()
        #    threads.append(thread)
        # Once we have everyone up, monitor them
        #while len(threads) > 0:
        #    threads[0].join()
        #    print "Thread Cleared"
        #    threads.remove(threads[0])
        #print "Test Complete"

    # Run a full ticket purchase
    def run_process(self, person_index):
        browser = None
        # Build a selenium browser
        try:
            browser = webdriver.PhantomJS()
        except Exception:
            try:
                # Fall back to Firefox
                browser = webdriver.Firefox()
            except:
                raise Exception("Could not start a Firefox or PhantomJS instance!")
        try:
            # Navigate to the queue to get a post
            browser.get(self.layer.route_path("queue"))
            # Find out where we are in the queue
            at_front = False
            while not at_front:
                browser.get(self.layer.route_path("queue_position"))
                source = browser.find_element_by_xpath("//body").text
                if "waiting" in source:
                    print "At front but waiting"
                    sleep(1) # Don't keep hammering
                elif "ready" in source:
                    print "Off we go!"
                    at_front = True
                    break
                elif int(source) < 0:
                    print "We've got a problem"
                    # Re-enter queue
                    browser.get(self.layer.route_path("queue"))
                else:
                    sleep(1)
            # Now we are at front, login and purchase some of dem tickets
            browser.get(self.layer.route_path("queue_front"))
            browser.get(self.layer.route_path("welcome"))
            # Click the raven link
            browser.find_element(By.ID, "ravenbutton").click()
            sleep(1)
            # We should now be at the Raven testing login page
            assert "Demonstration Authentication Service" in browser.page_source
            assert Raven.our_description in browser.page_source
            # Fill in the login details
            browser.find_element(By.ID, "userid").send_keys("test%04d" % person_index)
            browser.find_element(By.ID, "pwd").send_keys("test")
            browser.find_element(By.NAME, "credentials").submit()
            sleep(2)
            # Fill details automatically fills the profile
            filled_state = {
                "fullname": "Automated Test User %i" % self.count,
                "dob_day": "15",
                "dob_month": "3",
                "dob_year": "1987",
                "photofile": self.layer.root_path() + "/data/profile_images/dummy.png",
                "college": "sidney-sussex",
                "grad_status": "undergrad",
            }
            self.count += 1
            # Fill all of the fields
            browser.get(self.layer.route_path("user_profile_edit"))
            for key in filled_state:
                try:
                    browser.find_element(By.ID, key).clear()
                except WebDriverException:
                    pass
                browser.find_element(By.ID, key).send_keys(filled_state[key])
            # Submit
            browser.find_element(By.ID, "submit").click()
            # Find the test type and purchase it
            num_dining = num_qj = num_basic = 1
            dining_type_id = self.find_type_id(browser, "Dining Type")
            if dining_type_id == None:
                num_dining = 0
                print "No dining tickets left!"
            qj_type_id = self.find_type_id(browser, "Queue Jump Type")
            if qj_type_id == None:
                num_qj = 0
                print "No queue jump tickets left!"
            basic_type_id = self.find_type_id(browser, "Basic Type")
            if basic_type_id == None:
                num_basic = 0
                print "No basic tickets left"
            if dining_type_id == None and qj_type_id == None and basic_type_id == None:
                print "No tickets available for purchase"
                return
            # - Now run our purchase
            if dining_type_id != None:
                browser.find_element(By.ID, dining_type_id).send_keys("%i" % num_dining)
            if qj_type_id != None:
                browser.find_element(By.ID, qj_type_id).send_keys("%i" % num_qj)
            if basic_type_id != None:
                browser.find_element(By.ID, basic_type_id).send_keys("%i" % num_basic)
            # - Click the submit button
            browser.find_element(By.ID, "submit").click()
            sleep(1)
            # Mark the first ticket as our own
            row = 1
            marked = False
            person = 1
            numbers = ["one", "two", "three", "four", "five", "six", "seven"]
            while self.is_element_present(browser, "//table/tbody/tr[%i]/td[4]" % row):
                links = browser.find_elements_by_xpath("//table/tbody/tr[%i]/td[4]/a" % row)
                for link in links:
                    if "Mark as My Ticket" in link.text and not marked:
                        link.click()
                        marked = True
                        break
                    elif "Set Guest Information" in link.text:
                        # Fill in guest details
                        link.click()
                        browser.find_element(By.ID, "fullname").send_keys("Jim Bob %s" % numbers[person % 7])
                        browser.find_element(By.ID, "email").send_keys("jim.bod.%i@lightlogic.co.uk" % person)
                        browser.find_element(By.ID, "dob_day").send_keys("2")
                        browser.find_element(By.ID, "dob_month").send_keys("July")
                        browser.find_element(By.ID, "dob_year").send_keys("1991")
                        browser.find_element(By.ID, "photofile").send_keys(self.layer.root_path() + "/data/profile_images/dummy.png")
                        browser.find_element(By.ID, "submit").click()
                        person += 1
                row += 1
            browser.get(self.layer.route_path("order_details"))
            browser.find_element(By.ID, "submit").click()
            # Completed ticket details, now go to payment and randomly choose a pathway
            paths = ["pay-stripe", "pay-banktransfer", "pay-cheque"]
            choice = randint(0, 2)
            browser.find_element(By.ID, paths[choice]).click()
            # - Fill in the appropriate details
            if choice in [1, 2]:
                browser.find_element(By.ID, "makepayment").click()
            elif choice == 0:
                browser.find_element(By.ID, "number").send_keys("4242-4242-4242-4242")
                browser.find_element(By.ID, "cvc").send_keys("123")
                browser.find_element(By.ID, "exp-month").send_keys("04")
                browser.find_element(By.ID, "exp-year").send_keys("2020")
                browser.find_element(By.ID, "paynow").click()
                sleep(10) # Wait for stripe to process
        except Exception, e:
            raise e
        # Close the browser
        browser.quit()

    def find_type_id(self, browser, typename):
        type_id = None
        row = 1
        while self.is_element_present(browser, "//table/tbody/tr[%i]/td[1]/h4" % row):
            name = browser.find_element_by_xpath("//table/tbody/tr[%i]/td[1]/h4" % row).text
            if typename in name:
                if not self.is_element_present(browser, "//table/tbody/tr[%i]/td[3]/select" % row):
                    type_id = None
                    raise Exception("NO SELECT")
                else:
                    type_id = browser.find_element_by_xpath("//table/tbody/tr[%i]/td[3]/select" % row).get_attribute("id")
                break
            row += 1
        return type_id

    def is_element_present(cls, browser, xpath):
        try:
            browser.find_element_by_xpath(xpath)
        except NoSuchElementException:
            return False
        return True
