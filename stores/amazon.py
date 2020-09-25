import json
import secrets
import time
from os import path

from chromedriver_py import binary_path  # this will get you the path variable
from furl import furl
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from notifications.notifications import NotificationHandler
from utils import selenium_utils
from utils.json_utils import InvalidAutoBuyConfigException
from utils.logger import log
from utils.selenium_utils import options, enable_headless, wait_for_element

BASE_URL = "https://www.amazon.com/"
LOGIN_URL = "https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_custrec_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=usflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&"
CART_URL = "https://www.amazon.com/gp/aws/cart/add.html"
AUTOBUY_CONFIG_PATH = "amazon_config.json"

class Amazon:
    def __init__(self, headless=False):
        self.notification_handler = NotificationHandler()
        if headless:
            enable_headless()
        options.add_argument(f"user-data-dir=.profile-amz")
        self.driver = webdriver.Chrome(executable_path=binary_path, options=options)
        self.wait = WebDriverWait(self.driver, 10)
        if path.exists(AUTOBUY_CONFIG_PATH):
            with open(AUTOBUY_CONFIG_PATH) as json_file:
                try:
                    config = json.load(json_file)
                    self.username = config["username"]
                    self.password = config["password"]
                    self.asin_list = config["asin_list"]
                    assert isinstance(self.asin_list, list)
                except Exception:
                    raise InvalidAutoBuyConfigException("amazon_config.json file not formatted properly.")

        else:
            raise InvalidAutoBuyConfigException("Missing amazon_config.json file.")

        self.driver.get(BASE_URL)
        if self.is_logged_in():
            log.info("Already logged in")
        else:
            self.login()
            time.sleep(15)  # We can remove this once I get more info on the phone verification page.

    def is_logged_in(self):
        try:
            text = wait_for_element(self.driver, "nav-link-accountList").text
            return "Hello, Sign in" not in text
        except Exception:
            return False

    def login(self):
        self.driver.get(LOGIN_URL)
        if self.driver.find_element_by_xpath('//*[@id="ap_email"]'):
            self.driver.find_element_by_xpath('//*[@id="ap_email"]').send_keys(
                self.username + Keys.RETURN
            )
        self.driver.find_element_by_xpath('//*[@id="ap_password"]').send_keys(
            self.password + Keys.RETURN
        )

        log.info(f"Logged in as {self.username}")

    def run_item(self, delay=3, test=False):
        log.info("Checking stock for items.")
        while not self.something_in_stock():
            time.sleep(delay)
        self.notification_handler.send_notification("Your items on Amazon.com were found!")
        self.checkout(test=test)

    def something_in_stock(self):
        params = {
            'anticache': str(secrets.token_urlsafe(32))
        }

        for x in range(len(self.asin_list)):
            params[f'ASIN.{x+1}'] = self.asin_list[x]
            params[f'Quantity.{x+1}'] = 1

        f = furl(CART_URL)
        f.set(params)
        self.driver.get(f.url)
        selenium_utils.wait_for_page(self.driver, "Amazon.com: Please Confirm Your Action")

        if self.driver.find_elements_by_xpath('//td[@class="price item-row"]'):
            log.info("One or more items in stock!")

            return True
        else:
            return False

    def checkout(self, test):
        log.info("Clicking continue.")
        self.driver.find_element_by_xpath('//input[@value="add"]').click()
        selenium_utils.wait_for_page(self.driver, "Amazon.com Shopping Cart")

        log.info("clicking checkout.")
        self.driver.find_element_by_xpath('//*[@id="sc-buy-box-ptc-button"]/span/input').click()

        selenium_utils.wait_for_either_title(self.driver, "Amazon.com Checkout", "Amazon.com: Sign-In")

        if self.driver.title == "Amazon.com: Sign in":
            self.login()
            selenium_utils.wait_for_page(self.driver, "Amazon.com Checkout")

        log.info("Finishing checkout")
        if not test:
            self.driver.find_element_by_xpath('//*[@id="bottomSubmitOrderButtonId"]/span/input').click()

        selenium_utils.wait_for_page(self.driver, "Amazon.com Thanks You")

        log.info("Order Placed.")