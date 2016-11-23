from selenium.webdriver.common.by import By
import urllib
from unittest import TestCase

from ticketing.tests.layers.base import TestBase

class TestRunning(TestCase):

    layer = TestBase

    def setUp(self):
        self.layer.make_browser()

    def tearDown(self):
        self.layer.close_browser()

    def test_running(self):
        check_running = urllib.urlopen("http://localhost:%i/"  % self.layer.port_num)
        self.assertEqual(check_running.getcode(), 200)

    def test_routing(self):
        check_route = urllib.urlopen(self.layer.route_path('admin_login'))
        self.assertEqual(check_route.getcode(), 200)

    def test_front_page(self):
        self.layer.browser.get("http://localhost:%i/" % self.layer.port_num)
        # Check for copyright information
        elem = self.layer.browser.find_element(By.XPATH, "//div[contains(@class, 'footer')]")
        self.assertEqual(elem.text, "Copyright LightLogic 2013")
