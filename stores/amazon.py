import json
import secrets
import time
from os import path

from amazoncaptcha import AmazonCaptcha
from chromedriver_py import binary_path  # this will get you the path variable
from furl import furl
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from notifications.notifications import AppriseHandler
from utils import selenium_utils
from utils.json_utils import InvalidAutoBuyConfigException
from utils.logger import log
from utils.selenium_utils import options, enable_headless, wait_for_element

AMAZON_URLS = {
    "BASE_URL": "https://www.{domain}/",
    "CART_URL": "https://www.{domain}/gp/aws/cart/add.html",
}
CHECKOUT_URL = "https://www.{domain}/gp/cart/desktop/go-to-checkout.html/ref=ox_sc_proceed?partialCheckoutCart=1&isToBeGiftWrappedBefore=0&proceedToRetailCheckout=Proceed+to+checkout&proceedToCheckout=1&cartInitiateId={cart_id}"

AUTOBUY_CONFIG_PATH = "amazon_config.json"

SIGN_IN_TITLES = ["Amazon Sign In", "Amazon Sign-In", "Amazon Anmelden"]
CAPTCHA_PAGE_TITLES = ["Robot Check"]
HOME_PAGE_TITLES = [
    "Amazon.com: Online Shopping for Electronics, Apparel, Computers, Books, DVDs & more",
    "Amazon.co.uk: Low Prices in Electronics, Books, Sports Equipment & more",
    "Amazon.de: Low Prices in Electronics, Books, Sports Equipment & more",
    "Amazon.de: Günstige Preise für Elektronik & Foto, Filme, Musik, Bücher, Games, Spielzeug & mehr",
    "Amazon.es: compra online de electrónica, libros, deporte, hogar, moda y mucho más.",
    "Amazon.de: Günstige Preise für Elektronik & Foto, Filme, Musik, Bücher, Games, Spielzeug & mehr",
]
SHOPING_CART_TITLES = [
    "Amazon.com Shopping Cart",
    "Amazon.co.uk Shopping Basket",
    "Amazon.de Basket",
    "Amazon.de Einkaufswagen",
    "Cesta de compra Amazon.es",
]
CHECKOUT_TITLES = [
    "Amazon.com Checkout",
    "Place Your Order - Amazon.co.uk Checkout",
    "Amazon.de Checkout",
    "Place Your Order - Amazon.de Checkout",
    "Amazon.de - Bezahlvorgang",
    "Place Your Order - Amazon.com Checkout",
    "Place Your Order - Amazon.com",
    "Tramitar pedido en Amazon.es",
]
ORDER_COMPLETE_TITLES = ["Amazon.com Thanks You", "Thank you"]
ADD_TO_CART_TITLES = [
    "Amazon.com: Please Confirm Your Action",
    "Amazon.de: Bitte bestätigen Sie Ihre Aktion",
    "Amazon.de: Please Confirm Your Action",
    "Amazon.es: confirma tu acción",
]


