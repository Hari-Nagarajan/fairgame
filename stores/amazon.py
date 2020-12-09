import json
import math
import os
import random
import time
from datetime import datetime

import stdiomask
from amazoncaptcha import AmazonCaptcha
from chromedriver_py import binary_path  # this will get you the path variable
from furl import furl
from price_parser import parse_price
from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from utils.debugger import debug
from utils.discord_presence import searching_update, buy_update, start_presence
from utils.encryption import create_encrypted_config, load_encrypted_config
from utils.logger import log
from utils.selenium_utils import options, enable_headless
from utils.version import version

AMAZON_URLS = {
    "BASE_URL": "https://{domain}/",
    "OFFER_URL": "https://{domain}/gp/offer-listing/",
}
CHECKOUT_URL = "https://{domain}/gp/cart/desktop/go-to-checkout.html/ref=ox_sc_proceed?partialCheckoutCart=1&isToBeGiftWrappedBefore=0&proceedToRetailCheckout=Proceed+to+checkout&proceedToCheckout=1&cartInitiateId={cart_id}"

AUTOBUY_CONFIG_PATH = "config/amazon_config.json"
CREDENTIAL_FILE = "config/amazon_credentials.json"

SIGN_IN_TEXT = [
    "Hello, Sign in",
    "Sign in",
    "Hola, Identifícate",
    "Bonjour, Identifiez-vous",
    "Ciao, Accedi",
    "Hallo, Anmelden",
    "Hallo, Inloggen",
]
SIGN_IN_TITLES = [
    "Amazon Sign In",
    "Amazon Sign-In",
    "Amazon Anmelden",
    "Iniciar sesión en Amazon",
    "Connexion Amazon",
    "Amazon Accedi",
    "Inloggen bij Amazon",
]
CAPTCHA_PAGE_TITLES = ["Robot Check"]
HOME_PAGE_TITLES = [
    "Amazon.com: Online Shopping for Electronics, Apparel, Computers, Books, DVDs & more",
    "AmazonSmile: You shop. Amazon gives.",
    "Amazon.ca: Low Prices – Fast Shipping – Millions of Items",
    "Amazon.co.uk: Low Prices in Electronics, Books, Sports Equipment & more",
    "Amazon.de: Low Prices in Electronics, Books, Sports Equipment & more",
    "Amazon.de: Günstige Preise für Elektronik & Foto, Filme, Musik, Bücher, Games, Spielzeug & mehr",
    "Amazon.es: compra online de electrónica, libros, deporte, hogar, moda y mucho más.",
    "Amazon.de: Günstige Preise für Elektronik & Foto, Filme, Musik, Bücher, Games, Spielzeug & mehr",
    "Amazon.fr : livres, DVD, jeux vidéo, musique, high-tech, informatique, jouets, vêtements, chaussures, sport, bricolage, maison, beauté, puériculture, épicerie et plus encore !",
    "Amazon.it: elettronica, libri, musica, fashion, videogiochi, DVD e tanto altro",
    "Amazon.nl: Groot aanbod, kleine prijzen in o.a. Elektronica, boeken, sport en meer",
]
SHOPING_CART_TITLES = [
    "Amazon.com Shopping Cart",
    "Amazon.ca Shopping Cart",
    "Amazon.co.uk Shopping Basket",
    "Amazon.de Basket",
    "Amazon.de Einkaufswagen",
    "AmazonSmile Einkaufswagen",
    "Cesta de compra Amazon.es",
    "Amazon.fr Panier",
    "Carrello Amazon.it",
    "AmazonSmile Shopping Cart",
    "AmazonSmile Shopping Basket",
    "Amazon.nl-winkelwagen",
]
CHECKOUT_TITLES = [
    "Amazon.com Checkout",
    "Amazon.co.uk Checkout",
    "Place Your Order - Amazon.ca Checkout",
    "Place Your Order - Amazon.co.uk Checkout",
    "Amazon.de Checkout",
    "Place Your Order - Amazon.de Checkout",
    "Amazon.de - Bezahlvorgang",
    "Bestellung aufgeben - Amazon.de-Bezahlvorgang",
    "Place Your Order - Amazon.com Checkout",
    "Place Your Order - Amazon.com",
    "Tramitar pedido en Amazon.es",
    "Processus de paiement Amazon.com",
    "Confirmar pedido - Compra Amazon.es",
    "Passez votre commande - Processus de paiement Amazon.fr",
    "Ordina - Cassa Amazon.it",
    "AmazonSmile Checkout",
    "Plaats je bestelling - Amazon.nl-kassa",
    "Place Your Order - AmazonSmile Checkout",
    "Preparing your order",
    "Ihre Bestellung wird vorbereitet",
]
ORDER_COMPLETE_TITLES = [
    "Amazon.com Thanks You",
    "Amazon.ca Thanks You",
    "AmazonSmile Thanks You",
    "Thank you",
    "Amazon.fr Merci",
    "Merci",
    "Amazon.es te da las gracias",
    "Amazon.fr vous remercie.",
    "Grazie da Amazon.it",
    "Hartelijk dank",
    "Thank You",
    "Amazon.de Vielen Dank",
]
ADD_TO_CART_TITLES = [
    "Amazon.com: Please Confirm Your Action",
    "Amazon.de: Bitte bestätigen Sie Ihre Aktion",
    "Amazon.de: Please Confirm Your Action",
    "Amazon.es: confirma tu acción",
    "Amazon.com : Veuillez confirmer votre action",  # Careful, required non-breaking space after .com (&nbsp)
    "Amazon.it: confermare l'operazione",
    "AmazonSmile: Please Confirm Your Action",
    "",  # Amazon.nl has en empty title, sigh.
]
DOGGO_TITLES = ["Sorry! Something went wrong!"]

