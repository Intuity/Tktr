from ConfigParser import ConfigParser, InterpolationMissingOptionError
from multiprocessing import Process
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException 
import ticketing
import time
import urllib
from waitress import serve

class TestBase(object):
    
    wsgi_process = None
    port_num = 6543
    should_run = False

    @classmethod
    def run_wsgi(cls):
        if cls.wsgi_process != None:
            cls.make_browser()
            return
        cls.wsgi_process = Process(target=cls._run_wsgi)
        cls.wsgi_process.start()
        # Wait for it to come up
        success = False
        for i in range(10):
            try:
                if urllib.urlopen("http://localhost:%i/" % cls.port_num).getcode() == 200:
                    success = True
                    break
            except Exception:
                pass
            time.sleep(2)
        # Create a second app for routing etc
        cls.app = cls._make_app()
        # If we failed to run WSGI then clean-up
        if not success:
            cls.stop_wsgi()
            cls.wsgi_process = None
            raise Exception("Couldn't bring up WSGI server")
        cls.make_browser()

    @classmethod
    def run_test(cls):
        cls.make_browser()

    @classmethod
    def make_browser(cls):
        # Build a selenium browser
        try:
            cls.browser = webdriver.PhantomJS()
        except Exception:
            try:
                # Fall back to Firefox
                cls.browser = webdriver.Firefox()
            except:
                raise Exception("Could not start a Firefox or PhantomJS instance!")
        cls.browser.get("http://127.0.0.1:%i/" % cls.port_num)
        # Setup to support routing
        cls.app = cls._make_app()

    @classmethod
    def close_browser(cls):
        try:
            cls.browser.quit()
        except Exception:
            pass
        cls.browser = None

    @classmethod
    def admin_login(cls, username=None, password=None):
        # Fill the default values
        if username == None:
            username = "admin"
            password = "password"
        # Logout, then login
        cls.logout()
        cls.browser.get(cls.route_path("admin_login"))
        cls.browser.get(cls.route_path("admin_login"))
        time.sleep(1) # Just ensure we are here
        cls.browser.find_element(By.ID, "username").send_keys(username)
        cls.browser.find_element(By.ID, "password").send_keys(password)
        cls.browser.find_element(By.ID, "submit").click()
        # Return login credentials used
        return (username, password)

    @classmethod
    def logout(cls):
        cls.browser.get("http://127.0.0.1:%i/logout" % cls.port_num)

    @classmethod
    def root_path(cls):
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))

    @classmethod
    def is_element_present(cls, xpath):
        try:
            cls.browser.find_element_by_xpath(xpath)
        except NoSuchElementException:
            return False
        return True

    @classmethod
    def stop_wsgi(cls):
        cls.should_run = False
        cls.wsgi_process.terminate()
        cls.wsgi_process.join()
        cls.wsgi_process = None
        try:
            cls.browser.quit()
        except Exception:
            pass

    @classmethod
    def _run_wsgi(cls):
        cls.should_run = True
        while cls.should_run:
            try:
                serve(cls._make_app(), host='0.0.0.0', port=cls.port_num)
            except Exception:
                cls.port_num += 1 # Walk until we find a free address

    @classmethod
    def _make_app(cls):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
        # Parse in the options
        config = ConfigParser()
        config.read(os.path.join(base, "data/paste.ini"))
        ticketing_config = {}
        for section in config.sections():
            section_config = {}
            ticketing_config[section] = section_config
            for option in config.options(section):
                try:
                    section_config[option] = config.get(section, option)
                except InterpolationMissingOptionError:
                    pass
        # Setup some properties
        ticketing_config["app:main"]["zodbconn.uri"] = "memory://testdb"
        ticketing_config["app:main"]["raven.testing"] = "true"
        # Setup the app
        return ticketing.main(ticketing_config, **ticketing_config["app:main"])

    @classmethod
    def route_url(cls, route, kw={}):
        return "http://127.0.0.1:%i%s" % (cls.port_num, cls.app.routes_mapper.generate(route, kw))
