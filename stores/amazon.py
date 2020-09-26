import json
import secrets
import time
from os import path

from chromedriver_py import binary_path  # this will get you the path variable
from furl import furl
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By

from notifications.notifications import NotificationHandler
from utils import selenium_utils
from utils.json_utils import InvalidAutoBuyConfigException
from utils.logger import log
from utils.selenium_utils import options, enable_headless, wait_for_element

AMAZON_URLS = {
    "BASE_URL": "https://www.{}/",
    "CART_URL": "https://www.{}/gp/aws/cart/add.html",
}

AUTOBUY_CONFIG_PATH = "amazon_config.json"

SIGN_IN_TITLES = ["Amazon Sign In", "Amazon Sign-In", "Amazon Anmelden"]
SHOPING_CART_TITLES = [
    "Amazon.com Shopping Cart",
    "Amazon.co.uk Shopping Basket",
    "Amazon.de Basket",
]
CHECKOUT_TITLES = [
    "Amazon.com Checkout",
    "Place Your Order - Amazon.co.uk Checkout",
    "Place Your Order - Amazon.de Checkout",
    "Place Your Order - Amazon.com Checkout",
    "Place Your Order - Amazon.com",
]
ORDER_COMPLETE_TITLES = ["Amazon.com Thanks You", "Thank you"]
ADD_TO_CART_TITLES = [
    "Amazon.com: Please Confirm Your Action",
    "Amazon.de: Bitte bestätigen Sie Ihre Aktion",
    "Amazon.de: Please Confirm Your Action",
]


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
                    self.amazon_website = config.get("amazon_website", "amazon.com")
                    self.price_limit = config["price_limit"]
                    assert isinstance(self.asin_list, list)
                except Exception:
                    raise InvalidAutoBuyConfigException(
                        "amazon_config.json file not formatted properly."
                    )
        else:
            raise InvalidAutoBuyConfigException("Missing amazon_config.json file.")

        for key in AMAZON_URLS.keys():
            AMAZON_URLS[key] = AMAZON_URLS[key].format(self.amazon_website)
        print(AMAZON_URLS)
        self.driver.get(AMAZON_URLS["BASE_URL"])
        if self.is_logged_in():
            log.info("Already logged in")
        else:
            log.info("Lets log in.")
            selenium_utils.button_click_using_xpath(
                self.driver, '//*[@id="nav-link-accountList"]/div/span'
            )
            selenium_utils.wait_for_any_title(self.driver, SIGN_IN_TITLES)
            self.login()
            log.info("Waiting 15 seconds.")
            time.sleep(
                15
            )  # We can remove this once I get more info on the phone verification page.

    def is_logged_in(self):
        try:
            text = wait_for_element(self.driver, "nav-link-accountList").text
            return "Hello, Sign in" not in text
        except Exception:
            return False

    def login(self):

        try:
            log.info("Email")
            self.driver.find_element_by_xpath('//*[@id="ap_email"]').send_keys(
                self.username + Keys.RETURN
            )
        except:
            log.info("Email not needed.")
            pass

        log.info("Password")
        self.driver.find_element_by_xpath('//input[@name="rememberMe"]').click()
        self.driver.find_element_by_xpath('//*[@id="ap_password"]').send_keys(
            self.password + Keys.RETURN
        )

        log.info(f"Logged in as {self.username}")

    def run_item(self, delay=3, test=False):
        log.info("Checking stock for items.")
        while not self.something_in_stock():
            time.sleep(delay)
        self.notification_handler.send_notification(
            "Your items on Amazon.com were found!"
        )
        self.checkout(test=test)

    def something_in_stock(self):
        params = {"anticache": str(secrets.token_urlsafe(32))}

        for x in range(len(self.asin_list)):
            params[f"ASIN.{x + 1}"] = self.asin_list[x]
            params[f"Quantity.{x + 1}"] = 1

        f = furl(AMAZON_URLS["CART_URL"])
        f.set(params)
        self.driver.get(f.url)
        selenium_utils.wait_for_any_title(self.driver, ADD_TO_CART_TITLES)
        prices = self.driver.find_elements_by_xpath('//td[@class="price item-row"]')
        prices2 = self.driver.find_elements_by_xpath('//td[@class="price item-row"]')
        dont_refresh = True

        if prices:
            log.info("One or more items in stock!")

            # Check against limit price
            for price_str in prices:
                price_int = int(
                    round(float(price_str.text.replace("$", "").replace(",", "")))
                )

                if price_int <= self.price_limit:
                    # Loop through all available cards and remove ones above price limit
                    for price_str2 in prices2:
                        price_int2 = int(
                            round(
                                float(price_str.text.replace("$", "").replace(",", ""))
                            )
                        )
                        product_link = price_str2.find_element(
                            By.XPATH, (".//preceding-sibling::td[2]//a")
                        )
                        asin = product_link.get_attribute("href")[-10:]
                        log.info(asin)

                        if price_int2 > self.price_limit:
                            log.info(
                                "Removing overpriced item(s) and continuing with purchase!"
                            )
                            # Remove item from list
                            self.asin_list.remove(asin)
                            dont_refresh = False

                    return dont_refresh
                else:
                    log.info(
                        "Keeping in stock but overpriced items in cart. Will purchase if price falls under limit."
                    )
        else:
            return False

    def wait_for_cart_page(self):
        selenium_utils.wait_for_any_title(self.driver, SHOPING_CART_TITLES)
        log.info("On cart page.")

    def wait_for_pyo_page(self):
        selenium_utils.wait_for_any_title(self.driver, CHECKOUT_TITLES + SIGN_IN_TITLES)

        if self.driver.title in SIGN_IN_TITLES:
            log.info("Need to sign in again")
            self.login()

    def finalize_order_button(self, test, retry=0):
        button_xpaths = [
            '//*[@id="bottomSubmitOrderButtonId"]/span/input',
            '//*[@id="placeYourOrder"]/span/input',
            '//*[@id="submitOrderButtonId"]/span/input',
            '//input[@name="placeYourOrder1"]',
        ]
        button = None
        for button_xpath in button_xpaths:
            try:
                if (
                    self.driver.find_element_by_xpath(button_xpath).is_displayed()
                    and self.driver.find_element_by_xpath(button_xpath).is_enabled()
                ):
                    button = self.driver.find_element_by_xpath(button_xpath)
            except NoSuchElementException:
                log.debug(f"{button_xpath}, lets try a different one.")

        if button:
            log.info(f"Clicking Button: {button}")
            if not test:
                button.click()
            return
        else:
            if retry < 3:
                log.info("Couldn't find button. Lets retry in a sec.")
                time.sleep(5)
                self.finalize_order_button(test, retry + 1)
            else:
                log.info(
                    "Couldn't find button after 3 retries. Open a GH issue for this."
                )

    def wait_for_order_completed(self, test):
        if not test:
            selenium_utils.wait_for_any_title(self.driver, ORDER_COMPLETE_TITLES)
        else:
            log.info(
                "This is a test, so we don't need to wait for the order completed page."
            )

    def checkout(self, test):
        log.info("Clicking continue.")
        self.driver.find_element_by_xpath('//input[@value="add"]').click()

        log.info("Waiting for Cart Page")
        self.wait_for_cart_page()

        log.info("clicking checkout.")
        self.driver.find_element_by_xpath(
            '//*[@id="sc-buy-box-ptc-button"]/span/input'
        ).click()

        log.info("Waiting for Place Your Order Page")
        self.wait_for_pyo_page()

        log.info("Finishing checkout")
        self.finalize_order_button(test)

        log.info("Waiting for Order completed page.")
        self.wait_for_order_completed(test)

        log.info("Order Placed.")
