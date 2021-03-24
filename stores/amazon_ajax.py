import fileinput
import json
import os
import pickle
import platform
import random
import time
import typing
from contextlib import contextmanager
from datetime import datetime

import psutil
import requests
from amazoncaptcha import AmazonCaptcha
from chromedriver_py import binary_path
from furl import furl
from lxml import html
from price_parser import parse_price, Price
from selenium import webdriver

# from seleniumwire import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC, wait
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.support.ui import WebDriverWait

from common.amazon_support import (
    AmazonItemCondition,
    condition_check,
    FGItem,
    get_shipping_costs,
    price_check,
    SellerDetail,
    solve_captcha,
)
from notifications.notifications import NotificationHandler
from stores.basestore import BaseStoreHandler
from utils.logger import log
from utils.selenium_utils import enable_headless, options

from functools import wraps

# PDP_URL = "https://smile.amazon.com/gp/product/"
# AMAZON_DOMAIN = "www.amazon.com.au"
# AMAZON_DOMAIN = "www.amazon.com.br"
AMAZON_DOMAIN = "www.amazon.ca"
# NOT SUPPORTED AMAZON_DOMAIN = "www.amazon.cn"
# AMAZON_DOMAIN = "www.amazon.fr"
# AMAZON_DOMAIN = "www.amazon.de"
# NOT SUPPORTED AMAZON_DOMAIN = "www.amazon.in"
# AMAZON_DOMAIN = "www.amazon.it"
# AMAZON_DOMAIN = "www.amazon.co.jp"
# AMAZON_DOMAIN = "www.amazon.com.mx"
# AMAZON_DOMAIN = "www.amazon.nl"
# AMAZON_DOMAIN = "www.amazon.es"
# AMAZON_DOMAIN = "www.amazon.co.uk"
# AMAZON_DOMAIN = "www.amazon.com"
# AMAZON_DOMAIN = "www.amazon.se"

AMAZON_URLS = {
    "BASE_URL": "https://{domain}/",
    "ALT_OFFER_URL": "https://{domain}/gp/offer-listing/",
    "OFFER_URL": "https://{domain}/dp/",
    "CART_URL": "https://{domain}/gp/cart/view.html",
    "ATC_URL": "https://{domain}/gp/aws/cart/add.html",
}

PDP_PATH = f"/dp/"
REALTIME_INVENTORY_PATH = f"gp/aod/ajax?asin="

CONFIG_FILE_PATH = "config/amazon_ajax_config.json"
STORE_NAME = "Amazon"
DEFAULT_MAX_TIMEOUT = 10

# Request
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, sdch, br",
    "Accept-Language": "en-US,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
}


def free_shipping_check(seller):
    if seller.shipping_cost.amount > 0:
        return False
    else:
        return True


amazon_config = {}


