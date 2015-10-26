import os
import sys
import new
import unittest
import time
import json
from selenium import webdriver
from sauceclient import SauceClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.sys.path.insert(0, BASE_DIR)

# it's best to remove the hardcoded defaults and always get these values
# from environment variables
USERNAME = os.environ.get('SAUCE_USERNAME', os.environ.get('SAUCE_USERNAME'))
ACCESS_KEY = os.environ.get('SAUCE_ACCESS_KEY', os.environ.get('SAUCE_ACCESS_KEY'))

FLASK_USERNAME = 'super-admin@example.com'
FLASK_PASSWORD = 'admin'

# initialise sauce client to update jobs
sauce = SauceClient(USERNAME, ACCESS_KEY)

# load browser matrix from config.json
config = open('%s/config.json' % os.path.dirname(os.path.abspath(__file__)))
browserMatrix = json.load(config)
config.close()

def on_platforms(platforms):
    def decorator(base_class):
        module = sys.modules[base_class.__module__].__dict__
        for i, platform in enumerate(platforms):
            d = dict(base_class.__dict__)
            d['desired_capabilities'] = platform
            d['user'] = 'user%d' % i
            name = '%s_%s' % (base_class.__name__, i + 1)
            module[name] = new.classobj(name, (base_class,), d)
    return decorator

@on_platforms(browserMatrix['browser'])
class SauceSampleTest(unittest.TestCase):
    def setUp(self):
        self.desired_capabilities['name'] = str(self)
        self.desired_capabilities['username'] = USERNAME
        self.desired_capabilities['access-key'] = ACCESS_KEY

        if os.environ.get('TRAVIS_BUILD_NUMBER'):
            self.desired_capabilities[
                'build'] = os.environ.get('TRAVIS_BUILD_NUMBER')
            self.desired_capabilities[
                'tunnel-identifier'] = os.environ.get('TRAVIS_JOB_NUMBER')

        self.driver = webdriver.Remote(
            desired_capabilities=self.desired_capabilities,
            command_executor='http://localhost:4445/wd/hub'
        )

        self.driver.implicitly_wait(30)

    def login(self):
        # go to login page
        self.driver.get('http://localhost:8080/login')

        # enter email
        name = self.driver.find_element_by_css_selector(
            'input[name="email"]')
        name.send_keys(FLASK_USERNAME)

        # enter password
        pw = self.driver.find_element_by_css_selector(
            'input[name="password"]')
        pw.send_keys(FLASK_PASSWORD)

        # click submit
        button = self.driver.find_element_by_css_selector(
            'input[value="Login"]')
        button.click()

    def test_login(self):
        # login
        self.login()

        # login check
        message = self.driver.find_element_by_css_selector('.flashes').text
        assert 'You were logged in' in message

    def tearDown(self):
        try:
            if sys.exc_info() == (None, None, None):
                sauce.jobs.update_job(self.driver.session_id, passed=True, public=True)
            else:
                sauce.jobs.update_job(self.driver.session_id, passed=False, public=True)
        finally:
            self.driver.quit()
