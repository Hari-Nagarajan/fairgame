import fileinput
import json
import os
import pickle
import platform
import random

import stdiomask
import time
import typing
from contextlib import contextmanager
from datetime import datetime
from utils.debugger import debug
import secrets
from fake_useragent import UserAgent
import asyncio

import re

import psutil
import requests
from amazoncaptcha import AmazonCaptcha
from chromedriver_py import binary_path
from furl import furl
from lxml import html
from price_parser import parse_price, Price
from selenium import webdriver

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
    merchant_check,
)

from utils.misc import parse_html_source
from notifications.notifications import NotificationHandler
from stores.basestore import BaseStoreHandler
from utils.logger import log
from utils.selenium_utils import enable_headless, options

from functools import wraps

from stores.amazon_monitoring import AmazonMonitoringHandler
from stores.amazon_checkout import AmazonCheckoutHandler

# PDP_URL = "https://smile.amazon.com/gp/product/"
# AMAZON_DOMAIN = "www.amazon.com.au"
# AMAZON_DOMAIN = "www.amazon.com.br"
# AMAZON_DOMAIN = "www.amazon.ca"
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
    "PTC_GET": "https://{domain}/gp/cart/view.html/ref=lh_co_dup?ie=UTF8&proceedToCheckout.x=129",
    "PYO_POST": "https://{domain}/gp/buy/spc/handlers/static-submit-decoupled.html/ref=ox_spc_place_order?",
}

PDP_PATH = f"/dp/"
REALTIME_INVENTORY_PATH = f"gp/aod/ajax?asin="

CONFIG_FILE_PATH = "config/amazon_requests_config.json"
PROXY_FILE_PATH = "config/proxies.json"
STORE_NAME = "Amazon"
DEFAULT_MAX_TIMEOUT = 10

# Request
HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, sdch, br",
    "content-type": "application/x-www-form-urlencoded",
}
amazon_config = {}


