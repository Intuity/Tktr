from base import TestBase
from random import randint
from selenium.webdriver.common.by import By

class TicketingBase(TestBase):

    @classmethod
    def create_ticket_type(cls, name=None, description=None, cost=None, release=True, quantity=100):
        # Fill dummy data if not provided
        if name == None: name = str(randint(0, 100000))
        if description == None: description = "This is the demo description for %s" % name
        if cost == None: cost = str(randint(0, 200))
        else: cost = "%.2f" % (cost / 100.0)
        # Enact an administration login
        cls.admin_login()
        # Go to the ticket type add page
        cls.browser.get(cls.route_path("admin_ticket_type_add"))
        cls.browser.find_element(By.ID, "name").send_keys(name)
        cls.browser.find_element(By.ID, "description").send_keys(description)
        cls.browser.find_element(By.ID, "cost").send_keys(cost)
        # Check the group boxes so that purchaase is allowed
        cls.browser.find_element(By.ID, "raven-group").click()
        cls.browser.find_element(By.ID, "admin-group").click()
        cls.browser.find_element(By.ID, "alumni-group").click()
        cls.browser.find_element(By.ID, "committee-group").click()
        cls.browser.find_element(By.ID, "submit").click()
        # Ensure it added
        cls.browser.get(cls.route_path("admin_tickets"))
        assert name in cls.browser.page_source
        # If we have been told to release then do so
        if release: cls.release_tickets(name, quantity=quantity)
        # Logout of admin account
        cls.logout()
        # Return its details
        return (name, description, cost, quantity)

    @classmethod
    def release_tickets(cls, type_name, quantity=100):
        # Login
        cls.admin_login()
        # Find the release link and click it
        cls.browser.get(cls.route_path("admin_tickets"))
        row = 1
        found = False
        while cls.is_element_present("//table/tbody/tr[%i]/td[1]" % row):
            name = cls.browser.find_element_by_xpath("//table/tbody/tr[%i]/td[1]" % row).text
            if type_name in name:
                cell = cls.browser.find_element_by_xpath("//table/tbody/tr[%i]/td[4]" % row)
                cell.find_element(By.CLASS_NAME, "release_tick_link").click()
                found = True
                break
            row += 1
        assert found, "Didn't find release link for ticket type!"
        # Now actually release some tickets
        cls.browser.find_element(By.ID, "number").send_keys(str(quantity))
        cls.browser.find_element(By.ID, "submit").click()
        # Deal with modal alert
        try:
            cls.browser.switch_to_alert().accept()
        except Exception:
            pass # Catch for PhantomJS
        # Logout
        cls.logout()
        # Return quantity
        return quantity
