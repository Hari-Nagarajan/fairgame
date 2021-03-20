#      FairGame - Automated Purchasing Program
#      Copyright (C) 2021  Hari Nagarajan
#
#      This program is free software: you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#      The author may be contacted through the project's GitHub, at:
#      https://github.com/Hari-Nagarajan/fairgame

import fileinput
import json
import math
import os
import platform
import time
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import List

import psutil
from amazoncaptcha import AmazonCaptcha
from chromedriver_py import binary_path  # this will get you the path variable
from furl import furl
from lxml import html
from price_parser import parse_price, Price
from pypresence import exceptions as pyexceptions
from selenium import webdriver
from selenium.common import exceptions as sel_exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils import discord_presence as presence
from utils.debugger import debug
from utils.logger import log
from utils.selenium_utils import options, enable_headless

# Optional OFFER_URL is:     "OFFER_URL": "https://{domain}/dp/",
AMAZON_URLS = {
    "BASE_URL": "https://{domain}/",
    "ALT_OFFER_URL": "https://{domain}/gp/offer-listing/",
    "OFFER_URL": "https://{domain}/dp/",
    "CART_URL": "https://{domain}/gp/cart/view.html",
    "ATC_URL": "https://{domain}/gp/aws/cart/add.html",
}
CHECKOUT_URL = "https://{domain}/gp/cart/desktop/go-to-checkout.html/ref=ox_sc_proceed?partialCheckoutCart=1&isToBeGiftWrappedBefore=0&proceedToRetailCheckout=Proceed+to+checkout&proceedToCheckout=1&cartInitiateId={cart_id}"

AUTOBUY_CONFIG_PATH = "config/amazon_config.json"

BUTTON_XPATHS = [
    '//input[@name="placeYourOrder1"]',
    '//*[@id="submitOrderButtonId"]/span/input',
    '//*[@id="bottomSubmitOrderButtonId"]/span/input',
    '//*[@id="placeYourOrder"]/span/input',
]
# old xpaths, not sure these were needed for current work flow
# '//*[@id="orderSummaryPrimaryActionBtn"]',
# '//input[@name="placeYourOrder1"]',
# '//*[@id="hlb-ptc-btn-native"]',
# '//*[@id="sc-buy-box-ptc-button"]/span/input',
# '//*[@id="buy-now-button"]',
# Prime popup
# //*[@id="primeAutomaticPopoverAdContent"]/div/div/div[1]/a
# //*[@id="primeAutomaticPopoverAdContent"]/div/div/div[1]/a
FREE_SHIPPING_PRICE = parse_price("0.00")

DEFAULT_MAX_CHECKOUT_LOOPS = 20
DEFAULT_MAX_PTC_TRIES = 3
DEFAULT_MAX_PYO_TRIES = 3
DEFAULT_MAX_ATC_TRIES = 3
DEFAULT_MAX_WEIRD_PAGE_DELAY = 5
DEFAULT_PAGE_WAIT_DELAY = 0.5  # also serves as minimum wait for randomized delays
DEFAULT_MAX_PAGE_WAIT_DELAY = 1.0  # used for random page wait delay
MAX_CHECKOUT_BUTTON_WAIT = 3  # integers only
DEFAULT_REFRESH_DELAY = 3
DEFAULT_MAX_TIMEOUT = 10
DEFAULT_MAX_URL_FAIL = 5

amazon_config = {}


