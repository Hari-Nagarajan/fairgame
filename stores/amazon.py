import fileinput
import json
import math
import os
import platform
import time
from datetime import datetime

import psutil
from amazoncaptcha import AmazonCaptcha
from chromedriver_py import binary_path  # this will get you the path variable
from furl import furl
from lxml import html
from price_parser import parse_price
from pypresence import exceptions as pyexceptions
from selenium import webdriver
from selenium.common import exceptions as sel_exceptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from utils import discord_presence as presence
from utils.debugger import debug
from utils.logger import log
from utils.selenium_utils import options, enable_headless

# Optional OFFER_URL is:     "OFFER_URL": "https://{domain}/dp/",
AMAZON_URLS = {
    "BASE_URL": "https://{domain}/",
    "OFFER_URL": "https://{domain}/gp/offer-listing/",
    "CART_URL": "https://{domain}/gp/cart/view.html",
}
CHECKOUT_URL = "https://{domain}/gp/cart/desktop/go-to-checkout.html/ref=ox_sc_proceed?partialCheckoutCart=1&isToBeGiftWrappedBefore=0&proceedToRetailCheckout=Proceed+to+checkout&proceedToCheckout=1&cartInitiateId={cart_id}"

AUTOBUY_CONFIG_PATH = "config/amazon_config.json"