class AmazonStoreHandler(BaseStoreHandler):
    http_client = False
    http_20_client = False
    http_session = True

    def __init__(
        self,
        notification_handler: NotificationHandler,
        headless=False,
        checkshipping=False,
        detailed=False,
        single_shot=False,
        no_screenshots=False,
        disable_presence=False,
        slow_mode=False,
        encryption_pass=None,
        log_stock_check=False,
        shipping_bypass=False,
        wait_on_captcha_fail=False,
    ) -> None:
        super().__init__()

        self.shuffle = True

        self.notification_handler = notification_handler
        self.check_shipping = checkshipping
        self.item_list: typing.List[FGItem] = []
        self.stock_checks = 0
        self.start_time = int(time.time())
        self.amazon_domain = "smile.amazon.com"
        self.webdriver_child_pids = []
        self.take_screenshots = not no_screenshots
        self.shipping_bypass = shipping_bypass
        self.single_shot = single_shot
        self.detailed = detailed
        self.disable_presence = disable_presence
        self.log_stock_check = log_stock_check
        self.wait_on_captcha_fail = wait_on_captcha_fail
        self.amazon_cookies = {}

        from cli.cli import global_config

        global amazon_config
        amazon_config = global_config.get_amazon_config(encryption_pass)
        self.profile_path = global_config.get_browser_profile_path()

        # Load up our configuration
        self.parse_config()

        # Set up the Chrome options based on user flags
        if headless:
            enable_headless()

        prefs = get_prefs(no_image=False)
        set_options(prefs, slow_mode=slow_mode)
        modify_browser_profile()

        # Initialize the Session we'll use for this run
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        # self.conn = http.client.HTTPSConnection(self.amazon_domain)
        # self.conn20 = HTTP20Connection(self.amazon_domain)

        # Spawn the web browser
        self.driver = create_driver(options)
        self.webdriver_child_pids = get_webdriver_pids(self.driver)

    def __del__(self):
        message = f"Shutting down {STORE_NAME} Store Handler."
        log.info(message)
        self.notification_handler.send_notification(message)
        self.delete_driver()

    def delete_driver(self):
        try:
            if platform.system() == "Windows" and self.driver:
                log.debug("Cleaning up after web driver...")
                # brute force kill child Chrome pids with fire
                for pid in self.webdriver_child_pids:
                    try:
                        log.debug(f"Killing {pid}...")
                        process = psutil.Process(pid)
                        process.kill()
                    except psutil.NoSuchProcess:
                        log.debug(f"{pid} not found. Continuing...")
                        pass
            elif self.driver:
                self.driver.quit()

        except Exception as e:
            log.debug(e)
            log.debug(
                "Failed to clean up after web driver.  Please manually close browser."
            )
            return False
        return True

    def is_logged_in(self):
        try:
            text = self.driver.find_element_by_id("nav-link-accountList").text
            return not any(sign_in in text for sign_in in amazon_config["SIGN_IN_TEXT"])
        except NoSuchElementException:

            return False

    def login(self):
        log.info(f"Logging in to {self.amazon_domain}...")

        email_field: WebElement
        remember_me: WebElement
        password_field: WebElement

        # Look for a sign in link
        try:
            skip_link: WebElement = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//a[contains(@href, '/ap/signin/')]")
                )
            )
            skip_link.click()
        except TimeoutException as e:
            log.debug(
                "Timed out waiting for signin link.  Unable to find matching "
                "xpath for '//a[@data-nav-role='signin']'"
            )
            log.exception(e)
            exit(1)

        log.info("Inputting email...")
        try:

            email_field: WebElement = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="ap_email"]'))
            )
            with self.wait_for_page_content_change():
                email_field.clear()
                email_field.send_keys(amazon_config["username"] + Keys.RETURN)
            if self.driver.find_elements_by_xpath('//*[@id="auth-error-message-box"]'):
                log.error("Login failed, delete your credentials file")
                time.sleep(240)
                exit(1)
        except wait.TimeoutException as e:
            log.error("Timed out waiting for email login box.")
            log.exception(e)
            exit(1)

        log.debug("Checking 'rememberMe' checkbox...")
        try:
            remember_me = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@name="rememberMe"]'))
            )
            remember_me.click()
        except NoSuchElementException:
            log.error("Remember me checkbox did not exist")

        log.info("Inputting Password")
        captcha_entry: WebElement = None
        try:
            password_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="ap_password"]'))
            )
            password_field.clear()
            password_field.send_keys(amazon_config["password"])
            # check for captcha
            try:
                captcha_entry = self.driver.find_element_by_xpath(
                    '//*[@id="auth-captcha-guess"]'
                )
            except NoSuchElementException:
                with self.wait_for_page_content_change(timeout=10):
                    password_field.send_keys(Keys.RETURN)

        except NoSuchElementException:
            log.error("Unable to find password input box.  Unable to log in.")
        except wait.TimeoutException:
            log.error("Timeout expired waiting for password input box.")

        if captcha_entry:
            try:
                log.debug("Stuck on a captcha... Lets try to solve it.")
                captcha = AmazonCaptcha.fromdriver(self.driver)
                solution = captcha.solve()
                log.debug(f"The solution is: {solution}")
                if solution == "Not solved":
                    log.debug(
                        f"Failed to solve {captcha.image_link}, lets reload and get a new captcha."
                    )
                    self.send_notification(
                        "Unsolved Captcha", "unsolved_captcha", self.take_screenshots
                    )
                    self.driver.refresh()
                else:
                    self.send_notification(
                        "Solving catpcha", "captcha", self.take_screenshots
                    )
                    with self.wait_for_page_content_change(timeout=10):
                        captcha_entry.clear()
                        captcha_entry.send_keys(solution + Keys.RETURN)

            except Exception as e:
                log.debug(e)
                log.debug("Error trying to solve captcha. Refresh and retry.")
                self.driver.refresh()
                time.sleep(5)

        # Deal with 2FA
        if self.driver.title in amazon_config["TWOFA_TITLES"]:
            log.info("enter in your two-step verification code in browser")
            while self.driver.title in amazon_config["TWOFA_TITLES"]:
                time.sleep(0.2)

        # Deal with Account Fix Up prompt
        if "accountfixup" in self.driver.current_url:
            # Click the skip link
            try:
                skip_link: WebElement = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//a[contains(@id, 'skip-link')]")
                    )
                )
                skip_link.click()
            except TimeoutException as e:
                log.debug(
                    "Timed out waiting for the skip link.  Unable to find matching "
                    "xpath for '//a[contains(@id, 'skip-link')]'"
                )
                log.exception(e)

        log.info(f'Logged in as {amazon_config["username"]}')

    def run(self, delay=5, test=False):
        # Load up the homepage
        with self.wait_for_page_change():
            self.driver.get(f"https://{self.amazon_domain}")

        # Get a valid amazon session for our requests
        if not self.is_logged_in():
            self.login()

        # get cookies
        self.amazon_cookies = self.driver.get_cookies()

        # Verify the configuration file
        if not self.verify():
            # try one more time
            log.debug("Failed to verify... trying more more time")
            self.verify()

        # To keep the user busy https://github.com/jakesgordon/javascript-tetris
        # ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        # uri = pathlib.Path(f"{ROOT_DIR}/../tetris/index.html").as_uri()
        # log.debug(f"Tetris URL: {uri}")
        # self.driver.get(uri)

        message = f"Starting to hunt items at {STORE_NAME}"
        log.info(message)
        self.notification_handler.send_notification(message)
        self.save_screenshot("logged-in")
        print("\n\n")
        recurring_message = "The hunt continues! "
        update_time = get_timeout(1)
        idx = 0
        spinner = ["-", "\\", "|", "/"]
        while self.item_list:
            if time.time() > update_time:
                print(recurring_message, spinner[idx], end="\r")
                update_time = get_timeout(1)
                idx += 1
                if idx == len(spinner):
                    idx = 0

            for item in self.item_list:
                start_time = time.time()
                delay_time = start_time + delay
                successful = False
                qualified_seller = self.find_qualified_seller(item)
                log.debug(
                    f"ASIN check for {item.id} took {time.time()-start_time} seconds."
                )
                if qualified_seller:
                    if self.attempt_atc(offering_id=qualified_seller.offering_id):
                        checkout_attempts = 0
                        self.unknown_title_notification_sent = False
                        while (
                            checkout_attempts
                            < amazon_config["DEFAULT_MAX_CHECKOUT_ATTEMPTS"]
                        ):
                            if self.navigate_pages(test=test):
                                successful = True
                                if self.single_shot:
                                    self.item_list.clear()
                                else:
                                    self.item_list.remove(item)
                                break
                            checkout_attempts += 1
                while time.time() < delay_time:
                    time.sleep(0.01)
                if successful:
                    break
            if self.shuffle:
                random.shuffle(self.item_list)

    @contextmanager
    def wait_for_page_change(self, timeout=30):
        """Utility to help manage selenium waiting for a page to load after an action, like a click"""
        kill_time = get_timeout(timeout)
        old_page = self.driver.find_element_by_tag_name("html")
        yield
        WebDriverWait(self.driver, timeout).until(staleness_of(old_page))
        # wait for page title to be non-blank
        while self.driver.title == "" and time.time() < kill_time:
            time.sleep(0.05)

    @contextmanager
    def wait_for_page_content_change(self, timeout=5):
        """Utility to help manage selenium waiting for a page to load after an action, like a click"""
        old_page = self.driver.find_element_by_tag_name("html")
        yield
        try:
            WebDriverWait(self.driver, timeout).until(EC.staleness_of(old_page))
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//title"))
            )
        except TimeoutException:
            log.debug("Timed out reloading page, trying to continue anyway")
            pass
        except Exception as e:
            log.debug(f"Trying to recover from error: {e}")
            pass
        return None

    def do_button_click(
        self,
        button,
        clicking_text="Clicking button",
        clicked_text="Button clicked",
        fail_text="Could not click button",
    ):
        try:
            with self.wait_for_page_content_change():
                log.debug(clicking_text)
                button.click()
                log.debug(clicked_text)
            return True
        except WebDriverException as e:
            log.debug(fail_text)
            log.debug(e)
            return False

    def find_qualified_seller(self, item) -> SellerDetail or None:
        item_sellers = self.get_item_sellers(item, amazon_config["FREE_SHIPPING"])
        for seller in item_sellers:
            if not self.check_shipping and not free_shipping_check(seller):
                log.debug("Failed shipping hurdle.")
                return
            log.debug("Passed shipping hurdle.")
            if not condition_check(item, seller):
                log.debug("Failed item condition hurdle.")
                return
            log.debug("Passed item condition hurdle.")
            if not price_check(item, seller):
                log.debug("Failed price condition hurdle.")
                return
            log.debug("Pass price condition hurdle.")

            return seller

    def parse_config(self):
        log.debug(f"Processing config file from {CONFIG_FILE_PATH}")
        # Parse the configuration file to get our hunt list
        try:
            with open(CONFIG_FILE_PATH) as json_file:
                config = json.load(json_file)
                self.amazon_domain = config.get("amazon_domain", "smile.amazon.com")

                for key in AMAZON_URLS.keys():
                    AMAZON_URLS[key] = AMAZON_URLS[key].format(
                        domain=self.amazon_domain
                    )

                json_items = config.get("items")
                self.parse_items(json_items)

        except FileNotFoundError:
            log.error(
                f"Configuration file not found at {CONFIG_FILE_PATH}.  Please see {CONFIG_FILE_PATH}_template."
            )
            exit(1)
        log.debug(f"Found {len(self.item_list)} items to track at {STORE_NAME}.")

    def parse_items(self, json_items):
        for json_item in json_items:
            if (
                "max-price" in json_item
                and "asins" in json_item
                and "min-price" in json_item
            ):
                max_price = json_item["max-price"]
                min_price = json_item["min-price"]
                if type(max_price) is str:
                    max_price = parse_price(max_price)
                else:
                    max_price = Price(max_price, currency=None, amount_text=None)
                if type(min_price) is str:
                    min_price = parse_price(min_price)
                else:
                    min_price = Price(min_price, currency=None, amount_text=None)

                if "condition" in json_item:
                    condition = parse_condition(json_item["condition"])
                else:
                    condition = AmazonItemCondition.New

                # Create new instances of an item for each asin specified
                asins_collection = json_item["asins"]
                if isinstance(asins_collection, str):
                    log.warning(
                        f"\"asins\" node needs be an list/array and included in braces (e.g., [])  Attempting to recover {json_item['asins']}"
                    )
                    # did the user forget to put us in an array?
                    asins_collection = asins_collection.split(",")
                for asin in asins_collection:
                    self.item_list.append(
                        FGItem(
                            asin,
                            min_price,
                            max_price,
                            condition=condition,
                        )
                    )
            else:
                log.error(
                    f"Item isn't fully qualified.  Please include asin, min-price and max-price. {json_item}"
                )

    def verify(self):
        log.debug("Verifying item list...")
        items_to_purge = []
        verified = 0
        item_cache_file = os.path.join(
            os.path.dirname(os.path.abspath("__file__")),
            "stores",
            "store_data",
            "item_cache.p",
        )

        if os.path.exists(item_cache_file) and os.path.getsize(item_cache_file) > 0:
            item_cache = pickle.load(open(item_cache_file, "rb"))
        else:
            item_cache = {}

        for idx, item in enumerate(self.item_list):
            # Check the cache first to save the scraping...
            if item.id in item_cache.keys():
                cached_item = item_cache[item.id]
                log.debug(f"Verifying ASIN {cached_item.id} via cache  ...")
                # Update attributes that may have been changed in the config file
                cached_item.condition = item.condition
                cached_item.min_price = item.min_price
                cached_item.max_price = item.max_price
                self.item_list[idx] = cached_item
                log.debug(
                    f"Verified ASIN {cached_item.id} as '{cached_item.short_name}'"
                )
                verified += 1
                continue

            # Verify that the ASIN hits and that we have a valid inventory URL
            pdp_url = f"https://{self.amazon_domain}{PDP_PATH}{item.id}"
            log.debug(f"Verifying at {pdp_url} ...")

            data, status = self.get_html(pdp_url)
            if status == 503:
                # Check for CAPTCHA
                tree = html.fromstring(data)
                captcha_form_element = tree.xpath(
                    "//form[contains(@action,'validateCaptcha')]"
                )
                if captcha_form_element:
                    # Solving captcha and resetting data
                    data, status = solve_captcha(
                        self.session, captcha_form_element[0], pdp_url
                    )

            if status == 200:
                item.furl = furl(
                    f"https://{self.amazon_domain}/{REALTIME_INVENTORY_PATH}{item.id}"
                )
                tree = html.fromstring(data)
                captcha_form_element = tree.xpath(
                    "//form[contains(@action,'validateCaptcha')]"
                )
                if captcha_form_element:
                    tree = solve_captcha(self.session, captcha_form_element[0], pdp_url)

                title = tree.xpath('//*[@id="productTitle"]')
                if len(title) > 0:
                    item.name = title[0].text.strip()
                    item.short_name = (
                        item.name[:40].strip() + "..."
                        if len(item.name) > 40
                        else item.name
                    )
                    log.debug(f"Verified ASIN {item.id} as '{item.short_name}'")
                    item_cache[item.id] = item
                    verified += 1
                else:
                    # TODO: Evaluate if this happens with a 200 code
                    doggo = tree.xpath("//img[@alt='Dogs of Amazon']")
                    if doggo:
                        # Bad ASIN or URL... dump it
                        log.error(
                            f"Bad ASIN {item.id} for the domain or related failure.  Removing from hunt."
                        )
                        items_to_purge.append(item)
                    else:
                        log.debug(
                            f"Unable to verify ASIN {item.id}.  Continuing without verification."
                        )
            else:
                log.error(
                    f"Unable to locate details for {item.id} at {pdp_url}.  Removing from hunt."
                )
                items_to_purge.append(item)

        # Purge any items we didn't find while verifying
        for item in items_to_purge:
            self.item_list.remove(item)

        log.debug(
            f"Verified {verified} out of {len(self.item_list)} items on {STORE_NAME}"
        )
        pickle.dump(item_cache, open(item_cache_file, "wb"))

        return True

    def get_item_sellers(self, item, free_shipping_strings):
        """Parse out information to from the aod-offer nodes populate ItemDetail instances for each item """
        payload = self.get_real_time_data(item)
        sellers = []
        # This is where the parsing magic goes
        log.debug(f"payload is {len(payload)} bytes")
        if len(payload) == 0:
            log.error("Empty Response.  Skipping...")
            return sellers

        tree = html.fromstring(payload)

        # Get the pinned offer, if it exists, by checking for a pinned offer area and add to cart button
        pinned_offer = tree.xpath("//div[@id='aod-sticky-pinned-offer']")
        if not pinned_offer or not tree.xpath(
            "//div[@id='aod-sticky-pinned-offer']//input[@name='submit.addToCart']"
        ):
            log.debug(f"No pinned offer for {item.id} = {item.short_name}")
        else:
            for idx, offer in enumerate(pinned_offer):
                merchant_name = offer.xpath(
                    ".//span[@class='a-size-small a-color-base']"
                )[0].text.strip()
                price_text = offer.xpath(".//span[@class='a-price-whole']")[0].text
                price = parse_price(price_text)
                shipping_cost = get_shipping_costs(offer, free_shipping_strings)
                condition_heading = offer.xpath(".//div[@id='aod-offer-heading']/h5")
                if condition_heading:
                    condition = AmazonItemCondition.from_str(
                        condition_heading[0].text.strip()
                    )
                else:
                    condition = AmazonItemCondition.Unknown
                offers = offer.xpath(f".//input[@name='offeringID.1']")
                offer_id = None
                if len(offers) > 0:
                    offer_id = offers[0].value
                else:
                    log.error("No offer ID found!")

                seller = SellerDetail(
                    merchant_name,
                    price,
                    shipping_cost,
                    condition,
                    offer_id,
                )
                sellers.append(seller)

        offers = tree.xpath("//div[@id='aod-offer']")
        if not offers:
            log.debug(f"No offers found for {item.id} = {item.short_name}")
            return sellers
        for idx, offer in enumerate(offers):
            # This is preferred, but Amazon itself has unique URL parameters that I haven't identified yet
            # merchant_name = offer.xpath(
            #     ".//a[@target='_blank' and contains(@href, 'merch_name')]"
            # )[0].text.strip()
            merchant_name = offer.xpath(".//a[@target='_blank']")[0].text.strip()
            price_text = offer.xpath(
                ".//div[contains(@id, 'aod-price-')]//span[contains(@class,'a-offscreen')]"
            )[0].text
            price = parse_price(price_text)

            shipping_cost = get_shipping_costs(offer, free_shipping_strings)
            condition_heading = offer.xpath(".//div[@id='aod-offer-heading']/h5")
            if condition_heading:
                condition = AmazonItemCondition.from_str(
                    condition_heading[0].text.strip()
                )
            else:
                condition = AmazonItemCondition.Unknown
            offers = offer.xpath(f".//input[@name='offeringID.1']")
            offer_id = None
            if len(offers) > 0:
                offer_id = offers[0].value
            else:
                log.error("No offer ID found!")

            seller = SellerDetail(
                merchant_name,
                price,
                shipping_cost,
                condition,
                offer_id,
            )
            sellers.append(seller)
        return sellers

    def get_real_time_data(self, item):
        log.debug(f"Calling {STORE_NAME} for {item.short_name} using {item.furl.url}")
        data, status = self.get_html(item.furl.url)
        if item.status_code != status:
            # Track when we flip-flop between status codes.  200 -> 204 may be intelligent caching at Amazon.
            # We need to know if it ever goes back to a 200
            log.warning(
                f"{item.short_name} started responding with Status Code {status} instead of {item.status_code}"
            )
            item.status_code = status
        return data

    def attempt_atc(self, offering_id):
        # Open the add.html URL in Selenium
        f = f"{AMAZON_URLS['ATC_URL']}?OfferListingId.1={offering_id}&Quantity.1=1"
        atc_attempts = 0
        while atc_attempts < amazon_config["DEFAULT_MAX_ATC_TRIES"]:
            with self.wait_for_page_content_change(timeout=5):
                if not self.get_page(url=f):
                    atc_attempts += 1
                    continue
            continue_btn = self.wait_get_clickable_amazon_element(key="CONTINUE_ALT")
            if continue_btn:
                if self.do_button_click(
                    button=continue_btn, fail_text="Could not click continue button"
                ):
                    # after clicking the continue button, confirm an item was added to cart
                    if self.get_cart_count() != 0:
                        return True
                    else:
                        log.debug("Nothing added to cart, trying again")
                        self.save_screenshot("atc-fail")
            atc_attempts += 1
        log.debug("reached maximum ATC attempts, returning to stock check")
        return False

    # checkout page navigator
    def navigate_pages(self, test):
        title = self.driver.title
        log.debug(f"Navigating page title: '{title}'")
        # see if this resolves blank page title issue?
        if title == "":
            timeout_seconds = DEFAULT_MAX_TIMEOUT
            log.debug(
                f"Title was blank, checking to find a real title for {timeout_seconds} seconds"
            )
            timeout = get_timeout(timeout=timeout_seconds)
            while True:
                if self.driver.title != "":
                    title = self.driver.title
                    log.debug(f"found a real title: {title}.")
                    break
                if time.time() > timeout:
                    log.debug("Time out reached, page title was still blank.")
                    break
        if title in amazon_config["SIGN_IN_TITLES"]:
            self.login()
        elif title in amazon_config["CAPTCHA_PAGE_TITLES"]:
            self.handle_captcha()
        elif title in amazon_config["SHOPPING_CART_TITLES"]:
            self.handle_cart()
        elif title in amazon_config["CHECKOUT_TITLES"]:
            if self.handle_checkout(test):
                return True
        elif title in amazon_config["ORDER_COMPLETE_TITLES"]:
            if self.handle_order_complete():
                return True
        elif title in amazon_config["PRIME_TITLES"]:
            self.handle_prime_signup()
        elif title in amazon_config["HOME_PAGE_TITLES"]:
            # if home page, something went wrong
            self.handle_home_page()
        elif title in amazon_config["DOGGO_TITLES"]:
            self.handle_doggos()
        elif title in amazon_config["OUT_OF_STOCK"]:
            self.handle_out_of_stock()
        elif title in amazon_config["BUSINESS_PO_TITLES"]:
            self.handle_business_po()
        elif title in amazon_config["ADDRESS_SELECT"]:
            if self.shipping_bypass:
                self.handle_shipping_page()
            else:
                log.warning(
                    "Landed on address selection screen.  Fairgame will NOT select an address for you.  "
                    "Please select necessary options to arrive at the Review Order Page before the next "
                    "refresh, or complete checkout manually.  You have 30 seconds."
                )
                self.handle_unknown_title(title)
        else:
            log.debug(f"title is: [{title}]")
            # see if we can handle blank titles here
            time.sleep(
                3
            )  # wait a few seconds for page to load, since we don't know what we are dealing with
            log.warning(
                "FairGame is not sure what page it is on - will attempt to resolve."
            )
            ###################################################################
            # PERFORM ELEMENT CHECKS TO SEE IF WE CAN FIGURE OUT WHERE WE ARE #
            ###################################################################

            element = None
            # check page for order complete?
            try:
                element = self.driver.find_element_by_xpath(
                    '//*[@class="a-box a-alert a-alert-success"]'
                )
            except NoSuchElementException:
                pass
            if element:
                log.info(
                    "FairGame thinks it completed the purchase, please verify ASAP"
                )
                self.send_notification(
                    message="FairGame may have made a purchase, please confirm ASAP",
                    page_name="unknown-title-purchase",
                    take_screenshot=self.take_screenshots,
                )
                self.send_notification(
                    message="Notifications that follow assume purchase has been made, YOU MUST CONFIRM THIS ASAP",
                    page_name="confirm-purchase",
                    take_screenshot=False,
                )
                self.handle_order_complete()
                return False

            element = None
            # Prime offer page?
            try:
                element = self.get_amazon_element(key="PRIME_NO_THANKS")
            except NoSuchElementException:
                pass
            if element:
                if self.do_button_click(
                    button=element,
                    clicking_text="FairGame thinks it is seeing a Prime Offer, attempting to click No Thanks",
                    fail_text="FairGame could not click No Thanks button",
                ):
                    return False
            # see if a use this address (or similar) button is on page (based on known xpaths). Only check if
            # user has set the shipping_bypass flag
            if self.shipping_bypass:
                if self.handle_shipping_page():
                    return False

            if self.get_cart_count() == 0:
                log.debug("Nothing in cart")
                return False

            ##############################
            # other element checks above #
            ##############################

            # if above checks don't work, just continue on to trying to resolve

            # try to handle an unknown title
            log.debug(
                f"'{title}' is not a known page title. Please create issue indicating the title with a screenshot of page"
            )
            # give user 30 seconds to respond
            self.handle_unknown_title(title=title)
            # check if page title changed, if not, then continue doing other checks:
            if self.driver.title != title:
                log.info(
                    "FairGame thinks user intervened in time, will now continue running"
                )
                return False
            else:
                log.warning(
                    "FairGame does not think the user intervened in time, will attempt other methods to continue"
                )
            log.debug("Going to try and redirect to cart page")
            try:
                with self.wait_for_page_content_change(timeout=10):
                    self.driver.get(AMAZON_URLS["CART_URL"])
            except WebDriverException:
                log.error(
                    "failed to load cart URL, refreshing and returning to handler"
                )
                with self.wait_for_page_content_change(timeout=10):
                    self.driver.refresh()
                return False
            time.sleep(1)  # wait a second for page to load
            # verify cart quantity is not zero
            # note, not using greater than 0, in case there is an error,
            # still want to try and proceed, if possible
            if self.get_cart_count() == 0:
                return False

            log.debug("trying to click proceed to checkout")
            timeout = get_timeout()
            while True:
                try:
                    button = self.get_amazon_element(key="PTC")
                    break
                except NoSuchElementException:
                    button = None
                if time.time() > timeout:
                    log.debug("Could not find and click button")
                    break
            if button:
                if self.do_button_click(
                    button=button,
                    clicking_text="Found ptc button, attempting to click.",
                    clicked_text="Clicked ptc button",
                    fail_text="Could not click button",
                ):
                    return False
                else:
                    with self.wait_for_page_content_change():
                        self.driver.refresh()
                    return False

            # if we made it this far, all attempts to handle page failed, get current page info and return to handler
            log.error(
                "FairGame could not navigate current page, refreshing and returning to handler"
            )
            self.save_page_source(page="unknown")
            self.save_screenshot(page="unknown")
            with self.wait_for_page_content_change():
                self.driver.refresh()
        return False

    def handle_unknown_title(self, title):
        if not self.unknown_title_notification_sent:
            self.notification_handler.play_alarm_sound()
            self.send_notification(
                "User interaction required for checkout! You have 30 seconds!",
                title,
                self.take_screenshots,
            )

            self.unknown_title_notification_sent = True
        for i in range(30, 0, -1):
            log.warning(f"{i}...")
            time.sleep(1)
        return

    # Method to try and click the handle shipping page
    def handle_shipping_page(self):
        element = None
        try:
            element = self.get_amazon_element(key="ADDRESS_SELECT")
        except NoSuchElementException:
            pass
        if element:
            log.warning("FairGame thinks it needs to pick a shipping address.")
            log.warning("It will click whichever ship to this address button it found.")
            log.warning("If this works, VERIFY THE ADDRESS IT SHIPPED TO IMMEDIATELY!")
            self.send_notification(
                message="Clicking ship to address, hopefully this works. VERIFY ASAP!",
                page_name="choose-shipping",
                take_screenshot=self.take_screenshots,
            )
            if self.do_button_click(
                button=element, fail_text="Could not click ship to address button"
            ):
                return True

        # if we make it this far, it failed to click button
        log.error("FairGame cannot find a button to click on the shipping page")
        self.save_screenshot(page="shipping-select-error")
        self.save_page_source(page="shipping-select-error")
        return False

    def handle_prime_signup(self):
        log.debug("Prime offer page popped up, attempting to click No Thanks")
        time.sleep(
            2
        )  # just doing manual wait, sign up for prime if you don't want to deal with this
        button = self.wait_get_amazon_element(key="PRIME_NO_THANKS")
        if button:
            if self.do_button_click(
                button=button,
                clicking_text="Attempting to click No Thanks button on Prime Signup Page",
                fail_text="Failed to click No Thanks button on Prime Signup Page",
            ):
                return

        # If we get to this point, there was either no button, or we couldn't click it (exception hit above)
        log.error("Prime offer page popped up, user intervention required")
        self.notification_handler.play_alarm_sound()
        self.notification_handler.send_notification(
            "Prime offer page popped up, user intervention required"
        )
        timeout = get_timeout(timeout=60)
        while self.driver.title in amazon_config["PRIME_TITLES"]:
            if time.time() > timeout:
                log.debug("user did not intervene in time, will try and refresh page")
                with self.wait_for_page_content_change():
                    self.driver.refresh()
                break
            time.sleep(0.5)

    def handle_home_page(self):
        log.debug("On home page, trying to get back to checkout")
        button = self.wait_get_amazon_element(key="CART_BUTTON")
        current_page = self.driver.title
        if button:
            if self.do_button_click(button=button):
                return True
        self.send_notification(
            "Could not navigate to cart from homepage, user intervention required",
            "home-page-error",
            self.take_screenshots,
        )
        timeout = get_timeout(timeout=300)
        while self.driver.title == current_page:
            time.sleep(0.25)
            if time.time() > timeout:
                log.debug("user failed to intervene in time, returning to stock check")
                return False

    # only returns false if it shouldn't continue
    def handle_cart(self):
        self.start_time_atc = time.time()
        if self.get_cart_count() == 0:
            log.debug("You have no items in cart.")
            return False

        log.debug("Looking for Proceed To Checkout button...")
        try:
            self.save_screenshot("ptc-page")
        except:
            pass

        button = self.wait_get_amazon_element(key="PTC")
        if button:
            log.debug("Found Checkout Button")
            if self.detailed:
                self.send_notification(
                    message="Attempting to Proceed to Checkout",
                    page_name="ptc",
                    take_screenshot=self.take_screenshots,
                )
            if self.do_button_click(button=button):
                return True
        # failed, refresh return to navigator
        with self.wait_for_page_content_change():
            self.driver.refresh()
        return True

    def handle_checkout(self, test):
        pyo_buttons = self.wait_get_amazon_elements(key="PYO")
        # shuffle elements so it doesn't start the same every time, in case this is called again
        random.shuffle(pyo_buttons)

        if test:
            log.info(f"Found button {pyo_buttons[0].text}, but this is a test")
            log.info("will not try to complete order")
            log.info(f"test time took {time.time() - self.start_time_atc} to check out")
            return True

        for button in pyo_buttons:
            if (
                button.is_enabled()
                and button.is_displayed()
                and self.do_button_click(button=button)
            ):
                if self.driver.title not in amazon_config["CHECKOUT_TITLES"]:
                    return True

        if self.shipping_bypass:
            try:
                button = self.get_amazon_element(key="ADDRESS_SELECT")
            except NoSuchElementException:
                button = None

            if button:
                if self.do_button_click(button=button):
                    return True

        # failed to do anything
        self.save_page_source("pyo-error")
        self.send_notification(
            "Error in placing order.  Please check browser window.",
            "pyo-error",
            self.take_screenshots,
        )
        with self.wait_for_page_content_change():
            self.driver.refresh()
        return False

    def handle_order_complete(self):
        log.info("Order Placed.")
        self.send_notification("Order placed.", "order-placed", self.take_screenshots)
        log.info(f"checkout completed in {time.time() - self.start_time_atc} seconds")

    def handle_doggos(self):
        self.notification_handler.send_notification(
            "You got dogs, bot may not work correctly. Ending Checkout"
        )

    def handle_out_of_stock(self):
        self.notification_handler.send_notification(
            "Carted it, but went out of stock, better luck next time."
        )

    def handle_captcha(self, check_presence=True):
        # wait for captcha to load
        log.debug("Waiting for captcha to load.")
        time.sleep(3)
        try:
            if not check_presence or self.driver.find_element_by_xpath(
                '//form[contains(@action,"validateCaptcha")]'
            ):
                try:
                    log.debug("Stuck on a captcha... Lets try to solve it.")
                    captcha = AmazonCaptcha.fromdriver(self.driver)
                    solution = captcha.solve()
                    log.debug(f"The solution is: {solution}")
                    if solution == "Not solved":
                        log.debug(
                            f"Failed to solve {captcha.image_link}, lets reload and get a new captcha."
                        )
                        self.driver.refresh()
                        time.sleep(3)
                    else:
                        self.send_notification(
                            "Solving catpcha", "captcha", self.take_screenshots
                        )
                        with self.wait_for_page_content_change():
                            self.driver.find_element_by_xpath(
                                '//*[@id="captchacharacters"]'
                            ).send_keys(solution + Keys.RETURN)
                except Exception as e:
                    log.debug(e)
                    log.debug("Error trying to solve captcha. Refresh and retry.")
                    with self.wait_for_page_content_change():
                        self.driver.refresh()
        except NoSuchElementException:
            log.debug("captcha page does not contain captcha element")
            log.debug("refreshing")
            with self.wait_for_page_content_change():
                self.driver.refresh()

    def handle_business_po(self):
        log.debug("On Business PO Page, Trying to move on to checkout")
        button = self.wait_get_clickable_amazon_element("BUSINESS_PO_BUTTON")
        if button:
            if self.do_button_click(button=button):
                return True
        else:
            log.info(
                "Could not find the continue button, user intervention required, complete checkout manually"
            )
            self.notification_handler.send_notification(
                "Could not click continue button, user intervention required"
            )
            time.sleep(300)
            return None

    def get_html(self, url):
        """Unified mechanism to get content to make changing connection clients easier"""
        f = furl(url)
        if not f.scheme:
            f.set(scheme="https")
        response = self.session.get(f.url, headers=HEADERS)
        return response.text, response.status_code

    # returns negative number if cart element does not exist, returns number if cart exists
    def get_cart_count(self):
        # check if cart number is on the page, if cart items = 0
        try:
            element = self.get_amazon_element(key="CART")
        except NoSuchElementException:
            return -1
        if element:
            try:
                return int(element.text)
            except Exception as e:
                log.debug("Error converting cart number to integer")
                log.debug(e)
                return -1

    def wait_get_amazon_element(self, key):
        xpath = join_xpaths(amazon_config["XPATHS"][key])
        if wait_for_element_by_xpath(self.driver, xpath):
            return self.get_amazon_element(key=key)
        else:
            return None

    def wait_get_clickable_amazon_element(self, key):
        xpath = join_xpaths(amazon_config["XPATHS"][key])
        if wait_for_element_by_xpath(self.driver, xpath):
            try:
                return WebDriverWait(self.driver, timeout=5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
            except TimeoutException:
                return None
        else:
            return None

    def wait_get_amazon_elements(self, key):
        xpath = join_xpaths(amazon_config["XPATHS"][key])
        if wait_for_element_by_xpath(self.driver, xpath):
            return self.get_amazon_elements(key=key)
        else:
            return None

    def get_amazon_element(self, key):
        return self.driver.find_element_by_xpath(
            join_xpaths(amazon_config["XPATHS"][key])
        )

    def get_amazon_elements(self, key):
        return self.driver.find_elements_by_xpath(
            join_xpaths(amazon_config["XPATHS"][key])
        )

    def get_page(self, url):
        try:
            with self.wait_for_page_content_change():
                self.driver.get(url=url)
            return True
        except TimeoutException:
            log.debug("Failed to load page within timeout period")
            return False
        except Exception as e:
            log.debug(f"Other error encountered while loading page: {e}")

    def save_screenshot(self, page):
        file_name = get_timestamp_filename("screenshots/screenshot-" + page, ".png")
        try:
            self.driver.save_screenshot(file_name)
            return file_name
        except TimeoutException:
            log.debug("Timed out taking screenshot, trying to continue anyway")
            pass
        except Exception as e:
            log.debug(f"Trying to recover from error: {e}")
            pass
        return None

    def save_page_source(self, page):
        """Saves DOM at the current state when called.  This includes state changes from DOM manipulation via JS"""
        file_name = get_timestamp_filename("html_saves/" + page + "_source", "html")

        page_source = self.driver.page_source
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(page_source)

    def check_captcha(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                captcha_element = self.get_amazon_element(key="CAPTCHA_VALIDATE")
            except NoSuchElementException:
                captcha_element = None
            if captcha_element:
                captcha_link = self.driver.page_source.split('<img src="')[1].split('">')[0]  # extract captcha link
                captcha = AmazonCaptcha.fromlink(captcha_link)  # pass it to `fromlink` class method
                if captcha == "Not solved":
                    log.info(
                        f"Failed to solve {captcha.image_link}"
                    )
                    if self.wait_on_captcha_fail:
                        log.info(
                            "Will wait up to 60 seconds for user to solve captcha"
                        )
                        self.send(
                            "User Intervention Required - captcha check",
                            "captcha",
                            self.take_screenshots,
                        )
                        with self.wait_for_page_content_change():
                            timeout = self.get_timeout(timeout=60)
                            current_page = self.driver.title
                            while (
                                    time.time() < timeout
                                    and self.driver.title == current_page
                            ):
                                time.sleep(0.5)
                            # check above is not true, then we must have passed captcha, return back to nav handler
                            # Otherwise refresh page to try again - either way, returning to nav page handler
                            if (
                                    time.time() > timeout
                                    and self.driver.title == current_page
                            ):
                                log.info(
                                    "User intervention did not occur in time - will attempt to refresh page and try again"
                                )
                                return False
                            elif self.driver.title != current_page:
                                return True
                    else:
                        return False
                else:  # solved!
                    # take screenshot if user asked for detailed
                    if self.detailed:
                        self.send_notification(
                            "Solving catpcha", "captcha", self.take_screenshots
                        )
                    try:
                        captcha_field = self.get_amazon_element(key="CAPTCHA_TEXT_FIELD")
                    except NoSuchElementException:
                        log.debug("Could not locate captcha entry field")
                        captcha_field = None
                    if captcha_field:
                        try:
                            check_password = self.get_amazon_element(key="PASSWORD_TEXT_FIELD")
                        except NoSuchElementException:
                            check_password = None
                        if check_password:
                            check_password.clear()
                            check_password.send_keys(amazon_config["password"])
                        with self.wait_for_page_content_change():
                            captcha_field.send_keys(captcha + Keys.RETURN)
                        return True
                    else:
                        return False
            return f(*args, **kwargs)
        return wrapper


def parse_condition(condition: str) -> AmazonItemCondition:
    return AmazonItemCondition[condition]


def min_total_price(seller: SellerDetail):
    return seller.selling_price


def new_first(seller: SellerDetail):
    return seller.condition


def create_driver(options):
    try:
        return webdriver.Chrome(executable_path=binary_path, options=options)
    except Exception as e:
        log.error(e)
        log.error(
            "If you have a JSON warning above, try deleting your .profile-amz folder"
        )
        log.error(
            "If that's not it, you probably have a previous Chrome window open. You should close it."
        )
        exit(1)


def modify_browser_profile():
    # Delete crashed, so restore pop-up doesn't happen
    path_to_prefs = os.path.join(
        os.path.dirname(os.path.abspath("__file__")),
        ".profile-amz",
        "Default",
        "Preferences",
    )
    try:
        with fileinput.FileInput(path_to_prefs, inplace=True) as file:
            for line in file:
                print(line.replace("Crashed", "none"), end="")
    except FileNotFoundError:
        pass


def set_options(prefs, slow_mode):
    options.add_experimental_option("prefs", prefs)
    options.add_argument(f"user-data-dir=.profile-amz")
    if not slow_mode:
        options.set_capability("pageLoadStrategy", "none")


def get_prefs(no_image):
    prefs = {
        "profile.password_manager_enabled": False,
        "credentials_enable_service": False,
    }
    if no_image:
        prefs["profile.managed_default_content_settings.images"] = 2
    else:
        prefs["profile.managed_default_content_settings.images"] = 0
    return prefs


def create_webdriver_wait(driver, wait_time=10):
    return WebDriverWait(driver, wait_time)


def get_webdriver_pids(driver):
    pid = driver.service.process.pid
    driver_process = psutil.Process(pid)
    children = driver_process.children(recursive=True)
    webdriver_child_pids = []
    for child in children:
        webdriver_child_pids.append(child.pid)
    return webdriver_child_pids


def get_timeout(timeout=DEFAULT_MAX_TIMEOUT):
    return time.time() + timeout


def wait_for_element_by_xpath(d, xpath, timeout=10):
    try:
        WebDriverWait(d, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
    except TimeoutException:
        log.debug(f"failed to find {xpath}")
        return False

    return True


def join_xpaths(xpath_list, separator=" | "):
    return separator.join(xpath_list)


def get_timestamp_filename(name, extension):
    """Utility method to create a filename with a timestamp appended to the root and before
    the provided file extension"""
    now = datetime.now()
    date = now.strftime("%m-%d-%Y_%H_%M_%S")
    if extension.startswith("."):
        return name + "_" + date + extension
    else:
        return name + "_" + date + "." + extension