class Amazon:
    def __init__(self, notification_handler, headless=False):
        self.notification_handler = notification_handler
        self.apprise_handler = AppriseHandler()
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
                    assert isinstance(self.asin_list, list)
                except Exception:
                    raise InvalidAutoBuyConfigException(
                        "amazon_config.json file not formatted properly."
                    )
        else:
            log.error(
                "No config file found, see here on how to fix this: https://github.com/Hari-Nagarajan/nvidia-bot#amazon"
            )
            exit(0)

        for key in AMAZON_URLS.keys():
            AMAZON_URLS[key] = AMAZON_URLS[key].format(domain=self.amazon_website)
        print(AMAZON_URLS)
        self.driver.get(AMAZON_URLS["BASE_URL"])
        log.info("Waiting for home page.")
        self.check_if_captcha(self.wait_for_pages, HOME_PAGE_TITLES)

        if self.is_logged_in():
            log.info("Already logged in")
        else:
            log.info("Lets log in.")
            selenium_utils.button_click_using_xpath(
                self.driver, '//*[@id="nav-link-accountList"]/div/span'
            )
            log.info("Wait for Sign In page")
            self.check_if_captcha(self.wait_for_pages, SIGN_IN_TITLES)
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

        log.info("Remember me checkbox")
        selenium_utils.button_click_using_xpath(self.driver, '//*[@name="rememberMe"]')

        log.info("Password")
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
        self.check_if_captcha(self.wait_for_pages, ADD_TO_CART_TITLES)
        if self.driver.find_elements_by_xpath('//td[@class="price item-row"]'):
            log.info("One or more items in stock!")

            return True
        else:
            return False

    def get_captcha_help(self):
        if not self.on_captcha_page():
            log.info("Not on captcha page.")
            return
        try:
            log.info("Stuck on a captcha... Lets try to solve it.")
            captcha = AmazonCaptcha.from_webdriver(self.driver)
            solution = captcha.solve()
            log.info(f"The solution is: {solution}")
            if solution == "Not solved":
                log.info(f"Failed to solve, lets reload and get a new captcha.")
                self.driver.refresh()
                time.sleep(5)
                self.get_captcha_help()
            else:
                self.driver.save_screenshot("screenshot.png")
                self.apprise_handler.send(f"Solving Captcha: {solution}")
                self.driver.find_element_by_xpath(
                    '//*[@id="captchacharacters"]'
                ).send_keys(solution + Keys.RETURN)
        except Exception as e:
            log.debug(e)
            log.info("Error trying to solve captcha. Refresh and retry.")
            self.driver.refresh()
            time.sleep(5)

    def on_captcha_page(self):
        try:
            if self.driver.title in CAPTCHA_PAGE_TITLES:
                return True
            if self.driver.find_element_by_xpath(
                '//form[@action="/errors/validateCaptcha"]'
            ):
                return True
        except Exception:
            pass
        return False

    def check_if_captcha(self, func, args):
        try:
            func(args)
        except Exception as e:
            log.debug(str(e))
            if self.on_captcha_page():
                self.get_captcha_help()
                func(args, t=300)
            else:
                log.debug(self.driver.title)
                log.error(
                    f"An error happened, please submit a bug report including a screenshot of the page the "
                    f"selenium browser is on. There may be a file saved at: amazon-{func.__name__}.png"
                )
                screenshot_name = f"amazon-{func.__name__}.png"
                self.driver.save_screenshot(screenshot_name)
                self.apprise_handler.send(
                    f"Error on {self.driver.title}", screenshot_name
                )
                time.sleep(60)
                self.driver.close()
                raise e

    def wait_for_pages(self, page_titles, t=30):
        log.debug(f"wait_for_pages({page_titles}, {t})")
        selenium_utils.wait_for_any_title(self.driver, page_titles, t)

    def wait_for_pyo_page(self):
        self.check_if_captcha(self.wait_for_pages, CHECKOUT_TITLES + SIGN_IN_TITLES)

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
            log.info(f"Clicking Button: {button.text}")
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
            self.check_if_captcha(self.wait_for_pages, ORDER_COMPLETE_TITLES)
        else:
            log.info(
                "This is a test, so we don't need to wait for the order completed page."
            )

    def checkout(self, test):
        log.info("Clicking continue.")
        self.driver.save_screenshot("screenshot.png")
        self.apprise_handler.send("Starting Checkout", "screenshot.png")
        self.driver.find_element_by_xpath('//input[@value="add"]').click()

        log.info("Waiting for Cart Page")
        self.check_if_captcha(self.wait_for_pages, SHOPING_CART_TITLES)
        self.driver.save_screenshot("screenshot.png")
        self.apprise_handler.send("Cart Page", "screenshot.png")

        try:  # This is fast.
            log.info("Quick redirect to checkout page")
            cart_initiate_id = self.driver.find_element_by_name("cartInitiateId")
            cart_initiate_id = cart_initiate_id.get_attribute("value")
            self.driver.get(
                CHECKOUT_URL.format(
                    domain=self.amazon_website, cart_id=cart_initiate_id
                )
            )
        except:
            log.info("clicking checkout.")
            try:
                self.driver.find_element_by_xpath(
                    '//*[@id="sc-buy-box-ptc-button"]/span/input'
                ).click()
            finally:
                self.driver.save_screenshot("screenshot.png")
                self.apprise_handler.send(
                    "Failed to checkout. Returning to stock check.", "screenshot.png"
                )
                log.info("Failed to checkout. Returning to stock check.")
                self.run_item(test=test)

        log.info("Waiting for Place Your Order Page")
        self.wait_for_pyo_page()

        log.info("Finishing checkout")
        self.driver.save_screenshot("screenshot.png")
        self.apprise_handler.send("Finishing checkout", "screenshot.png")

        self.finalize_order_button(test)

        log.info("Waiting for Order completed page.")
        self.wait_for_order_completed(test)

        log.info("Order Placed.")
        self.driver.save_screenshot("screenshot.png")
        self.apprise_handler.send("Order Placed", "screenshot.png")

        time.sleep(20)
