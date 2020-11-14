import json
import secrets
import time
from os import path
from price_parser import parse_price

from amazoncaptcha import AmazonCaptcha
from chromedriver_py import binary_path  # this will get you the path variable
from furl import furl
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from utils import selenium_utils
from utils.json_utils import InvalidAutoBuyConfigException
from utils.logger import log
from utils.selenium_utils import options, enable_headless, wait_for_element
from price_parser import parse_price

AMAZON_URLS = {
    "BASE_URL": "https://{domain}/",
    "CART_URL": "https://{domain}/gp/aws/cart/add.html",
}
CHECKOUT_URL = "https://{domain}/gp/cart/desktop/go-to-checkout.html/ref=ox_sc_proceed?partialCheckoutCart=1&isToBeGiftWrappedBefore=0&proceedToRetailCheckout=Proceed+to+checkout&proceedToCheckout=1&cartInitiateId={cart_id}"

AUTOBUY_CONFIG_PATH = "amazon_config.json"

SIGN_IN_TITLES = [
    "Amazon Sign In",
    "Amazon Sign-In",
    "Amazon Anmelden",
    "Iniciar sesión en Amazon",
    "Connexion Amazon",
    "Amazon Accedi",
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
]
SHOPING_CART_TITLES = [
    "Amazon.com Shopping Cart",
    "Amazon.ca Shopping Cart",
    "Amazon.co.uk Shopping Basket",
    "Amazon.de Basket",
    "Amazon.de Einkaufswagen",
    "Cesta de compra Amazon.es",
    "Amazon.fr Panier",
    "Carrello Amazon.it",
    "AmazonSmile Shopping Cart",
]
CHECKOUT_TITLES = [
    "Amazon.com Checkout",
    "Amazon.co.uk Checkout",
    "Place Your Order - Amazon.ca Checkout",
    "Place Your Order - Amazon.co.uk Checkout",
    "Amazon.de Checkout",
    "Place Your Order - Amazon.de Checkout",
    "Amazon.de - Bezahlvorgang",
    "Place Your Order - Amazon.com Checkout",
    "Place Your Order - Amazon.com",
    "Tramitar pedido en Amazon.es",
    "Processus de paiement Amazon.com",
    "Confirmar pedido - Compra Amazon.es",
    "Passez votre commande - Processus de paiement Amazon.fr",
    "Ordina - Cassa Amazon.it",
    "AmazonSmile Checkout",
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
]
ADD_TO_CART_TITLES = [
    "Amazon.com: Please Confirm Your Action",
    "Amazon.de: Bitte bestätigen Sie Ihre Aktion",
    "Amazon.de: Please Confirm Your Action",
    "Amazon.es: confirma tu acción",
    "Amazon.com : Veuillez confirmer votre action",  # Careful, required non-breaking space after .com (&nbsp)
    "Amazon.it: confermare l'operazione",
    "AmazonSmile: Please Confirm Your Action",
]
DOGGO_TITLES = [
    "Sorry! Something went wrong!"
]