# this is not non-US friendly
SHIPPING_ONLY_IF = "FREE Shipping on orders over"

TWOFA_TITLES = ["Two-Step Verification"]

PRIME_TITLES = ["Complete your Amazon Prime sign up"]

OUT_OF_STOCK = ["Out of Stock - AmazonSmile Checkout"]

# OFFER_PAGE_TITLES = ["Amazon.com: Buying Choices:"]

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


DEFAULT_MAX_CHECKOUT_LOOPS = 20
DEFAULT_MAX_PTC_TRIES = 3
DEFAULT_MAX_PYO_TRIES = 3
DEFAULT_MAX_ATC_TRIES = 3
DEFAULT_MAX_WEIRD_PAGE_DELAY = 5
DEFAULT_PAGE_WAIT_DELAY = 0.5  # also serves as minimum wait for randomized delays
DEFAULT_MAX_PAGE_WAIT_DELAY = 1.0  # used for random page wait delay
MAX_CHECKOUT_BUTTON_WAIT = 3  # integers only


class Amazon:
    def __init__(
        self,
        notification_handler,
        headless=False,
        checkshipping=False,
        random_delay=False,
        detailed=False,
        used=False,
        single_shot=False,
        no_screenshots=False,
        disable_presence=False,
    ):
        self.notification_handler = notification_handler
        self.asin_list = []
        self.reserve_min = []
        self.reserve_max = []
        self.checkshipping = checkshipping
        self.button_xpaths = BUTTON_XPATHS
        self.random_delay = random_delay
        self.detailed = detailed
        self.used = used
        self.single_shot = single_shot
        self.disable_presence = disable_presence
        self.take_screenshots = not no_screenshots
        self.start_time = time.time()
        self.start_time_atc = 0

        if not self.disable_presence:
            start_presence("Spinning up")

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

        if os.path.exists(CREDENTIAL_FILE):
            credential = load_encrypted_config(CREDENTIAL_FILE)
            self.username = credential["username"]
            self.password = credential["password"]
        else:
            log.info("No credential file found, let's make one")
            credential = self.await_credential_input()
            create_encrypted_config(credential, CREDENTIAL_FILE)
            self.username = credential["username"]
            self.password = credential["password"]

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

        if headless:
            enable_headless()

        # profile_amz = ".profile-amz"
        # # keep profile bloat in check
        # if os.path.isdir(profile_amz):
        #     os.remove(profile_amz)
        options.add_argument(f"user-data-dir=.profile-amz")

        try:
            self.driver = webdriver.Chrome(executable_path=binary_path, options=options)
            self.wait = WebDriverWait(self.driver, 10)
        except Exception as e:
            log.info("you probably have chrome open, you should close it")
            log.error(e)
            exit(1)

        for key in AMAZON_URLS.keys():
            AMAZON_URLS[key] = AMAZON_URLS[key].format(domain=self.amazon_website)

    @staticmethod
    def await_credential_input():
        username = input("Amazon login ID: ")
        password = stdiomask.getpass(prompt="Amazon Password: ")
        return {
            "username": username,
            "password": password,
        }

    def run(self, delay=3, test=False):
        log.info("Waiting for home page.")
        while True:
            try:
                self.driver.get(AMAZON_URLS["BASE_URL"])
                break
            except Exception:
                log.error(
                    "Couldn't talk to "
                    + AMAZON_URLS["BASE_URL"]
                    + ", if the address is right, there might be a network outage..."
                )
                time.sleep(3)
                pass
        self.handle_startup()
        if not self.is_logged_in():
            self.login()
        self.send_notification(
            "Bot Logged in and Starting up", "Start-Up", self.take_screenshots
        )

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
                except exceptions.StaleElementReferenceException:
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
                elif self.order_retry > DEFAULT_MAX_PYO_TRIES:
                    if test:
                        self.remove_asin_list(asin)
                    self.try_to_checkout = False
                loop_iterations += 1
                if loop_iterations > DEFAULT_MAX_CHECKOUT_LOOPS:
                    self.try_to_checkout = False
            # if no items left it list, let loop end
            if not self.asin_list:
                keep_going = False
        runtime = time.time() - self.start_time
        log.info(f"FairGame bot ran for {runtime} seconds.")

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
            except exceptions.NoSuchElementException:
                log.error("Log in button does not exist")
            log.info("Wait for Sign In page")
            time.sleep(self.page_wait_delay())

    @debug
    def is_logged_in(self):
        try:
            text = self.driver.find_element_by_id("nav-link-accountList").text
            return not any(sign_in in text for sign_in in SIGN_IN_TEXT)
        except exceptions.NoSuchElementException:
            return False

    @debug
    def login(self):

        try:
            log.info("Email")
            self.driver.find_element_by_xpath('//*[@id="ap_email"]').send_keys(
                self.username + Keys.RETURN
            )
        except exceptions.NoSuchElementException:
            log.info("Email not needed.")
            pass

        if self.driver.find_elements_by_xpath('//*[@id="auth-error-message-box"]'):
            log.error("Login failed, check your username in amazon_config.json")
            time.sleep(240)
            exit(1)

        log.info("Remember me checkbox")
        try:
            self.driver.find_element_by_xpath('//*[@name="rememberMe"]').click()
        except exceptions.NoSuchElementException:
            log.error("Remember me checkbox did not exist")

        log.info("Password")
        try:
            self.driver.find_element_by_xpath('//*[@id="ap_password"]').send_keys(
                self.password + Keys.RETURN
            )
        except exceptions.NoSuchElementException:
            log.error("Password entry box did not exist")

        time.sleep(self.page_wait_delay())
        if self.driver.title in TWOFA_TITLES:
            log.info("enter in your two-step verification code in browser")
            while self.driver.title in TWOFA_TITLES:
                time.sleep(DEFAULT_MAX_WEIRD_PAGE_DELAY)
        log.info(f"Logged in as {self.username}")

    @debug
    def run_asins(self, delay):
        found_asin = False
        while not found_asin:
            for i in range(len(self.asin_list)):
                for asin in self.asin_list[i]:
                    if self.check_stock(asin, self.reserve_min[i], self.reserve_max[i]):
                        return asin
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

        if not self.disable_presence:
            try:
                searching_update()
            except:
                pass

        try:
            while True:
                try:
                    self.driver.get(f.url)
                    break
                except Exception:
                    log.error("Failed to get the URL, were in the exception now.")
                    time.sleep(3)
                    pass
            elements = self.driver.find_elements_by_xpath(
                '//*[@name="submit.addToCart"]'
            )
            prices = self.driver.find_elements_by_xpath(
                '//*[@class="a-size-large a-color-price olpOfferPrice a-text-bold"]'
            )
            shipping = self.driver.find_elements_by_xpath(
                '//*[@class="a-color-secondary"]'
            )
        except Exception as e:
            log.error(e)
            return None

        in_stock = False
        for i in range(len(elements)):
            price = parse_price(prices[i].text)
            if SHIPPING_ONLY_IF in shipping[i].text:
                ship_price = parse_price("0")
            else:
                ship_price = parse_price(shipping[i].text)
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

                if not self.disable_presence:
                    try:
                        buy_update()
                    except:
                        pass

                elements[i].click()
                time.sleep(self.page_wait_delay())
                if self.driver.title in SHOPING_CART_TITLES:
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
        time.sleep(self.page_wait_delay())

        title = self.driver.title
        if title in SIGN_IN_TITLES:
            self.login()
        elif title in CAPTCHA_PAGE_TITLES:
            self.handle_captcha()
        elif title in SHOPING_CART_TITLES:
            self.handle_cart()
        elif title in CHECKOUT_TITLES:
            self.handle_checkout(test)
        elif title in ORDER_COMPLETE_TITLES:
            self.handle_order_complete()
        elif title in PRIME_TITLES:
            self.handle_prime_signup()
        elif title in HOME_PAGE_TITLES:
            # if home page, something went wrong
            self.handle_home_page()
        elif title in DOGGO_TITLES:
            self.handle_doggos()
        elif title in OUT_OF_STOCK:
            self.handle_out_of_stock()
        else:
            log.error(
                f"{title} is not a known title, please create issue indicating the title with a screenshot of page"
            )
            self.send_notification(
                "Encountered Unknown Page Title", "unknown-title", self.take_screenshots
            )
            self.save_page_source("unknown-title")

    @debug
    def handle_prime_signup(self):
        log.info("Prime offer page popped up, attempting to click No Thanks")
        button = None
        try:
            button = self.driver.find_element_by_xpath(
                # '//*[@class="a-button a-button-base no-thanks-button"]'
                '//*[contains(@class, "no-thanks-button") or contains(@class, "prime-nothanks-button") or contains(@class, "prime-no-button")]'
            )
        except exceptions.NoSuchElementException:
            log.error("could not find button")
            # log.info("check if PYO button hidden")
            # try:
            #     button = self.driver.find_element_by_xpath(
            #         '//*[@id="placeYourOrder"]/span/input'
            #     )
            # except exceptions.NoSuchElementException:
            #     log.error("couldn't find PYO button")
            log.info("sign up for Prime and this won't happen anymore")
            self.save_page_source("prime-signup-error")
            self.send_notification(
                "Prime Sign-up Error occurred",
                "prime-signup-error",
                self.take_screenshots,
            )
        if button:
            button.click()
        else:
            log.error("Prime offer page popped up, user intervention required")
            self.notification_handler.send_notification(
                "Prime offer page popped up, user intervention required"
            )
            time.sleep(DEFAULT_MAX_WEIRD_PAGE_DELAY)
            self.driver.refresh()

    @debug
    def handle_home_page(self):
        log.info("On home page, trying to get back to checkout")
        button = None
        try:
            button = self.driver.find_element_by_xpath('//*[@id="nav-cart"]')
        except exceptions.NoSuchElementException:
            log.info("Could not find cart button")
        if button:
            button.click()
        else:
            self.notification_handler.send_notification(
                "Could not click cart button, user intervention required"
            )
            time.sleep(DEFAULT_MAX_WEIRD_PAGE_DELAY)

    @debug
    def handle_cart(self):
        self.start_time_atc = time.time()
        log.info("clicking checkout.")
        try:
            self.save_screenshot("ptc-page")
        except:
            pass
        try:
            self.driver.find_element_by_xpath('//*[@id="hlb-ptc-btn-native"]').click()
        except exceptions.NoSuchElementException:
            try:
                self.driver.find_element_by_xpath('//*[@id="hlb-ptc-btn"]').click()
            except exceptions.NoSuchElementException:
                log.error("couldn't find buttons to proceed to checkout")
                self.save_page_source("ptc-error")
                self.send_notification(
                    "Proceed to Checkout Error Occurred",
                    "ptc-error",
                    self.take_screenshots,
                )
                log.info("Refreshing page to try again")
                self.driver.refresh()
                self.checkout_retry += 1

    @debug
    def handle_checkout(self, test):
        previous_title = self.driver.title
        button = None
        i = 0
        for i in range(len(self.button_xpaths)):
            try:
                if (
                    self.driver.find_element_by_xpath(
                        self.button_xpaths[0]
                    ).is_displayed()
                    and self.driver.find_element_by_xpath(
                        self.button_xpaths[0]
                    ).is_enabled()
                ):
                    button = self.driver.find_element_by_xpath(self.button_xpaths[0])
            except exceptions.NoSuchElementException:
                log.debug(f"{self.button_xpaths[0]}, lets try a different one.")
            if button:
                if not test:
                    log.info(f"Clicking Button: {button.text}")
                    button.click()
                    j = 0
                    while (
                        self.driver.title == previous_title
                        and j < MAX_CHECKOUT_BUTTON_WAIT
                    ):
                        time.sleep(self.page_wait_delay())
                        j += 1
                    if self.driver.title != previous_title:
                        break
                    else:
                        log.info(
                            f"Button {self.button_xpaths[0]} didn't work, trying another one"
                        )
                else:
                    log.info(f"Found button {button.text}, but this is a test")
                    log.info("will not try to complete order")
                    self.try_to_checkout = False
                    self.great_success = True
                    if self.single_shot:
                        self.asin_list = []
                    break
            self.button_xpaths.append(self.button_xpaths.pop(0))
        if not test and self.driver.title == previous_title:
            # Could not click button, refresh page and try again
            log.error("couldn't find buttons to proceed to checkout")
            self.save_page_source("ptc-error")
            self.send_notification(
                "Error in checkout.  Please check browser window.",
                "ptc-error",
                self.take_screenshots,
            )
            log.info("Refreshing page to try again")
            self.driver.refresh()
            self.order_retry += 1

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
                    else:
                        self.send_notification(
                            "Solving catpcha", "captcha", self.take_screenshots
                        )
                        self.driver.find_element_by_xpath(
                            '//*[@id="captchacharacters"]'
                        ).send_keys(solution + Keys.RETURN)
                except Exception as e:
                    log.debug(e)
                    log.info("Error trying to solve captcha. Refresh and retry.")
                    self.driver.refresh()
        except exceptions.NoSuchElementException:
            log.error("captcha page does not contain captcha element")
            log.error("refreshing")
            self.driver.refresh()

    def save_screenshot(self, page):
        file_name = get_timestamp_filename("screenshots/screenshot-" + page, ".png")
        try:
            self.driver.save_screenshot(file_name)
            return file_name
        except exceptions.TimeoutException:
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

    def page_wait_delay(self):
        if self.random_delay:
            return random.uniform(DEFAULT_PAGE_WAIT_DELAY, DEFAULT_MAX_PAGE_WAIT_DELAY)
        else:
            return DEFAULT_PAGE_WAIT_DELAY

    def send_notification(self, message, page_name, take_screenshot=True):
        if take_screenshot:
            file_name = self.save_screenshot(page_name)
            self.notification_handler.send_notification(message, file_name)
        else:
            self.notification_handler.send_notification(message)


def get_timestamp_filename(name, extension):
    """Utility method to create a filename with a timestamp appended to the root and before
    the provided file extension"""
    now = datetime.now()
    date = now.strftime("%m-%d-%Y_%H_%M_%S")
    if extension.startswith("."):
        return name + "_" + date + extension
    else:
        return name + "_" + date + "." + extension