class Amazon:
    def __init__(
        self,
        notification_handler,
        headless=False,
        checkshipping=False,
        detailed=False,
        used=False,
        single_shot=False,
        no_screenshots=False,
        disable_presence=False,
        slow_mode=False,
        no_image=False,
        encryption_pass=None,
        log_stock_check=False,
        shipping_bypass=False,
        alt_offers=False,
        wait_on_captcha_fail=False,
    ):
        self.notification_handler = notification_handler
        self.asin_list = []
        self.reserve_min = []
        self.reserve_max = []
        self.checkshipping = checkshipping
        self.button_xpaths = BUTTON_XPATHS
        self.detailed = detailed
        self.used = used
        if used:
            self.condition = AmazonItemCondition.UsedAcceptable
        else:
            self.condition = AmazonItemCondition.New
        self.single_shot = single_shot
        self.take_screenshots = not no_screenshots
        self.start_time = time.time()
        self.start_time_atc = 0
        self.webdriver_child_pids = []
        self.driver = None
        self.refresh_delay = DEFAULT_REFRESH_DELAY
        self.testing = False
        self.slow_mode = slow_mode
        self.setup_driver = True
        self.headless = headless
        self.no_image = no_image
        self.log_stock_check = log_stock_check
        self.shipping_bypass = shipping_bypass
        self.unknown_title_notification_sent = False
        self.alt_offers = alt_offers
        self.wait_on_captcha_fail = wait_on_captcha_fail

        presence.enabled = not disable_presence

        global amazon_config
        from cli.cli import global_config

        amazon_config = global_config.get_amazon_config(encryption_pass)
        self.profile_path = global_config.get_browser_profile_path()

        try:
            presence.start_presence()
        except Exception in pyexceptions:
            log.error("Discord presence failed to load")
            presence.enabled = False

        # Create necessary sub-directories if they don't exist
        if not os.path.exists("screenshots"):
            try:
                os.makedirs("screenshots")
            except:
                raise

        if not os.path.exists("html_saves"):
            try:
                os.makedirs("html_saves")
            except:
                raise

        if os.path.exists(AUTOBUY_CONFIG_PATH):
            with open(AUTOBUY_CONFIG_PATH) as json_file:
                try:
                    config = json.load(json_file)
                    self.asin_groups = int(config["asin_groups"])
                    self.amazon_website = config.get(
                        "amazon_website", "smile.amazon.com"
                    )
                    for x in range(self.asin_groups):
                        self.asin_list.append(config[f"asin_list_{x + 1}"])
                        self.reserve_min.append(float(config[f"reserve_min_{x + 1}"]))
                        self.reserve_max.append(float(config[f"reserve_max_{x + 1}"]))
                    # assert isinstance(self.asin_list, list)
                except Exception as e:
                    log.error(f"{e} is missing")
                    log.error(
                        "amazon_config.json file not formatted properly: https://github.com/Hari-Nagarajan/fairgame/wiki/Usage#json-configuration"
                    )
                    exit(0)
        else:
            log.error(
                "No config file found, see here on how to fix this: https://github.com/Hari-Nagarajan/fairgame/wiki/Usage#json-configuration"
            )
            exit(0)

        if not self.create_driver(self.profile_path):
            exit(1)

        for key in AMAZON_URLS.keys():
            AMAZON_URLS[key] = AMAZON_URLS[key].format(domain=self.amazon_website)
        if self.alt_offers:
            log.info("Using alternate page for offer parsing.")
            self.ACTIVE_OFFER_URL = AMAZON_URLS["ALT_OFFER_URL"]
        else:
            self.ACTIVE_OFFER_URL = AMAZON_URLS["OFFER_URL"]

    def run(self, delay=DEFAULT_REFRESH_DELAY, test=False):
        self.testing = test
        self.refresh_delay = delay
        self.show_config()

        log.info("Waiting for home page.")
        while True:
            try:
                self.get_page(url=AMAZON_URLS["BASE_URL"])
                break
            except sel_exceptions.WebDriverException:
                log.error(
                    "Couldn't talk to "
                    + AMAZON_URLS["BASE_URL"]
                    + ", if the address is right, there might be a network outage..."
                )
                time.sleep(3)
                pass
        cart_quantity = self.get_cart_count()
        if cart_quantity > 0:
            log.warning(f"Found {cart_quantity} item(s) in your cart.")
            log.info("Delete all item(s) in cart before starting bot.")
            self.driver.get(AMAZON_URLS["CART_URL"])
            log.info("Exiting in 30 seconds...")
            time.sleep(30)
            return
        self.handle_startup()
        if not self.is_logged_in():
            self.login()
        self.notification_handler.play_notify_sound()
        self.send_notification(
            "Bot Logged in and Starting up", "Start-Up", self.take_screenshots
        )
        if self.get_cart_count() > 0:
            log.warning(f"Found {cart_quantity} item(s) in your cart.")
            log.info("Delete all item(s) in cart before starting bot.")
            self.driver.get(AMAZON_URLS["CART_URL"])
            log.info("Exiting in 30 seconds...")
            time.sleep(30)
            return

        continue_stock_check = True

        log.info("Checking stock for items.")

        while continue_stock_check:
            self.unknown_title_notification_sent = False
            asin = self.run_asins(delay)
            # found something in stock and under reserve
            # initialize loop limiter variables
            self.try_to_checkout = True
            self.checkout_retry = 0
            self.order_retry = 0
            loop_iterations = 0
            self.great_success = False
            while self.try_to_checkout:
                try:
                    self.navigate_pages(test)
                # if for some reason page transitions in the middle of checking elements, don't break the program
                except sel_exceptions.StaleElementReferenceException:
                    pass
                # if successful after running navigate pages, remove the asin_list from the list
                if (
                    not self.try_to_checkout
                    and not self.single_shot
                    and self.great_success
                ):
                    self.remove_asin_list(asin)
                # checkout loop limiters
                elif self.checkout_retry > DEFAULT_MAX_PTC_TRIES:
                    self.try_to_checkout = False
                    self.fail_to_checkout_note()
                elif self.order_retry > DEFAULT_MAX_PYO_TRIES:
                    self.try_to_checkout = False
                    self.fail_to_checkout_note()
                loop_iterations += 1
                if loop_iterations > DEFAULT_MAX_CHECKOUT_LOOPS:
                    self.fail_to_checkout_note()
                    self.try_to_checkout = False
            # if no items left it list, let loop end
            if not self.asin_list:
                continue_stock_check = False
        runtime = time.time() - self.start_time
        log.info(f"FairGame bot ran for {runtime} seconds.")
        time.sleep(10)  # add a delay to shut stuff done

    def fail_to_checkout_note(self):
        log.info(
            "It's likely that the product went out of stock before FairGame could checkout."
        )
        log.info(
            "Also verify that your default shipping and payment options are selected and work correctly."
        )
        log.info("FairGame WILL NOT select shipping and payment options for you.")
        log.info("Better luck next time.")

    @debug
    def handle_startup(self):
        time.sleep(self.page_wait_delay())
        if self.is_logged_in():
            log.info("Already logged in")
        else:
            log.info("Lets log in.")

            is_smile = "smile" in AMAZON_URLS["BASE_URL"]
            xpath = (
                '//*[@id="ge-hello"]/div/span/a'
                if is_smile
                else '//*[@id="nav-link-accountList"]/div/span'
            )

            try:
                self.driver.find_element_by_xpath(xpath).click()
            except sel_exceptions.NoSuchElementException:
                log.error("Log in button does not exist")
            log.info("Wait for Sign In page")
            time.sleep(self.page_wait_delay())

    @debug
    def is_logged_in(self):
        try:
            text = self.driver.find_element_by_id("nav-link-accountList").text
            return not any(sign_in in text for sign_in in amazon_config["SIGN_IN_TEXT"])
        except sel_exceptions.NoSuchElementException:

            return False

    @debug
    def login(self):
        log.info("Email")
        email_field = None
        password_field = None
        timeout = self.get_timeout()
        while True:
            try:
                email_field = self.driver.find_element_by_xpath('//*[@id="ap_email"]')
                break
            except sel_exceptions.NoSuchElementException:
                try:
                    password_field = self.driver.find_element_by_xpath(
                        '//*[@id="ap_password"]'
                    )
                    break
                except sel_exceptions.NoSuchElementException:
                    pass
            if time.time() > timeout:
                break

        if email_field:
            try:
                email_field.send_keys(amazon_config["username"] + Keys.RETURN)
            except sel_exceptions.ElementNotInteractableException:
                log.info("Email not needed.")
        else:
            log.info("Email not needed.")

        if "reverification" in self.driver.current_url:
            log.warning(
                "Beta code for allowing user to solve OTP.  Please report success/failures "
                "to #feature-testing on Discord"
            )
            # Maybe/Probably/Likely a One Time Password prompt?  Let's wait until the user takes action
            self.notification_handler.play_alarm_sound()
            log.error("One Time Password input required... pausing for user input")
            try:
                WebDriverWait(self.driver, timeout=300).until(
                    lambda d: "/ap/" not in d.driver.current_url
                )
            except sel_exceptions.TimeoutException:
                log.error("User did not solve One Time Password prompt in time.")

        if self.driver.find_elements_by_xpath('//*[@id="auth-error-message-box"]'):
            log.error("Login failed, delete your credentials file")
            time.sleep(240)
            exit(1)

        time.sleep(self.page_wait_delay())

        log.info("Remember me checkbox")
        try:
            self.driver.find_element_by_xpath('//*[@name="rememberMe"]').click()
        except sel_exceptions.NoSuchElementException:
            log.error("Remember me checkbox did not exist")

        log.info("Password")
        password_field = None
        timeout = self.get_timeout()
        current_page = self.driver.title
        while True:
            try:
                password_field = self.driver.find_element_by_xpath(
                    '//*[@id="ap_password"]'
                )
                break
            except sel_exceptions.NoSuchElementException:
                pass
            if time.time() > timeout:
                break

        captcha_entry = []
        if password_field:
            password_field.send_keys(amazon_config["password"])
            # check for captcha
            try:
                captcha_entry = self.driver.find_element_by_xpath(
                    '//form[contains(@action,"validateCaptcha")]'
                )
            except sel_exceptions.NoSuchElementException:
                password_field.send_keys(Keys.RETURN)
                self.wait_for_page_change(current_page)
        else:
            log.error("Password entry box did not exist")

        if captcha_entry:
            self.handle_captcha(False)
        if self.driver.title in amazon_config["TWOFA_TITLES"]:
            log.info("enter in your two-step verification code in browser")
            while self.driver.title in amazon_config["TWOFA_TITLES"]:
                # Wait for the user to enter 2FA
                time.sleep(2)
        log.info(f'Logged in as {amazon_config["username"]}')

    @debug
    def run_asins(self, delay):
        found_asin = False
        while not found_asin:
            for i in range(len(self.asin_list)):
                for asin in self.asin_list[i]:
                    # start_time = time.time()
                    if self.log_stock_check:
                        log.info(f"Checking ASIN: {asin}.")
                    if self.check_stock(asin, self.reserve_min[i], self.reserve_max[i]):
                        return asin
                    # log.info(f"check time took {time.time()-start_time} seconds")
                    time.sleep(delay)

    @debug
    def check_stock(self, asin, reserve_min, reserve_max, retry=0):
        if retry > DEFAULT_MAX_ATC_TRIES:
            log.info("max add to cart retries hit, returning to asin check")
            return False

        if self.alt_offers:
            if self.checkshipping:
                if self.used:
                    f = furl(self.ACTIVE_OFFER_URL + asin)
                else:
                    f = furl(self.ACTIVE_OFFER_URL + asin + "/ref=olp_f_new&f_new=true")
            else:
                if self.used:
                    f = furl(self.ACTIVE_OFFER_URL + asin + "/f_freeShipping=on")
                else:
                    f = furl(
                        self.ACTIVE_OFFER_URL
                        + asin
                        + "/ref=olp_f_new&f_new=true&f_freeShipping=on"
                    )
        else:
            # Force the flyout by default
            f = furl(self.ACTIVE_OFFER_URL + asin + "?aod=1")
        fail_counter = 0
        presence.searching_update()

        # handles initial page load only
        while True:
            try:
                self.get_page(f.url)
                log.debug(f"Initial page title {self.driver.title}")
                log.debug(f"        page url: {self.driver.current_url}")
                if self.driver.title in amazon_config["CAPTCHA_PAGE_TITLES"]:
                    self.handle_captcha()
                break
            except Exception:
                fail_counter += 1
                log.error(f"Failed to load the offer URL {fail_counter} times.")
                if fail_counter < DEFAULT_MAX_URL_FAIL:
                    log.error(
                        f"WebDriver will restart if it fails {DEFAULT_MAX_URL_FAIL} times. Retrying now..."
                    )
                    time.sleep(3)
                else:
                    log.info(
                        "Attempting to delete and recreate current chrome instance"
                    )
                    if not self.delete_driver():
                        log.error("Failed to delete chrome processes")
                        log.error("Please restart bot")
                        self.send_notification(
                            message="Bot Failed, please restart bot",
                            page_name="Bot Failed",
                            take_screenshot=False,
                        )
                        raise RuntimeError("Failed to restart bot")
                    elif not self.create_driver(self.profile_path):
                        log.error("Failed to recreate webdriver processes")
                        log.error("Please restart bot")
                        self.send_notification(
                            message="Bot Failed, please restart bot",
                            page_name="Bot Failed",
                            take_screenshot=False,
                        )
                        raise RuntimeError("Failed to restart bot")
                    else:  # deleted driver and recreated it succesfully
                        log.info(
                            "WebDriver recreated successfully. Returning back to stock check"
                        )
                        return False

        timeout = self.get_timeout()
        atc_buttons = None
        while True:
            # Sanity check to see if we have any offers
            try:
                # Wait for the page to load before determining what's in it by looking for the footer
                footer: List[WebElement] = WebDriverWait(
                    self.driver, timeout=DEFAULT_MAX_TIMEOUT
                ).until(
                    lambda d: d.find_elements_by_xpath(
                        "//div[@class='nav-footer-line'] | //div[@id='navFooter'] | //img[@alt='Dogs of Amazon']"
                    )
                )
                if footer and footer[0].tag_name == "img":
                    log.info(f"Saw dogs for {asin}.  Skipping...")
                    return False

                log.debug(f"After footer page title {self.driver.title}")
                log.debug(f"             page url: {self.driver.current_url}")

                offers = WebDriverWait(self.driver, timeout=DEFAULT_MAX_TIMEOUT).until(
                    lambda d: d.find_element_by_xpath(
                        "//div[@id='aod-container'] | "
                        "//div[@id='olpOfferList'] | "
                        "//div[@id='backInStock' or @id='outOfStock'] |"
                        "//span[@data-action='show-all-offers-display'] | "
                        "//input[@name='submit.add-to-cart' and not(//span[@data-action='show-all-offers-display'])]"
                    )
                )
                offer_count = []
                offer_id = offers.get_attribute("id")
                if offer_id == "outOfStock" or offer_id == "backInStock":
                    # No dice... Early out and move on
                    log.info("Item is currently unavailable.  Moving on...")
                    return False

                if offer_id == "olpOfferList":
                    # Offers Page ... count the 'a-row' classes to know how many offers we 'see'
                    offer_count = self.driver.find_elements_by_xpath(
                        "//div[@id='olpOfferList']//div[contains(@class, 'olpOffer')]"
                    )
                elif offer_id == "aod-container":
                    # Offer Flyout or Ajax call ... count the 'aod-offer' divs that we 'see'
                    offer_count = self.driver.find_elements_by_xpath(
                        "//div[@id='aod-pinned-offer' or @id='aod-offer']//input[@name='submit.addToCart']"
                    )
                elif offers.get_attribute("data-action") == "show-all-offers-display":
                    # PDP Page
                    # Find the offers link first, just to burn some cycles in case the flyout is loading
                    open_offers_link = None
                    try:
                        open_offers_link: WebElement = (
                            self.driver.find_element_by_xpath(
                                "//span[@data-action='show-all-offers-display']//a"
                            )
                        )
                    except sel_exceptions.NoSuchElementException:
                        pass

                    # Now check to see if we're already loading the flyout...
                    flyout = self.driver.find_elements_by_xpath(
                        "/html/body/div[@id='all-offers-display']"
                    )
                    if flyout:
                        # This means we have a flyout already loading, as it gets inserted as the first
                        # div after the body tag of the document.  Wait for the container to load and start
                        # the loop again to scan for known elements
                        log.debug(
                            "Found a loading flyout div.  Waiting for offers to load..."
                        )
                        WebDriverWait(self.driver, timeout=DEFAULT_MAX_TIMEOUT).until(
                            lambda d: d.find_element_by_xpath(
                                "//div[@id='aod-container']  "
                            )
                        )
                        continue

                    if open_offers_link:
                        log.debug("Attempting to click the open offers link...")
                        try:
                            open_offers_link.click()
                        except sel_exceptions.WebDriverException as e:
                            log.error("Problem clicking open offers link")
                            log.error(
                                "May have issue with rest of this ASIN check cycle"
                            )
                            log.debug(e)
                            filename = "open-offers-link-error"
                            self.save_screenshot(filename)
                            self.save_page_source(filename)
                        try:
                            # Now wait for the flyout to load
                            log.debug("Waiting for flyout...")
                            WebDriverWait(
                                self.driver, timeout=DEFAULT_MAX_TIMEOUT
                            ).until(
                                lambda d: d.find_element_by_xpath(
                                    "//div[@id='aod-container'] | //div[@id='olpOfferList']"
                                )
                            )
                            log.debug("Flyout should be open and populated.")
                        except sel_exceptions.TimeoutException as te:
                            log.error(
                                "Timed out waiting for the flyout to open and populate.  Is the "
                                "connection slow?  Do you see the flyout populate?"
                            )
                        continue
                    else:
                        log.error("Could not open offers link")
                elif (
                    offers.get_attribute("aria-labelledby")
                    == "submit.add-to-cart-announce"
                ):
                    # This assumes we're on a PDP with only an add to cart button... no offers
                    log.warning(
                        "NOT YET IMPLEMENTED: PDP represents only item worth considering.  No other sellers available."
                        " TODO: Parse pricing and Add To Cart from PDP if item qualifies."
                    )
                else:
                    log.warning(
                        "We found elements, but didn't recognize any of the combinations."
                    )
                    log.warning(f"Element found: {offers.tag_name}")
                    attrs = self.driver.execute_script(
                        "var items = {}; "
                        "for (index = 0; index < arguments[0].attributes.length; ++index) "
                        "{ items[arguments[0].attributes[index].name] = arguments[0].attributes[index].value }; "
                        "return items;",
                        offers,
                    )
                    log.warning("Dumping element attributes:")
                    for attr in attrs:
                        log.warning(f"{attr} = {attrs[attr]}")

                    return False
                if len(offer_count) == 0:
                    log.info("No offers found.  Moving on.")
                    return False
                log.info(
                    f"Found {len(offer_count)} offers for {asin}.  Evaluating offers..."
                )

            except sel_exceptions.TimeoutException as te:
                log.error("Timed out waiting for offers to render.  Skipping...")
                log.error(f"URL: {self.driver.current_url}")
                log.exception(te)
                return False
            except sel_exceptions.NoSuchElementException:
                log.error("Unable to find any offers listing.  Skipping...")
                return False
            except sel_exceptions.ElementClickInterceptedException as e:
                log.debug(
                    "Covering element detected... Assuming it's a slow flyout... scanning document again..."
                )
                continue

            atc_buttons = self.get_amazon_elements(key="ATC")
            # if not atc_buttons:
            #     # Sanity check to see if we have a valid page, but no offers:
            #     offer_count = WebDriverWait(self.driver, timeout=25).until(
            #         lambda d: d.find_element_by_xpath(
            #             "//div[@id='aod-offer-list']//input[@id='aod-total-offer-count']"
            #         )
            #     )
            #
            #     # offer_count = self.driver.find_element_by_xpath(
            #     #     "//div[@id='aod-offer-list']//input[@id='aod-total-offer-count']"
            #     # )
            #     if offer_count.get_attribute("value") == "0":
            #         log.info("Found zero offers explicitly.  Moving to next ASIN.")
            #         return False
            if atc_buttons:
                # Early out if we found buttons
                break

            test = None
            try:
                test = self.driver.find_element_by_xpath(
                    '//*[@id="olpOfferList"]/div/p'
                )
            except sel_exceptions.NoSuchElementException:
                pass

            if test and (test.text in amazon_config["NO_SELLERS"]):
                return False
            if time.time() > timeout:
                log.info(f"failed to load page for {asin}, going to next ASIN")
                return False

        timeout = self.get_timeout()
        flyout_mode = False
        while True:
            prices = self.driver.find_elements_by_xpath(
                '//*[@class="a-size-large a-color-price olpOfferPrice a-text-bold"]'
            )
            if not prices:
                # Try the flyout x-paths
                prices = self.driver.find_elements_by_xpath(
                    "//div[@id='aod-pinned-offer' or @id='aod-offer']//div[contains(@id, 'aod-price')]//span[@class='a-price']//span[@class='a-offscreen']"
                )
                if prices:
                    flyout_mode = True
                    break
            if prices:
                break
            if time.time() > timeout:
                log.info(f"failed to load prices for {asin}, going to next ASIN")
                return False
        shipping = []
        shipping_prices = []

        timeout = self.get_timeout()
        while True:
            if not flyout_mode:
                shipping = self.driver.find_elements_by_xpath(
                    '//*[@class="a-color-secondary a-size-base"]'
                )
            if shipping:
                # Convert to prices just in case
                for idx, shipping_node in enumerate(shipping):
                    log.debug(f"Processing shipping node {idx}")
                    if self.checkshipping:
                        if amazon_config["SHIPPING_ONLY_IF"] in shipping_node.text:
                            shipping_prices.append(parse_price("0"))
                        else:
                            shipping_prices.append(parse_price(shipping_node.text))
                    else:
                        shipping_prices.append(parse_price("0"))
            else:
                # Check for offers
                # offer_xpath = "//div[@id='aod-pinned-offer' or @id='aod-offer']"
                offer_xpath = (
                    "//div[@id='aod-offer' and .//input[@name='submit.addToCart']] | "
                    "//div[@id='aod-pinned-offer' and .//input[@name='submit.addToCart']]"
                )
                offers = self.driver.find_elements_by_xpath(offer_xpath)
                for idx, offer in enumerate(offers):
                    tree = html.fromstring(offer.get_attribute("innerHTML"))
                    shipping_prices.append(
                        get_shipping_costs(tree, amazon_config["FREE_SHIPPING"])
                    )
            if shipping_prices:
                break

            if time.time() > timeout:
                log.info(f"failed to load shipping for {asin}, going to next ASIN")
                return False

        in_stock = False
        for shipping_price in shipping_prices:
            log.debug(f"\tShipping Price: {shipping_price}")

        for idx, atc_button in enumerate(atc_buttons):
            # If the user has specified that they only want free items, we can skip any items
            # that have any shipping cost and early out
            if not self.checkshipping and shipping_prices[idx].amount_float > 0.00:
                continue

            # Condition check first, using the button to find the form that will divulge the item's condition
            if flyout_mode:
                condition: List[WebElement] = atc_button.find_elements_by_xpath(
                    "./ancestor::form[@method='post']"
                )
                if condition:
                    atc_form_action = condition[0].get_attribute("action")
                    seller_item_condition = get_item_condition(atc_form_action)
                    # Lower condition value imply newer
                    if seller_item_condition.value > self.condition.value:
                        # Item is below our standards, so skip it
                        log.debug(
                            f"Skipping item because its condition is below the requested level: "
                            f"{seller_item_condition} is below {self.condition}"
                        )
                        continue

            try:
                if flyout_mode:
                    price = parse_price(prices[idx].get_attribute("innerHTML"))
                else:
                    price = parse_price(prices[idx].text)
            except IndexError:
                log.debug("Price index error")
                return False
            # Include the price, even if it's zero for comparison
            ship_price = shipping_prices[idx]
            ship_float = ship_price.amount
            price_float = price.amount
            if price_float is None:
                return False
            if ship_float is None:
                ship_float = 0

            if (
                (ship_float + price_float) <= reserve_max
                or math.isclose((price_float + ship_float), reserve_max, abs_tol=0.01)
            ) and (
                (ship_float + price_float) >= reserve_min
                or math.isclose((price_float + ship_float), reserve_min, abs_tol=0.01)
            ):
                log.info("Item in stock and in reserve range!")
                log.info(f"{price_float} + {ship_float} shipping <= {reserve_max}")
                log.debug(
                    f"{reserve_min} <= {price_float} + {ship_float} shipping <= {reserve_max}"
                )
                log.info("Adding to cart")
                # Get the offering ID
                offering_id_elements = atc_button.find_elements_by_xpath(
                    "./preceding::input[@name='offeringID.1'][1]"
                )
                if offering_id_elements:
                    log.info("Attempting Add To Cart with offer ID...")
                    offering_id = offering_id_elements[0].get_attribute("value")
                    if self.attempt_atc(
                        offering_id, max_atc_retries=DEFAULT_MAX_ATC_TRIES
                    ):
                        return True
                    else:
                        self.send_notification(
                            "Failed Add to Cart after {max-atc-retries}",
                            "failed-atc",
                            self.take_screenshots,
                        )
                        self.save_page_source("failed-atc")
                        return False
                else:
                    log.error(
                        "Unable to find offering ID to add to cart.  Using legacy mode."
                    )
                    self.notification_handler.play_notify_sound()
                    if self.detailed:
                        self.send_notification(
                            message=f"Found Stock ASIN:{asin}",
                            page_name="Stock Alert",
                            take_screenshot=self.take_screenshots,
                        )

                    presence.buy_update()
                    current_title = self.driver.title
                    # log.info(f"current page title is {current_title}")
                    try:
                        atc_button.click()
                    except IndexError:
                        log.debug("Index Error")
                        return False
                    self.wait_for_page_change(current_title)
                    # log.info(f"page title is {self.driver.title}")
                    emtpy_cart_elements = self.driver.find_elements_by_xpath(
                        "//div[contains(@class, 'sc-your-amazon-cart-is-empty') or contains(@class, 'sc-empty-cart')]"
                    )

                    if (
                        not emtpy_cart_elements
                        and self.driver.title in amazon_config["SHOPPING_CART_TITLES"]
                    ):
                        return True
                    else:
                        log.info("did not add to cart, trying again")
                        if emtpy_cart_elements:
                            log.info(
                                "Cart appeared empty after clicking Add To Cart button"
                            )
                        log.debug(f"failed title was {self.driver.title}")
                        self.send_notification(
                            "Failed Add to Cart", "failed-atc", self.take_screenshots
                        )
                        self.save_page_source("failed-atc")
                        in_stock = self.check_stock(
                            asin=asin,
                            reserve_max=reserve_max,
                            reserve_min=reserve_min,
                            retry=retry + 1,
                        )
        return in_stock

    def attempt_atc(self, offering_id, max_atc_retries=DEFAULT_MAX_ATC_TRIES):
        # Open the add.html URL in Selenium
        f = f"{AMAZON_URLS['ATC_URL']}?OfferListingId.1={offering_id}&Quantity.1=1"
        atc_attempts = 0
        while atc_attempts < max_atc_retries:
            with self.wait_for_page_content_change(timeout=5):
                try:
                    self.driver.get(f)
                except sel_exceptions.TimeoutException:
                    log.error("Failed to get page")
                    atc_attempts += 1
                    continue
            xpath = "//input[@value='add' and @name='add']"
            continue_btn = None
            if wait_for_element_by_xpath(self.driver, xpath):
                try:
                    continue_btn = WebDriverWait(self.driver, timeout=5).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                except sel_exceptions.TimeoutException:
                    log.error("No continue button found")
            if continue_btn:
                if self.do_button_click(
                    button=continue_btn, fail_text="Could not click continue button"
                ):
                    if self.get_cart_count() != 0:
                        return True
                    else:
                        log.info("Nothing added to cart, trying again")

            atc_attempts = atc_attempts + 1
        log.error("reached maximum ATC attempts, returning to stock check")
        return False

    # search lists of asin lists, and remove the first list that matches provided asin
    @debug
    def remove_asin_list(self, asin):
        for i in range(len(self.asin_list)):
            if asin in self.asin_list[i]:
                self.asin_list.pop(i)
                self.reserve_max.pop(i)
                self.reserve_min.pop(i)
                break

    # checkout page navigator
    @debug
    def navigate_pages(self, test):
        title = self.driver.title
        log.debug(f"Navigating page title: '{title}'")
        # see if this resolves blank page title issue?
        if title == "":
            timeout_seconds = DEFAULT_MAX_TIMEOUT
            log.debug(
                f"Title was blank, checking to find a real title for {timeout_seconds} seconds"
            )
            timeout = self.get_timeout(timeout=timeout_seconds)
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
            self.handle_checkout(test)
        elif title in amazon_config["ORDER_COMPLETE_TITLES"]:
            self.handle_order_complete()
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
            except sel_exceptions.NoSuchElementException:
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
                return

            element = None
            # Prime offer page?
            try:
                element = self.get_amazon_element(key="PRIME_NO_THANKS")
            except sel_exceptions.NoSuchElementException:
                pass
            if element:
                if self.do_button_click(
                    button=element,
                    clicking_text="FairGame thinks it is seeing a Prime Offer, attempting to click No Thanks",
                    fail_text="FairGame could not click No Thanks button",
                    log_debug=True,
                ):
                    return
            # see if a use this address (or similar) button is on page (based on known xpaths). Only check if
            # user has set the shipping_bypass flag
            if self.shipping_bypass:
                if self.handle_shipping_page():
                    return

            if self.get_cart_count() == 0:
                log.info("It appears you have nothing in your cart.")
                log.info("Returning to stock check.")
                self.try_to_checkout = False
                return

            ##############################
            # other element checks above #
            ##############################

            # if above checks don't work, just continue on to trying to resolve

            # try to handle an unknown title
            log.error(
                f"'{title}' is not a known page title. Please create issue indicating the title with a screenshot of page"
            )
            # give user 30 seconds to respond
            self.handle_unknown_title(title=title)
            # check if page title changed, if not, then continue doing other checks:
            if self.driver.title != title:
                log.info(
                    "FairGame thinks user intervened in time, will now continue running"
                )
                return
            else:
                log.warning(
                    "FairGame does not think the user intervened in time, will attempt other methods to continue"
                )
            log.info("Going to try and redirect to cart page")
            try:
                with self.wait_for_page_content_change(timeout=10):
                    self.driver.get(AMAZON_URLS["CART_URL"])
            except sel_exceptions.WebDriverException:
                log.error(
                    "failed to load cart URL, refreshing and returning to handler"
                )
                with self.wait_for_page_content_change(timeout=10):
                    self.driver.refresh()
                return
            time.sleep(1)  # wait a second for page to load
            # verify cart quantity is not zero
            # note, not using greater than 0, in case there is an error,
            # still want to try and proceed, if possible
            if self.get_cart_count() == 0:
                log.info("It appears you have nothing in your cart.")
                log.info("Returning to stock check.")
                self.try_to_checkout = False
                return

            log.info("trying to click proceed to checkout")
            timeout = self.get_timeout()
            while True:
                try:
                    button = self.get_amazon_element(key="PTC")
                    break
                except sel_exceptions.NoSuchElementException:
                    button = None
                if time.time() > timeout:
                    log.error("Could not find and click button")
                    break
            if button:
                if self.do_button_click(
                    button=button,
                    clicking_text="Found ptc button, attempting to click.",
                    clicked_text="Clicked ptc button",
                    fail_text="Could not click button",
                ):
                    return
                else:
                    with self.wait_for_page_content_change():
                        self.driver.refresh()
                    return

            # if we made it this far, all attempts to handle page failed, get current page info and return to handler
            log.error(
                "FairGame could not navigate current page, refreshing and returning to handler"
            )
            self.save_page_source(page="unknown")
            self.save_screenshot(page="unknown")
            with self.wait_for_page_content_change():
                self.driver.refresh()
            return

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
        except sel_exceptions.NoSuchElementException:
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

    def get_amazon_element(self, key):
        return self.driver.find_element_by_xpath(
            join_xpaths(amazon_config["XPATHS"][key])
        )

    def get_amazon_elements(self, key):
        return self.driver.find_elements_by_xpath(
            join_xpaths(amazon_config["XPATHS"][key])
        )

    # returns negative number if cart element does not exist, returns number if cart exists
    def get_cart_count(self):
        # check if cart number is on the page, if cart items = 0
        try:
            element = self.get_amazon_element(key="CART")
        except sel_exceptions.NoSuchElementException:
            return -1
        if element:
            try:
                return int(element.text)
            except Exception as e:
                log.debug("Error converting cart number to integer")
                log.debug(e)
                return -1

    @debug
    def handle_prime_signup(self):
        log.info("Prime offer page popped up, attempting to click No Thanks")
        time.sleep(
            2
        )  # just doing manual wait, sign up for prime if you don't want to deal with this
        button = None
        try:
            button = self.get_amazon_element(key="PRIME_NO_THANKS")
        except sel_exceptions.NoSuchElementException:
            log.error("could not find button")
            log.info("sign up for Prime and this won't happen anymore")
            self.save_page_source("prime-signup-error")
            self.send_notification(
                "Prime Sign-up Error occurred",
                "prime-signup-error",
                self.take_screenshots,
            )
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
        timeout = self.get_timeout(timeout=60)
        while self.driver.title in amazon_config["PRIME_TITLES"]:
            if time.time() > timeout:
                log.info("user did not intervene in time, will try and refresh page")
                with self.wait_for_page_content_change():
                    self.driver.refresh()
                break
            time.sleep(0.5)

    def do_button_click(
        self,
        button,
        clicking_text="Clicking button",
        clicked_text="Button clicked",
        fail_text="Could not click button",
        log_debug=False,
    ):
        try:
            with self.wait_for_page_content_change():
                log.info(clicking_text)
                button.click()
                log.info(clicked_text)
            return True
        except sel_exceptions.WebDriverException as e:
            if log_debug:
                log.debug(fail_text)
                log.debug(e)
            else:
                log.error(fail_text)
                log.error(e)
            return False

    @debug
    def handle_home_page(self):
        log.info("On home page, trying to get back to checkout")
        button = None
        tries = 0
        maxTries = 10
        while not button and tries < maxTries:
            try:
                button = self.get_amazon_element("CART_BUTTON")
            except sel_exceptions.NoSuchElementException:
                pass
            tries += 1
            time.sleep(0.5)
        current_page = self.driver.title
        if button:
            if self.do_button_click(button=button):
                return
            else:
                log.info("Failed to click on cart button")
        else:
            log.info("Could not find cart button after " + str(maxTries) + " tries")

        # no button found or could not interact with the button
        self.send_notification(
            "Could not click cart button, user intervention required",
            "home-page-error",
            self.take_screenshots,
        )
        timeout = self.get_timeout(timeout=300)
        while self.driver.title == current_page:
            time.sleep(0.25)
            if time.time() > timeout:
                log.info("user failed to intervene in time, returning to stock check")
                self.try_to_checkout = False
                break

    @debug
    def handle_cart(self):
        self.start_time_atc = time.time()
        log.info("Looking for Proceed To Checkout button...")
        try:
            self.save_screenshot("ptc-page")
        except:
            pass
        timeout = self.get_timeout()
        button = None
        while True:
            try:
                button = self.get_amazon_element(key="PTC")
                break
            except sel_exceptions.NoSuchElementException:
                if self.shipping_bypass:
                    try:
                        button = self.get_amazon_element(key="ADDRESS_SELECT")
                        break
                    except sel_exceptions.NoSuchElementException:
                        pass
            if self.get_cart_count() == 0:
                log.info("You have no items in cart. Going back to stock check.")
                self.try_to_checkout = False
                break

            if time.time() > timeout:
                log.info("couldn't find buttons to proceed to checkout")
                self.save_page_source("ptc-error")
                self.send_notification(
                    "Proceed to Checkout Error Occurred",
                    "ptc-error",
                    self.take_screenshots,
                )
                # if self.get_cart_count() == 0:
                #     log.info("It appears this is because you have no items in cart.")
                #     log.info(
                #         "It is likely that the product went out of stock before you could checkout"
                #     )
                #     log.info("Going back to stock check.")
                #     self.try_to_checkout = False
                # else:
                log.info("Refreshing page to try again")
                with self.wait_for_page_content_change():
                    self.driver.refresh()
                self.checkout_retry += 1
                return

        if button:
            log.info("Found Checkout Button")
            if self.detailed:
                self.send_notification(
                    message="Attempting to Proceed to Checkout",
                    page_name="ptc",
                    take_screenshot=self.take_screenshots,
                )
            if self.do_button_click(button=button):
                return
            else:
                log.error("Problem clicking Proceed to Checkout button.")
                log.info("Refreshing page to try again")
                with self.wait_for_page_content_change():
                    self.driver.refresh()
                self.checkout_retry += 1

    @debug
    def handle_checkout(self, test):
        previous_title = self.driver.title
        button = None
        timeout = self.get_timeout()
        while True:
            try:
                button = self.driver.find_element_by_xpath(self.button_xpaths[0])
            except sel_exceptions.NoSuchElementException:
                if self.shipping_bypass:
                    try:
                        button = self.get_amazon_element(key="ADDRESS_SELECT")
                    except sel_exceptions.NoSuchElementException:
                        pass
                self.button_xpaths.append(self.button_xpaths.pop(0))
            if button:
                if button.is_enabled() and button.is_displayed():
                    break
            if time.time() > timeout:
                log.error("couldn't find button to place order")
                self.save_page_source("pyo-error")
                self.send_notification(
                    "Error in placing order.  Please check browser window.",
                    "pyo-error",
                    self.take_screenshots,
                )
                log.info("Refreshing page to try again")
                self.driver.refresh()
                time.sleep(DEFAULT_PAGE_WAIT_DELAY)
                self.order_retry += 1
                return
        if test:
            log.info(f"Found button {button.text}, but this is a test")
            log.info("will not try to complete order")
            log.info(f"test time took {time.time() - self.start_time_atc} to check out")
            self.try_to_checkout = False
            self.great_success = True
            if self.single_shot:
                self.asin_list = []
        else:
            log.info(f"Clicking Button {button.text} to place order")
            self.do_button_click(button=button)

    @debug
    def handle_order_complete(self):
        log.info("Order Placed.")
        self.send_notification("Order placed.", "order-placed", self.take_screenshots)
        self.notification_handler.play_purchase_sound()
        self.great_success = True
        if self.single_shot:
            self.asin_list = []
        self.try_to_checkout = False
        log.info(f"checkout completed in {time.time() - self.start_time_atc} seconds")

    @debug
    def handle_doggos(self):
        self.notification_handler.send_notification(
            "You got dogs, bot may not work correctly. Ending Checkout"
        )
        self.try_to_checkout = False

    @debug
    def handle_out_of_stock(self):
        self.notification_handler.send_notification(
            "Carted it, but went out of stock, better luck next time."
        )
        self.try_to_checkout = False

    @debug
    def handle_captcha(self, check_presence=True):
        # wait for captcha to load
        log.debug("Waiting for captcha to load.")
        time.sleep(DEFAULT_MAX_WEIRD_PAGE_DELAY)
        current_page = self.driver.title
        try:
            if not check_presence or self.driver.find_element_by_xpath(
                '//form[contains(@action,"validateCaptcha")]'
            ):
                try:
                    log.info("Stuck on a captcha... Lets try to solve it.")
                    captcha = AmazonCaptcha.fromdriver(self.driver)
                    solution = captcha.solve()
                    log.info(f"The solution is: {solution}")
                    if solution == "Not solved":
                        log.info(
                            f"Failed to solve {captcha.image_link}, lets reload and get a new captcha."
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
                                    self.driver.refresh()
                                    return False
                                else:
                                    return True
                    # Solved (!?)
                    else:
                        # take screenshot if user asked for detailed
                        if self.detailed:
                            self.send_notification(
                                "Solving catpcha", "captcha", self.take_screenshots
                            )
                        try:
                            captcha_field = self.driver.find_element_by_xpath(
                                '//*[@id="captchacharacters"]'
                            )
                        except sel_exceptions.NoSuchElementException:
                            log.debug("Could not locate captcha")
                            captcha_field = None
                        if captcha_field:
                            with self.wait_for_page_content_change():
                                captcha_field.send_keys(solution + Keys.RETURN)
                            return True
                        else:
                            return False
                except Exception as e:
                    log.debug(e)
                    log.debug("Error trying to solve captcha. Refresh and retry.")
                    with self.wait_for_page_content_change():
                        self.driver.refresh()
                    return False
        except sel_exceptions.NoSuchElementException:
            log.debug("captcha page does not contain captcha element")
            with self.wait_for_page_content_change():
                self.driver.refresh()
            return False

    @debug
    def handle_business_po(self):
        log.info("On Business PO Page, Trying to move on to checkout")
        button = None
        timeout = self.get_timeout()
        while True:
            try:
                button = self.driver.find_element_by_xpath(
                    '//*[@id="a-autoid-0"]/span/input'
                )
                break
            except sel_exceptions.NoSuchElementException:
                pass
            if time.time() > timeout:
                break
        if button:
            current_page = self.driver.title
            button.click()
            self.wait_for_page_change(page_title=current_page)
        else:
            log.info(
                "Could not find the continue button, user intervention required, complete checkout manually"
            )
            self.notification_handler.send_notification(
                "Could not click continue button, user intervention required"
            )
            time.sleep(300)

    def save_screenshot(self, page):
        file_name = get_timestamp_filename("screenshots/screenshot-" + page, ".png")
        try:
            self.driver.save_screenshot(file_name)
            return file_name
        except sel_exceptions.TimeoutException:
            log.info("Timed out taking screenshot, trying to continue anyway")
            pass
        except Exception as e:
            log.error(f"Trying to recover from error: {e}")
            pass
        return None

    def save_page_source(self, page):
        """Saves DOM at the current state when called.  This includes state changes from DOM manipulation via JS"""
        file_name = get_timestamp_filename("html_saves/" + page + "_source", "html")

        page_source = self.driver.page_source
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(page_source)

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
        except sel_exceptions.TimeoutException:
            log.info("Timed out reloading page, trying to continue anyway")
            pass
        except Exception as e:
            log.error(f"Trying to recover from error: {e}")
            pass
        return None

    def wait_for_page_change(self, page_title, timeout=3):
        time_to_end = self.get_timeout(timeout=timeout)
        while time.time() < time_to_end and (
            self.driver.title == page_title or not self.driver.title
        ):
            pass
        if self.driver.title != page_title:
            return True
        else:
            return False

    def page_wait_delay(self):
        return DEFAULT_PAGE_WAIT_DELAY

    def send_notification(self, message, page_name, take_screenshot=True):
        if take_screenshot:
            file_name = self.save_screenshot(page_name)
            self.notification_handler.send_notification(message, file_name)
        else:
            self.notification_handler.send_notification(message)

    def get_timeout(self, timeout=DEFAULT_MAX_TIMEOUT):
        return time.time() + timeout

    def get_webdriver_pids(self):
        pid = self.driver.service.process.pid
        driver_process = psutil.Process(pid)
        children = driver_process.children(recursive=True)
        for child in children:
            self.webdriver_child_pids.append(child.pid)

    def get_page(self, url):
        check_cart_element = None
        current_page = []
        try:
            check_cart_element = self.driver.find_element_by_xpath(
                '//*[@id="nav-cart"]'
            )
        except sel_exceptions.NoSuchElementException:
            current_page = self.driver.title
        try:
            self.driver.get(url=url)
        except sel_exceptions.WebDriverException or sel_exceptions.TimeoutException:
            log.error(f"failed to load page at url: {url}")
            return False
        if check_cart_element:
            timeout = self.get_timeout()
            while True:
                try:
                    check_cart_element.is_displayed()
                except sel_exceptions.StaleElementReferenceException:
                    break
                if time.time() > timeout:
                    return False
            return True
        elif self.wait_for_page_change(current_page):
            return True
        else:
            log.error("page did not change")
            return False

    def __del__(self):
        self.delete_driver()

    def show_config(self):
        log.info(f"{'=' * 50}")
        log.info(
            f"Starting Amazon ASIN Hunt on {AMAZON_URLS['BASE_URL']} for {len(self.asin_list)} Products with:"
        )
        log.info(f"--Offer URL of: {self.ACTIVE_OFFER_URL}")
        log.info(f"--Delay of {self.refresh_delay} seconds")
        if self.headless:
            log.info(f"--Chrome is running in Headless mode")
        if self.used:
            log.info(f"--Used items are considered for purchase")
        if self.checkshipping:
            log.info(f"--Shipping costs are included in price calculations")
        else:
            log.info(f"--Free Shipping items only")
        if self.single_shot:
            log.info("--Single Shot purchase enabled")
        if not self.take_screenshots:
            log.info(
                f"--Screenshotting is Disabled, DO NOT ASK FOR HELP IN TECH SUPPORT IF YOU HAVE NO SCREENSHOTS!"
            )
        if self.detailed:
            log.info(f"--Detailed screenshots/notifications is enabled")
        if self.log_stock_check:
            log.info(f"--Additional stock check logging enabled")
        if self.slow_mode:
            log.warning(f"--Slow-mode enabled. Pages will fully load before execution.")
        if self.shipping_bypass:
            log.warning(f"{'=' * 50}")
            log.warning(f"--FairGame will attempt to choose shipping address.")
            log.warning(f"USE THIS OPTION AT YOUR OWN RISK!!!")
            log.warning(
                f"DO NOT COMPLAIN OR ASK FOR HELP IF BOT SHIPS TO INCORRECT ADDRESS!!!"
            )
            log.warning(f"Choosing payment options is not available,")
            log.warning(
                f"bot may still fail during checkout if defaults are not set on Amazon's site."
            )
            log.warning(f"{'=' * 50}")
        for idx, asins in enumerate(self.asin_list):
            log.info(
                f"--Looking for {len(asins)} ASINs between {self.reserve_min[idx]:.2f} and {self.reserve_max[idx]:.2f}"
            )
        if not presence.enabled:
            log.info(f"--Discord Presence feature is disabled.")
        if self.no_image:
            log.info(f"--No images will be requested")
        if not self.notification_handler.sound_enabled:
            log.info(f"--Notification sounds are disabled.")
        if self.ACTIVE_OFFER_URL == AMAZON_URLS["ALT_OFFER_URL"]:
            log.info(f"--Using alternate offers URL")
        if self.testing:
            log.warning(f"--Testing Mode.  NO Purchases will be made.")
        log.info(f"{'=' * 50}")

    def create_driver(self, path_to_profile):
        if self.setup_driver:

            if self.headless:
                enable_headless()

            prefs = {
                "profile.password_manager_enabled": False,
                "credentials_enable_service": False,
            }
            if self.no_image:
                prefs["profile.managed_default_content_settings.images"] = 2
            else:
                prefs["profile.managed_default_content_settings.images"] = 0
            options.add_experimental_option("prefs", prefs)
            options.add_argument(f"user-data-dir={path_to_profile}")
            if not self.slow_mode:
                options.set_capability("pageLoadStrategy", "none")

            self.setup_driver = False

        # Delete crashed, so restore pop-up doesn't happen
        path_to_prefs = os.path.join(
            path_to_profile,
            "Default",
            "Preferences",
        )
        try:
            with fileinput.FileInput(path_to_prefs, inplace=True) as file:
                for line in file:
                    print(line.replace("Crashed", "none"), end="")
        except FileNotFoundError:
            pass
        try:
            self.driver = webdriver.Chrome(executable_path=binary_path, options=options)
            self.wait = WebDriverWait(self.driver, 10)
            self.get_webdriver_pids()
        except Exception as e:
            log.error(e)
            log.error(
                "If you have a JSON warning above, try cleaning your profile (e.g. --clean-profile)"
            )
            log.error(
                "If that's not it, you probably have a previous Chrome window open. You should close it."
            )

            return False

        return True

    def delete_driver(self):
        try:
            if platform.system() == "Windows" and self.driver:
                log.info("Cleaning up after web driver...")
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
            log.info(e)
            log.info(
                "Failed to clean up after web driver.  Please manually close browser."
            )
            return False
        return True


def get_timestamp_filename(name, extension):
    """Utility method to create a filename with a timestamp appended to the root and before
    the provided file extension"""
    now = datetime.now()
    date = now.strftime("%m-%d-%Y_%H_%M_%S")
    if extension.startswith("."):
        return name + "_" + date + extension
    else:
        return name + "_" + date + "." + extension


def get_shipping_costs(tree, free_shipping_string):
    # This version expects to find the shipping pricing within a div with the explicit ID 'delivery-message'
    shipping_xpath = ".//div[@id='delivery-message']"
    shipping_nodes = tree.xpath(shipping_xpath)
    count = len(shipping_nodes)
    if count > 0:
        # Get the text out of the div and evaluate it
        shipping_node = shipping_nodes[0]
        if shipping_node.text:
            shipping_span_text = shipping_node.text.strip()
            if any(
                shipping_span_text.upper() in free_message
                for free_message in amazon_config["FREE_SHIPPING"]
            ):
                # We found some version of "free" inside the span.. but this relies on a match
                log.info(
                    f"Assuming free shipping based on this message: '{shipping_span_text}'"
                )
                return FREE_SHIPPING_PRICE
            else:
                # will it parse?
                shipping_cost: Price = parse_price(shipping_span_text)
                if shipping_cost.currency is not None:
                    log.debug(
                        f"Found parseable price with currency symbol: {shipping_cost.currency}"
                    )
                    return shipping_cost
    # Try the alternative method...
    return get_alt_shipping_costs(tree, free_shipping_string)


def get_alt_shipping_costs(tree, free_shipping_string) -> Price:
    # Assume Free Shipping and change otherwise

    # Shipping collection xpath:
    # .//div[starts-with(@id, 'aod-bottlingDepositFee-')]/following-sibling::span
    shipping_xpath = (
        ".//div[starts-with(@id, 'aod-bottlingDepositFee-')]/following-sibling::*[1]"
    )
    shipping_nodes = tree.xpath(shipping_xpath)
    count = len(shipping_nodes)
    log.debug(f"Found {count} shipping nodes.")
    if count == 0:
        log.warning("No shipping nodes (standard or alt) found.  Assuming zero.")
        return FREE_SHIPPING_PRICE
    elif count > 1:
        log.warning("Found multiple shipping nodes.  Using the first.")

    shipping_node = shipping_nodes[0]
    # Shipping information is found within either a DIV or a SPAN following the bottleDepositFee DIV
    # What follows is logic to parse out the various pricing formats within the HTML.  Not ideal, but
    # it's what we have to work with.
    if shipping_node.text:
        shipping_span_text = shipping_node.text.strip()
    else:
        shipping_span_text = ""
    if shipping_node.tag == "div":
        # Do we have any spans outlining the price?  Typically seen like this:
        # <div class="a-row aod-ship-charge">
        #     <span class="a-size-base a-color-base">+</span>
        #     <span class="a-size-base a-color-base">S$21.44</span>
        #     <span class="a-size-base a-color-base">shipping</span>
        # </div>
        shipping_spans = shipping_node.xpath(".//span")
        if shipping_spans:
            log.debug(
                f"Found {len(shipping_spans)} shipping SPANs within the shipping DIV"
            )
            # Look for a price
            for shipping_span in shipping_spans:
                if shipping_span.text and shipping_span.text != "+":
                    shipping_cost: Price = parse_price(shipping_span.text)
                    if shipping_cost.currency is not None:
                        log.debug(
                            f"Found parseable price with currency symbol: {shipping_cost.currency}"
                        )
                        return shipping_cost

        if shipping_span_text == "":
            # Assume zero shipping for an empty div
            log.debug(
                "Empty div found after bottleDepositFee.  Assuming zero shipping."
            )
        else:
            # Assume zero shipping for unknown values in
            log.warning(
                f"Non-Empty div found after bottleDepositFee.  Assuming zero. Stripped Value: '{shipping_span_text}'"
            )
    elif shipping_node.tag == "span":
        # Shipping values in the span are contained in:
        # - another SPAN
        # - hanging out alone in a B tag
        # - Hanging out alone in an I tag
        # - Nested in two I tags <i><i></i></i>
        # - "Prime FREE Delivery" in this node

        shipping_spans = shipping_node.findall("span")
        shipping_bs = shipping_node.findall("b")
        # shipping_is = shipping_node.findall("i")
        shipping_is = shipping_node.xpath("//i[@aria-label]")
        if len(shipping_spans) > 0:
            # If the span starts with a "& " it's free shipping (right?)
            if shipping_spans[0].text.strip() == "&":
                # & Free Shipping message
                log.debug("Found '& Free', assuming zero.")
            elif shipping_spans[0].text.startswith("+"):
                return parse_price(shipping_spans[0].text.strip())
        elif len(shipping_bs) > 0:
            for message_node in shipping_bs:

                if message_node.text.upper() in free_shipping_string:
                    log.debug("Found free shipping string.")
                else:
                    log.error(
                        f"Couldn't parse price from <B>. Assuming 0. Do we need to add: '{message_node.text.upper()}'"
                    )
        elif len(shipping_is) > 0:
            # If it has prime icon class, assume free Prime shipping
            if "FREE" in shipping_is[0].attrib["aria-label"].upper():
                log.debug("Found Free shipping with Prime")
        elif any(
            shipping_span_text.upper() in free_message
            for free_message in amazon_config["FREE_SHIPPING"]
        ):
            # We found some version of "free" inside the span.. but this relies on a match
            log.warning(
                f"Assuming free shipping based on this message: '{shipping_span_text}'"
            )
        else:
            log.error(
                f"Unable to locate price.  Assuming 0.  Found this: '{shipping_span_text}'  Consider reporting to #tech-support Discord."
            )
    return FREE_SHIPPING_PRICE


class AmazonItemCondition(Enum):
    # See https://sellercentral.amazon.com/gp/help/external/200386310?language=en_US&ref=efph_200386310_cont_G1831
    New = 10
    Renewed = 20
    Refurbished = 20
    Rental = 30
    Open_box = 40
    UsedLikeNew = 40
    UsedVeryGood = 50
    UsedGood = 60
    UsedAcceptable = 70
    CollectibleLikeNew = 40
    CollectibleVeryGood = 50
    CollectibleGood = 60
    CollectibleAcceptable = 70
    Unknown = 1000

    @classmethod
    def from_str(cls, label):
        # Straight lookup
        try:
            condition = AmazonItemCondition[label]
            return condition
        except KeyError:
            # Key doesn't exist as a Member, so try cleaning up the string
            cleaned_label = "".join(label.split())
            cleaned_label = cleaned_label.replace("-", "")
            try:
                condition = AmazonItemCondition[cleaned_label]
                return condition
            except KeyError:
                raise NotImplementedError


def get_item_condition(form_action) -> AmazonItemCondition:
    """ Attempts to determine the Item Condition from the Add To Cart form action """
    if "_new_" in form_action:
        # log.debug(f"Item condition is new")
        return AmazonItemCondition.New
    elif "_used_" in form_action:
        # log.debug(f"Item condition is used")
        return AmazonItemCondition.UsedGood
    elif "_col_" in form_action:
        # og.debug(f"Item condition is collectible")
        return AmazonItemCondition.CollectibleGood
    else:
        # log.debug(f"Item condition is unknown: {form_action}")
        return AmazonItemCondition.Unknown


def wait_for_element_by_xpath(d, xpath, timeout=10):
    try:
        WebDriverWait(d, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
    except sel_exceptions.TimeoutException:
        log.error(f"failed to find {xpath}")
        return False

    return True


def join_xpaths(xpath_list, separator=" | "):
    return separator.join(xpath_list)