BUTTON_XPATHS = [
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

amazon_config = None


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
    ):
        self.notification_handler = notification_handler
        self.asin_list = []
        self.reserve_min = []
        self.reserve_max = []
        self.checkshipping = checkshipping
        self.button_xpaths = BUTTON_XPATHS
        self.detailed = detailed
        self.used = used
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

        presence.enabled = not disable_presence

        global amazon_config
        from cli.cli import global_config

        amazon_config = global_config.get_amazon_config(encryption_pass)

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

        if not self.create_driver():
            exit(1)

        for key in AMAZON_URLS.keys():
            AMAZON_URLS[key] = AMAZON_URLS[key].format(domain=self.amazon_website)

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
            log.info("Exiting now...")
            time.sleep(5)
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
            log.info("Exiting now...")
            time.sleep(5)
            return

        keep_going = True

        log.info("Checking stock for items.")

        while keep_going:
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
                keep_going = False
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
                    '//*[@id="auth-captcha-guess"]'
                )
            except sel_exceptions.NoSuchElementException:
                password_field.send_keys(Keys.RETURN)
                self.wait_for_page_change(current_page)
        else:
            log.error("Password entry box did not exist")

        if captcha_entry:
            try:
                log.info("Stuck on a captcha... Lets try to solve it.")
                captcha = AmazonCaptcha.fromdriver(self.driver)
                solution = captcha.solve()
                log.info(f"The solution is: {solution}")
                if solution == "Not solved":
                    log.info(
                        f"Failed to solve {captcha.image_link}, lets reload and get a new captcha."
                    )
                    self.driver.refresh()
                else:
                    self.send_notification(
                        "Solving catpcha", "captcha", self.take_screenshots
                    )
                    captcha_entry.send_keys(solution + Keys.RETURN)
                    self.wait_for_page_change(current_page)

            except Exception as e:
                log.debug(e)
                log.info("Error trying to solve captcha. Refresh and retry.")
                self.driver.refresh()
                time.sleep(5)

        if self.driver.title in amazon_config["TWOFA_TITLES"]:
            log.info("enter in your two-step verification code in browser")
            while self.driver.title in amazon_config["WOFA_TITLES"]:
                time.sleep(0.2)
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
        if self.checkshipping:
            if self.used:
                f = furl(AMAZON_URLS["OFFER_URL"] + asin)
            else:
                f = furl(AMAZON_URLS["OFFER_URL"] + asin + "/ref=olp_f_new&f_new=true")
        else:
            if self.used:
                f = furl(AMAZON_URLS["OFFER_URL"] + asin + "/f_freeShipping=on")
            else:
                f = furl(
                    AMAZON_URLS["OFFER_URL"]
                    + asin
                    + "/ref=olp_f_new&f_new=true&f_freeShipping=on"
                )
        fail_counter = 0
        presence.searching_update()

        while True:
            try:
                self.get_page(f.url)
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
                    elif not self.create_driver():
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
        while True:
            # Sanity check to see if we have any offers
            try:
                offers_exist = WebDriverWait(self.driver, timeout=5).until(
                    lambda d: d.find_element_by_xpath(
                        "//div[@id='aod-offer-list'] | "
                        "//div[@id='olpOfferList'] | "
                        "//span[@data-action='show-all-offers-display'] |"
                        "//input[@name='submit.add-to-cart' and not(//span[@data-action='show-all-offers-display'])]"
                    )
                )
                offer_count = []
                if offers_exist.get_attribute("id") == "olpOfferList":
                    # Offers Page ... count the 'a-row' classes to know how many offers we 'see'
                    offer_count = self.driver.find_elements_by_xpath(
                        "//div[contains(@class, 'a-row')]"
                    )
                elif offers_exist.get_attribute("id") == "aod-offer-list":
                    # Offer Flyout or Ajax call ... count the 'aod-offer' divs that we 'see'
                    offer_count = self.driver.find_elements_by_xpath(
                        "//div[@id='aod-offer']"
                    )
                elif (
                    offers_exist.get_attribute("data-action")
                    == "show-all-offers-display"
                ):
                    # No offers to parse... look for a link to the offers
                    log.info("Attempting to click the open offers link...")
                    self.driver.find_element_by_xpath(
                        "//span[@data-action='show-all-offers-display']//a"
                    ).click()
                    # Now wait for the flyout to load
                    log.info("Waiting for flyout... probably")
                    WebDriverWait(self.driver, timeout=5).until(
                        lambda d: d.find_element_by_xpath("//div[@id='aod-container']")
                    )
                    log.info("It flew out?!")
                    continue
                else:
                    # This assumes we're on a PDP with only an add to cart button... no offers
                    log.warning(
                        "NOT YET IMPLEMENTED: PDP represents only item worth considering.  Parse pricing and Add To Cart from PDP if item qualifies."
                    )
                    return False
                log.info(
                    f"Found {len(offer_count)} offers in the HTML.  Attempting to parse..."
                )

            except sel_exceptions.TimeoutException:
                log.error("Timed out waiting for offers to render.  Skipping...")
                return False
            except sel_exceptions.NoSuchElementException:
                log.error("Unable to find any offers listing.  Skipping...")
                return False

            atc_buttons = self.driver.find_elements_by_xpath(
                '//*[@name="submit.addToCart"]'
            )
            if not atc_buttons:
                # Sanity check to see if we have a valid page, but no offers:
                offer_count = WebDriverWait(self.driver, timeout=5).until(
                    lambda d: d.find_element_by_xpath(
                        "//div[@id='aod-offer-list']//input[@id='aod-total-offer-count']"
                    )
                )

                # offer_count = self.driver.find_element_by_xpath(
                #     "//div[@id='aod-offer-list']//input[@id='aod-total-offer-count']"
                # )
                if offer_count.get_attribute("value") == "0":
                    log.info("Found zero offers explicitly.  Moving to next ASIN.")
                    return False
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
                    "//div[@id='aod-offer']//div[@id='aod-offer-price']//span[@class='a-price']//span[@class='a-offscreen']"
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
        if self.checkshipping:
            timeout = self.get_timeout()
            while True:
                if not flyout_mode:
                    shipping = self.driver.find_elements_by_xpath(
                        '//*[@class="a-color-secondary"]'
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
                    offers = self.driver.find_elements_by_xpath(
                        "//div[@id='aod-offer']"
                    )
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
            try:
                price = parse_price(prices[idx].text)
            except IndexError:
                log.debug("Price index error")
                return False
            try:
                if self.checkshipping:
                    ship_price = shipping_prices[idx]
                else:
                    ship_price = parse_price("0")
            except IndexError:
                log.debug("shipping index error")
                return False
            ship_float = ship_price.amount
            price_float = price.amount
            if price_float is None:
                return False
            if ship_float is None or not self.checkshipping:
                ship_float = 0

            if (
                (ship_float + price_float) <= reserve_max
                or math.isclose((price_float + ship_float), reserve_max, abs_tol=0.01)
            ) and (
                (ship_float + price_float) >= reserve_min
                or math.isclose((price_float + ship_float), reserve_min, abs_tol=0.01)
            ):
                log.info("Item in stock and in reserve range!")
                log.info("clicking add to cart")
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
                if self.driver.title in amazon_config["SHOPPING_CART_TITLES"]:
                    return True
                else:
                    log.info("did not add to cart, trying again")
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
        # delay to wait for page load
        # time.sleep(self.page_wait_delay())

        title = self.driver.title
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
                element = self.driver.find_element_by_xpath(
                    '//*[contains(@class, "no-thanks-button") or contains(@class, "prime-nothanks-button") or contains(@class, "prime-no-button")]'
                )
            except sel_exceptions.NoSuchElementException:
                pass
            if element:
                try:
                    log.info(
                        "FairGame thinks it is seeing a Prime Offer, attempting to click No Thanks"
                    )
                    element.click()
                    self.wait_for_page_change(page_title=title)
                    # if we were able to click, return to program flow
                    return
                except sel_exceptions.ElementNotInteractableException:
                    log.debug("FairGame could not click No Thanks button")

            if self.shipping_bypass:
                element = None
                try:
                    element = self.driver.find_element_by_xpath(
                        '//*[@class="ship-to-this-address a-button a-button-primary a-button-span12 a-spacing-medium  "]'
                    )
                except sel_exceptions.NoSuchElementException:
                    pass
                if element:
                    log.warning("FairGame thinks it needs to pick a shipping address.")
                    log.warning(
                        "It will click whichever ship to this address button it found."
                    )
                    log.warning(
                        "If this works, VERIFY THE ADDRESS IT SHIPPED TO IMMEDIATELY!"
                    )
                    self.send_notification(
                        message="Clicking ship to address, hopefully this works. VERIFY ASAP!",
                        page_name="choose-shipping",
                        take_screenshot=self.take_screenshots,
                    )
                    try:
                        element.click()
                        log.info("Clicked button.")
                        self.wait_for_page_change(page_title=title)
                        return
                    except sel_exceptions.WebDriverException:
                        log.error("Could not click ship to address button")

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
                f"{title} is not a known title, please create issue indicating the title with a screenshot of page"
            )
            self.send_notification(
                "Encountered Unknown Page Title",
                "unknown-title",
                self.take_screenshots,
            )
            self.save_page_source("unknown-title")
            log.info("going to try and redirect to cart page")
            try:
                self.driver.get(AMAZON_URLS["CART_URL"])
            except sel_exceptions.WebDriverException:
                log.error(
                    "failed to load cart URL, refreshing and returning to handler"
                )
                self.driver.refresh()
                time.sleep(3)
                return
            self.wait_for_page_change(page_title=title)
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
            button = []
            while True:
                try:
                    button = self.driver.find_element_by_xpath(
                        '//*[@id="sc-buy-box-ptc-button"]'
                    )
                    break
                except sel_exceptions.NoSuchElementException:
                    pass
                if time.time() > timeout:
                    log.error(
                        "Could not find and click button, refreshing and returning to handler"
                    )
                    self.driver.refresh()
                    time.sleep(3)
                    break
            if button:
                try:
                    current_title = self.driver.title
                    log.info("Found ptc button, attempting to click.")
                    button.click()
                    log.info("Clicked ptc button")
                    self.wait_for_page_change(page_title=current_title)
                except sel_exceptions.WebDriverException:
                    log.info(
                        "Could not click button - refreshing and returning to checkout handler"
                    )
                    self.driver.refresh()
                    time.sleep(3)

    # returns negative number if cart element does not exist, returns number if cart exists
    def get_cart_count(self):
        # check if cart number is on the page, if cart items = 0
        try:
            element = self.driver.find_element_by_xpath('//*[@id="nav-cart-count"]')
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
            button = self.driver.find_element_by_xpath(
                # '//*[@class="a-button a-button-base no-thanks-button"]'
                '//*[contains(@class, "no-thanks-button") or contains(@class, "prime-nothanks-button") or contains(@class, "prime-no-button")]'
            )
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
            current_page = self.driver.title
            button.click()
            self.wait_for_page_change(current_page)
        else:
            log.error("Prime offer page popped up, user intervention required")
            self.notification_handler.play_alarm_sound()
            self.notification_handler.send_notification(
                "Prime offer page popped up, user intervention required"
            )
            timeout = self.get_timeout(timeout=60)
            while self.driver.title in amazon_config["PRIME_TITLES"]:
                if time.time() > timeout:
                    log.info(
                        "user did not intervene in time, will try and refresh page"
                    )
                    self.driver.refresh()
                    time.sleep(DEFAULT_MAX_WEIRD_PAGE_DELAY)
                    break

    @debug
    def handle_home_page(self):
        log.info("On home page, trying to get back to checkout")
        button = None
        try:
            button = self.driver.find_element_by_xpath('//*[@id="nav-cart"]')
        except sel_exceptions.NoSuchElementException:
            log.info("Could not find cart button")
        current_page = self.driver.title
        if button:
            button.click()
            self.wait_for_page_change(current_page)
        else:
            self.send_notification(
                "Could not click cart button, user intervention required",
                "home-page-error",
                self.take_screenshots,
            )
            timeout = self.get_timeout(timeout=300)
            while self.driver.title == current_page:
                time.sleep(0.25)
                if time.time() > timeout:
                    log.info(
                        "user failed to intervene in time, returning to stock check"
                    )
                    self.try_to_checkout = False
                    break

    @debug
    def handle_cart(self):
        self.start_time_atc = time.time()
        log.info("clicking checkout.")
        try:
            self.save_screenshot("ptc-page")
        except:
            pass
        timeout = self.get_timeout()
        button = None
        while True:
            try:
                button = self.driver.find_element_by_xpath(
                    '//*[@id="hlb-ptc-btn-native"]'
                )
                break
            except sel_exceptions.NoSuchElementException:
                try:
                    button = self.driver.find_element_by_xpath('//*[@id="hlb-ptc-btn"]')
                    break
                except sel_exceptions.NoSuchElementException:
                    pass
            if time.time() > timeout:
                log.info("couldn't find buttons to proceed to checkout")
                self.save_page_source("ptc-error")
                self.send_notification(
                    "Proceed to Checkout Error Occurred",
                    "ptc-error",
                    self.take_screenshots,
                )
                if self.get_cart_count() == 0:
                    log.info("It appears this is because you have no items in cart.")
                    log.info(
                        "It is likely that the product went out of stock before you could checkout"
                    )
                    log.info("Going back to stock check.")
                    self.try_to_checkout = False
                else:
                    log.info("Refreshing page to try again")
                    self.driver.refresh()
                    self.checkout_retry += 1
                return

        current_page = self.driver.title
        if button:
            if self.detailed:
                self.send_notification(
                    message="Attempting to Proceed to Checkout",
                    page_name="ptc",
                    take_screenshot=self.take_screenshots,
                )
            log.info("Found Checkout Button")
            try:
                button.click()
                log.info("Clicked Proceed to Checkout Button")
                self.wait_for_page_change(page_title=current_page)
            except sel_exceptions.WebDriverException:
                log.error("Problem clicking Proceed to Checkout button.")
                log.info("Refreshing page to try again")
                self.driver.refresh()
                self.wait_for_page_change(page_title=current_page)
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
                pass
            self.button_xpaths.append(self.button_xpaths.pop(0))
            if button:
                if button.is_enabled() and button.is_displayed():
                    break
            if time.time() > timeout:
                log.error("couldn't find buttons to proceed to checkout")
                self.save_page_source("ptc-error")
                self.send_notification(
                    "Error in checkout.  Please check browser window.",
                    "ptc-error",
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
            button.click()
        self.wait_for_page_change(page_title=previous_title)

    @debug
    def handle_order_complete(self):
        log.info("Order Placed.")
        self.send_notification("Order placed.", "order-placed", self.take_screenshots)
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
    def handle_captcha(self):
        # wait for captcha to load
        time.sleep(DEFAULT_MAX_WEIRD_PAGE_DELAY)
        current_page = self.driver.title
        try:
            if self.driver.find_element_by_xpath(
                '//form[@action="/errors/validateCaptcha"]'
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
                        self.driver.refresh()
                        time.sleep(3)
                    else:
                        self.send_notification(
                            "Solving catpcha", "captcha", self.take_screenshots
                        )
                        self.driver.find_element_by_xpath(
                            '//*[@id="captchacharacters"]'
                        ).send_keys(solution + Keys.RETURN)
                        self.wait_for_page_change(page_title=current_page)
                except Exception as e:
                    log.debug(e)
                    log.info("Error trying to solve captcha. Refresh and retry.")
                    self.driver.refresh()
                    time.sleep(3)
        except sel_exceptions.NoSuchElementException:
            log.error("captcha page does not contain captcha element")
            log.error("refreshing")
            self.driver.refresh()
            time.sleep(3)

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
        if self.no_image:
            log.info(f"--No images will be requested")
        if not self.notification_handler.sound_enabled:
            log.info(f"--Notification sounds are disabled.")
        if self.headless:
            log.warning(
                f"--Running headless is unsupported.  If you get it to work, please let us know on Discord."
            )
        if self.testing:
            log.warning(f"--Testing Mode.  NO Purchases will be made.")
        log.info(f"{'=' * 50}")

    def create_driver(self):
        if self.setup_driver:

            if self.headless:
                enable_headless()

            # profile_amz = ".profile-amz"
            # # keep profile bloat in check
            # if os.path.isdir(profile_amz):
            #     os.remove(profile_amz)
            prefs = {
                "profile.password_manager_enabled": False,
                "credentials_enable_service": False,
            }
            if self.no_image:
                prefs["profile.managed_default_content_settings.images"] = 2
            else:
                prefs["profile.managed_default_content_settings.images"] = 0
            options.add_experimental_option("prefs", prefs)
            path_to_profile = os.path.join(
                os.path.dirname(os.path.abspath("__file__")), ".profile-amz"
            )
            options.add_argument(f"user-data-dir={path_to_profile}")
            if not self.slow_mode:
                options.set_capability("pageLoadStrategy", "none")

            self.setup_driver = False

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
        try:
            self.driver = webdriver.Chrome(executable_path=binary_path, options=options)
            self.wait = WebDriverWait(self.driver, 10)
            self.get_webdriver_pids()
        except Exception as e:
            log.error(e)
            log.error(
                "If you have a JSON warning above, try deleting your .profile-amz folder"
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
    # Assume Free Shipping and change otherwise

    # Shipping collection xpath:
    # .//div[starts-with(@id, 'aod-bottlingDepositFee-')]/following-sibling::span
    shipping_nodes = tree.xpath(
        ".//div[starts-with(@id, 'aod-bottlingDepositFee-')]/following-sibling::*[1]"
    )
    count = len(shipping_nodes)
    log.debug(f"Found {count} shipping nodes.")
    if count == 0:
        log.warning("No shipping nodes found.  Assuming zero.")
        return FREE_SHIPPING_PRICE
    elif count > 1:
        log.warning("Found multiple shipping nodes.  Using the first.")

    shipping_node = shipping_nodes[0]
    # Shipping information is found within either a DIV or a SPAN following the bottleDepositFee DIV
    # What follows is logic to parse out the various pricing formats within the HTML.  Not ideal, but
    # it's what we have to work with.
    shipping_span_text = shipping_node.text.strip()
    if shipping_node.tag == "div":
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
        elif any(shipping_span_text.upper() in free_message for free_message in amazon_config["FREE_SHIPPING"]):
            # We found some version of "free" inside the span.. but this relies on a match
            log.warning(f"Assuming free shipping based on this message: '{shipping_span_text}'")
        else:
            log.error(
                f"Unable to locate price.  Assuming 0.  Found this: '{shipping_span_text}'  Consider reporting to #tech-support Discord."
            )
    return FREE_SHIPPING_PRICE
