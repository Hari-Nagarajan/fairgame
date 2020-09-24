import time
import hashlib

from chromedriver_py import binary_path  # this will get you the path variable
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException

from notifications.notifications import NotificationHandler
from utils.logger import log
from utils.selenium_utils import options, enable_headless, wait_for_element


BASE_URL = "https://www.amazon.com/"
LOGIN_URL = "https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_custrec_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=usflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&"


class Amazon:
    def __init__(self, username, password, item_url, headless=False):
        self.notification_handler = NotificationHandler()
        if headless:
            enable_headless()
        h = hashlib.md5(item_url.encode()).hexdigest()
        options.add_argument(f"user-data-dir=.profile-amz-{h}")
        self.driver = webdriver.Chrome(executable_path=binary_path, options=options)
        self.wait = WebDriverWait(self.driver, 10)
        self.username = username
        self.password = password
        self.driver.get(BASE_URL)
        if self.is_logged_in():
            log.info("Already logged in")
        else:
            self.login()
            time.sleep(15)

    def is_logged_in(self):
        try:
            text = wait_for_element(self.driver, "nav-link-accountList").text
            return "Hello, Sign in" not in text
        except Exception:
            return False

    def login(self):
        self.driver.get(LOGIN_URL)
        self.driver.find_element_by_xpath('//*[@id="ap_email"]').send_keys(
            self.username + Keys.RETURN
        )
        self.driver.find_element_by_xpath('//*[@id="ap_password"]').send_keys(
            self.password + Keys.RETURN
        )

        log.info(f"Logged in as {self.username}")

    def run_item(self, item_url, price_limit=1000, delay=3):
        log.info(f"Loading page: {item_url}")
        self.driver.get(item_url)
        item = ""
        try:
            product_title = self.wait.until(
                presence_of_element_located((By.ID, "productTitle"))
            )
            log.info(f"Loaded page for {product_title.text}")
            item = product_title.text
        except:
            log.error(self.driver.current_url)

        availability = self.driver.find_element_by_xpath(
            '//*[@id="availability"]'
        ).text.replace("\n", " ")

        log.info(f"Initial availability message is: {availability}")

        while not self.driver.find_elements_by_xpath('//*[@id="buy-now-button"]'):
            try:
                self.driver.refresh()
                log.info(f"Refreshing page for {item}")
                availability = self.wait.until(
                    presence_of_element_located((By.ID, "availability"))
                ).text.replace("\n", " ")
                log.info(f"Current availability message is: {availability}")
                time.sleep(delay)
            except TimeoutException as _:
                log.warn("A polling request timed out. Retrying.")

        log.info("Item in stock, buy now button found!")
        try:
            price_str = self.driver.find_element_by_id("priceblock_ourprice").text
        except NoSuchElementException as _:
            price_str = self.driver.find_element_by_id("priceblock_dealprice").text
        price_int = int(round(float(price_str.strip("$"))))
        if price_int < price_limit:
            log.info(f"Attempting to buy item for {price_int}")
            self.buy_now()
        else:
            self.notification_handler.send_notification(
                f"Item was found, but price is at {price_int} so we did not buy it."
            )
            log.info(f"Price was too high {price_int}")

    def buy_now(self):
        self.driver.find_element_by_xpath('//*[@id="buy-now-button"]').click()
        log.info("Clicking 'Buy Now'.")

        try:
            place_order = WebDriverWait(self.driver, 2).until(
                presence_of_element_located((By.ID, "turbo-checkout-pyo-button"))
            )
        except:
            log.debug("Went to check out page.")
            place_order = WebDriverWait(self.driver, 2).until(
                presence_of_element_located((By.NAME, "placeYourOrder1"))
            )

        log.info("Clicking 'Place Your Order'.")
        place_order.click()
        self.notification_handler.send_notification(
            f"Item was purchased! Check your Amazon account."
        )

    def force_stop(self):
        self.driver.stop_client()