class Amazon:
    def __init__(self, notification_handler, headless=False):
        self.notification_handler = notification_handler
        if headless:
            enable_headless()
        options.add_argument(f"user-data-dir=.profile-amz")
        try:
            self.driver = webdriver.Chrome(executable_path=binary_path, options=options)
            self.wait = WebDriverWait(self.driver, 10)
        except Exception:
            log.error("Another instance of chrome is running, close that and try again.")
            exit(1)
        if path.exists(AUTOBUY_CONFIG_PATH):
            with open(AUTOBUY_CONFIG_PATH) as json_file:
                try:
                    config = json.load(json_file)
                    self.username = config["username"]
                    self.password = config["password"]
                    self.asin_list = config["asin_list"]
                    self.reserve = float(config["reserve"])
                    self.amazon_website = config.get("amazon_website", "smile.amazon.com")
                    assert isinstance(self.asin_list, list)
                except Exception:
                    log.error(
                        "amazon_config.json file not formatted properly: https://github.com/Hari-Nagarajan/nvidia-bot/wiki/Usage#json-configuration"
                    )
        else:
            log.error(
                "No config file found, see here on how to fix this: https://github.com/Hari-Nagarajan/nvidia-bot/wiki/Usage#json-configuration"
            )
            exit(0)

        for key in AMAZON_URLS.keys():
            AMAZON_URLS[key] = AMAZON_URLS[key].format(domain=self.amazon_website)
        self.driver.get(AMAZON_URLS["BASE_URL"])
        log.info("Waiting for home page.")
        self.check_if_captcha(self.wait_for_pages, HOME_PAGE_TITLES)

        if self.is_logged_in():
            log.info("Already logged in")
        else:
            log.info("Lets log in.")

            is_smile = "smile" in AMAZON_URLS["BASE_URL"]
            xpath = '//*[@id="ge-hello"]/div/span/a' if is_smile else '//*[@id="nav-link-accountList"]/div/span'
            selenium_utils.button_click_using_xpath(
                self.driver,
                xpath
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

        if self.driver.find_elements_by_xpath('//*[@id="auth-error-message-box"]'):
            log.error("Login failed, check your username in amazon_config.json")
            time.sleep(240)
            exit(1)

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
            "Your items on Amazon.com were found!", True
        )
        self.checkout(test=test)

    def something_in_stock(self):
        #params = {"anticache": str(secrets.token_urlsafe(32))}
        params = {}
        for x in range(len(self.asin_list)):
            params[f"ASIN.{x + 1}"] = self.asin_list[x]
            params[f"Quantity.{x + 1}"] = 1

        f = furl(AMAZON_URLS["CART_URL"])
        f.set(params)
        self.driver.get(f.url)
        title = self.driver.title
        #if len(self.asin_list) > 1 and title in DOGGO_TITLES:
        if title in DOGGO_TITLES:
            good_asin_list = []
            for asin in self.asin_list:
                checkparams = {}
                checkparams[f"ASIN.1"] = asin
                checkparams[f"Quantity.1"] = 1
                check = furl(AMAZON_URLS["CART_URL"])
                check.set(checkparams)
                self.driver.get(check.url)
                sanity_check = self.driver.title
                if sanity_check in DOGGO_TITLES:
                    log.error(f"{asin} blocked from bulk adding by Amazon")
                    time.sleep(1)
                else:
                    log.info(f"{asin} appears to allow adding")
                    good_asin_list.append(asin)
            if len(good_asin_list)>0:
                log.info("Revising ASIN list to include only good ASINs listed above")
                self.asin_list = good_asin_list
            else:
                log.error("No ASINs work in list. Try using smile.amazon.com")
                exit(1)
        self.check_if_captcha(self.wait_for_pages, ADD_TO_CART_TITLES)
        price_element = self.driver.find_elements_by_xpath('//td[@class="price item-row"]')
        if price_element:
            str_price = price_element[0].text
            log.info(f'Item Cost: {str_price}')
            price = parse_price(str_price)
            priceFloat = price.amount
            if priceFloat is None:
                log.error("Error reading price information on page.")
                return False
            elif priceFloat <= self.reserve:
                log.info("One or more items in stock and under reserve!")
                return True
            else:
                log.info("No stock available under reserve price")
                #log.info("{}".format(self.asin_list))
                return False
            return False
        else:
            return False
        
    def get_captcha_help(self):
        if not self.on_captcha_page():
            log.info("Not on captcha page.")
            return
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
                time.sleep(5)
                self.get_captcha_help()
            else:
                self.driver.save_screenshot("screenshot.png")
                self.driver.find_element_by_xpath(
                    '//*[@id="captchacharacters"]'
                ).send_keys(solution + Keys.RETURN)
                self.notification_handler.send_notification(
                    f"Solved captcha with solution: {solution}", True
                )
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
                self.driver.save_screenshot(f"amazon-{func.__name__}.png")
                self.driver.save_screenshot("screenshot.png")
                self.notification_handler.send_notification(
                    f"Error on {self.driver.title}", True
                )
                time.sleep(60)
                self.driver.close()
                log.debug(e)
                pass

    def wait_for_pages(self, page_titles, t=30):
        log.debug(f"wait_for_pages({page_titles}, {t})")
        try:
            title = selenium_utils.wait_for_any_title(self.driver, page_titles, t)
            if not title in page_titles:
                log.error(
                    "{} is not a recognized title, report to #tech-support or open an issue on github".format()
                )
            pass
        except Exception as e:
            log.debug(e)
            pass

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
        self.notification_handler.send_notification("Starting Checkout", True)
        self.driver.find_element_by_xpath('//input[@value="add"]').click()

        log.info("Waiting for Cart Page")
        self.check_if_captcha(self.wait_for_pages, SHOPING_CART_TITLES)
        self.driver.save_screenshot("screenshot.png")
        self.notification_handler.send_notification("Cart Page", True)

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
                self.notification_handler.send_notification(
                    "Failed to checkout. Returning to stock check.", True
                )
                log.info("Failed to checkout. Returning to stock check.")
                self.run_item(test=test)

        log.info("Waiting for Place Your Order Page")
        self.wait_for_pyo_page()

        log.info("Finishing checkout")
        self.driver.save_screenshot("screenshot.png")
        self.notification_handler.send_notification("Finishing checkout", True)

        self.finalize_order_button(test)

        log.info("Waiting for Order completed page.")
        self.wait_for_order_completed(test)

        log.info("Order Placed.")
        self.driver.save_screenshot("screenshot.png")
        self.notification_handler.send_notification("Order Placed", True)

        time.sleep(20)