class AmazonStoreHandler(BaseStoreHandler):
    http_client = False
    http_20_client = False
    http_session = True

    def __init__(
        self,
        notification_handler: NotificationHandler,
        single_shot=False,
        encryption_pass=None,
        transfer_headers=False,
        use_atc_mode=False,
    ) -> None:
        super().__init__()

        self.shuffle = True
        self.is_test = False
        self.selenium_refresh_offset = 7200
        self.selenium_refresh_time = 0

        self.notification_handler = notification_handler
        self.item_list: typing.List[FGItem] = []
        self.stock_checks = 0
        self.start_time = int(time.time())
        self.amazon_domain = "smile.amazon.com"
        self.webdriver_child_pids = []
        self.single_shot = single_shot
        self.transfer_headers = transfer_headers
        self.buy_it_now = not use_atc_mode
        self.loop = asyncio.get_event_loop()

        if not self.buy_it_now:
            log.warning("Using legacy add-to-cart mode instead of turbo_initiate")

        self.ua = UserAgent()

        from cli.cli import global_config

        global amazon_config
        amazon_config = global_config.get_amazon_config(encryption_pass)
        self.profile_path = global_config.get_browser_profile_path()

        # Load up our configuration
        self.parse_config()

    def __del__(self):
        message = f"Shutting down {STORE_NAME} Store Handler."
        log.info(message)
        self.notification_handler.send_notification(message)

    async def run_async(self, checkout_tasks=1):
        log.debug("Creating checkout queue")
        queue = asyncio.Queue()
        log.debug("Creating checkout handler")
        amazon_checkout = AmazonCheckoutHandler(
            notification_handler=self.notification_handler,
            amazon_config=amazon_config,
            cookie_list=[
                "session-id",
                "x-amz-captcha-1",
                "x-amz-captcha-2",
                "ubid-main",
                "x-main",
                "at-main",
                "sess-at-main",
            ],
            profile_path=self.profile_path,
        )
        log.debug("Creating monitoring handler")
        amazon_monitoring = AmazonMonitoringHandler(
            notification_handler=self.notification_handler,
            loop=self.loop,
            item_list=self.item_list,
            amazon_config=amazon_config,
            tasks=checkout_tasks,
        )
        log.debug("Creating checkout worker and monitoring task(s)")
        await asyncio.gather(
            amazon_checkout.checkout_worker(queue=queue),
            *[
                session.stock_check(queue)
                for session in amazon_monitoring.sessions_list
            ],
        )

        return

    def wait_for_delay(self, delay_time):
        """wait until delay_time

        Any checks or housekeeping should be done in this function in
        order to group all delay between stock checkes"""
        if time.time() > self.selenium_refresh_time:
            self.selenium_login_cookies(
                session_list=[self.session_checkout],
                all_cookies=self.all_cookies,
                transfer_headers=self.transfer_headers,
            )
            self.selenium_refresh_time = time.time() + self.selenium_refresh_offset

        # initialize amazon session cookie, if missing from _next_ proxy
        if (
            self.proxy_sessions
            and len(self.proxy_sessions) > 1
            and not self.proxy_sessions[1].cookies
        ):
            self.proxy_sessions[1].get(f"https://{self.amazon_domain}")

        # sleep remainder of delay_time
        time_left = delay_time - time.time()
        if time_left > 0:
            time.sleep(time_left)

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

                if "merchant_id" in json_item:
                    merchant_id = json_item["merchant_id"]
                else:
                    merchant_id = "any"

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
                            merchant_id=merchant_id,
                            furl=furl(
                                url=f"https://smile.amazon.com/gp/aod/ajax?asin={asin}"
                            ),
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
                cached_item.pdp_url = item.pdp_url
                cached_item.condition = item.condition
                cached_item.min_price = item.min_price
                cached_item.max_price = item.max_price
                cached_item.merchant_id = item.merchant_id
                self.item_list[idx] = cached_item
                log.debug(
                    f"Verified ASIN {cached_item.id} as '{cached_item.short_name}'"
                )
                verified += 1
                continue

            # Verify that the ASIN hits and that we have a valid inventory URL
            item.pdp_url = f"https://{self.amazon_domain}{PDP_PATH}{item.id}"
            log.debug(f"Verifying at {item.pdp_url} ...")

            session = self.session_checkout
            data, status = self.get_html(item.pdp_url, s=session)
            if not data and not status:
                log.debug("Response empty, skipping item")
                continue
            if status == 503:
                # Check for CAPTCHA
                tree = parse_html_source(data)
                if tree is None:
                    continue
                captcha_form_element = tree.xpath(
                    "//form[contains(@action,'validateCaptcha')]"
                )
                if captcha_form_element:
                    # Solving captcha and resetting data
                    data, status = solve_captcha(
                        session, captcha_form_element[0], item.pdp_url
                    )

            if status == 200:
                item.furl = furl(
                    f"https://{self.amazon_domain}/{REALTIME_INVENTORY_PATH}{item.id}"
                )
                tree = parse_html_source(data)
                if tree is None:
                    continue
                captcha_form_element = tree.xpath(
                    "//form[contains(@action,'validateCaptcha')]"
                )
                if captcha_form_element:
                    data, status = solve_captcha(
                        session, captcha_form_element[0], item.pdp_url
                    )
                    if status != 200:
                        log.debug(f"ASIN {item.id} failed, skipping...")
                        continue
                    tree = parse_html_source(data)
                    if tree is None:
                        continue

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
                    f"Unable to locate details for {item.id} at {item.pdp_url}.  Removing from hunt."
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

    def get_real_time_data(self, item: FGItem, session: requests.Session):
        log.debug(f"Calling {STORE_NAME} for {item.short_name} using {item.furl.url}")
        if self.proxies:
            log.debug(f"Using proxy: {self.proxies[0]}")
        params = {"anticache": str(secrets.token_urlsafe(32))}
        item.furl.args.update(params)
        data, status = self.get_html(item.furl.url, s=session)

        if item.status_code != status:
            # Track when we flip-flop between status codes.  200 -> 204 may be intelligent caching at Amazon.
            # We need to know if it ever goes back to a 200
            log.warning(
                f"{item.short_name} started responding with Status Code {status} instead of {item.status_code}"
            )
            item.status_code = status
        return data

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

    @debug
    def get_html(self, url, s: requests.Session):
        """Unified mechanism to get content to make changing connection clients easier"""
        f = furl(url)
        if not f.scheme:
            f.set(scheme="https")
        try:
            response = s.get(f.url, timeout=5)
        except requests.exceptions.RequestException as e:
            log.debug(e)
            log.debug("timeout on get_html")
            return None, None
        except Exception as e:
            log.debug(e)
            return None, None
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

    def check_captcha_selenium(self, f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            with self.wait_for_page_content_change():
                f(*args, **kwargs)
            try:
                captcha_element = self.get_amazon_element(key="CAPTCHA_VALIDATE")
            except NoSuchElementException:
                captcha_element = None
            if captcha_element:
                captcha_link = self.driver.page_source.split('<img src="')[1].split(
                    '">'
                )[
                    0
                ]  # extract captcha link
                captcha = AmazonCaptcha.fromlink(
                    captcha_link
                )  # pass it to `fromlink` class method
                if captcha == "Not solved":
                    log.info(f"Failed to solve {captcha.image_link}")
                    if self.wait_on_captcha_fail:
                        log.info("Will wait up to 60 seconds for user to solve captcha")
                        self.send_notification(
                            "User Intervention Required - captcha check",
                            "captcha",
                            self.take_screenshots,
                        )
                        with self.wait_for_page_content_change():
                            timeout = get_timeout(timeout=60)
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
                        captcha_field = self.get_amazon_element(
                            key="CAPTCHA_TEXT_FIELD"
                        )
                    except NoSuchElementException:
                        log.debug("Could not locate captcha entry field")
                        captcha_field = None
                    if captcha_field:
                        try:
                            check_password = self.get_amazon_element(
                                key="PASSWORD_TEXT_FIELD"
                            )
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
            return True

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


def set_options(profile_path, prefs, slow_mode=True):
    options.add_experimental_option("prefs", prefs)
    options.add_argument(f"user-data-dir={profile_path}")
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


def transfer_selenium_cookies(
    d: webdriver.Chrome, s: requests.Session, all_cookies=False
):
    # get cookies, might use these for checkout later, with no cookies on
    # cookie_names = ["session-id", "ubid-main", "x-main", "at-main", "sess-at-main"]
    # for c in self.driver.get_cookies():
    #     if c["name"] in cookie_names:
    #         self.amazon_cookies[c["name"]] = c["value"]

    # update session with cookies from Selenium
    cookie_names = ["session-id", "ubid-main", "x-main", "at-main", "sess-at-main"]
    for c in d.get_cookies():
        if all_cookies or c["name"] in cookie_names:
            s.cookies.set(name=c["name"], value=c["value"])
            log.dev(f'Set Cookie {c["name"]} as value {c["value"]}')


def save_html_response(filename, status, body):
    """Saves response body"""
    file_name = get_timestamp_filename(
        "html_saves/" + filename + "_" + str(status) + "_requests_source", "html"
    )

    page_source = body
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(page_source)


def captcha_handler(session, page_source, domain):
    data = page_source
    status = 200
    tree = parse_html_source(data)
    if tree is None:
        data = None
        status = None
        return data, status
    CAPTCHA_RETRY = 5
    retry = 0
    # loop until no captcha in return page, or max captcha tries reached
    while (captcha_element := has_captcha(tree)) and (retry < CAPTCHA_RETRY):
        data, status = solve_captcha(
            session=session, form_element=captcha_element[0], domain=domain
        )
        tree = parse_html_source(data)
        if tree is None:
            data = None
            status = None
            return data, status
        retry += 1
    if captcha_element:
        data = None
        status = None
    return data, status


def has_captcha(tree):
    return tree.xpath("//form[contains(@action,'validateCaptcha')]")
