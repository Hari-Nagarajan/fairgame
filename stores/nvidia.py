import concurrent
import json
import webbrowser
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
from os import path
from time import sleep

import requests
from chromedriver_py import binary_path  # this will get you the path variable
from furl import furl
from requests.exceptions import Timeout
from requests.packages.urllib3.util.retry import Retry
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver import ActionChains
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait
from spinlog import Spinner

from notifications.notifications import NotificationHandler
from utils import selenium_utils
from utils.http import TimeoutHTTPAdapter
from utils.logger import log
from utils.selenium_utils import options, chrome_options

DIGITAL_RIVER_OUT_OF_STOCK_MESSAGE = "PRODUCT_INVENTORY_OUT_OF_STOCK"
DIGITAL_RIVER_API_KEY = "9485fa7b159e42edb08a83bde0d83dia"
DIGITAL_RIVER_PRODUCT_LIST_URL = "https://api.digitalriver.com/v1/shoppers/me/products"
DIGITAL_RIVER_STOCK_CHECK_URL = "https://api.digitalriver.com/v1/shoppers/me/products/{product_id}/inventory-status?"
DIGITAL_RIVER_ADD_TO_CART_URL = (
    "https://api.digitalriver.com/v1/shoppers/me/carts/active/line-items"
)
DIGITAL_RIVER_CHECKOUT_URL = (
    "https://api.digitalriver.com/v1/shoppers/me/carts/active/web-checkout"
)

DIGITAL_RIVER_ADD_TO_CART_API_URL = (
    "https://api.digitalriver.com/v1/shoppers/me/carts/active"
)
DIGITAL_RIVER_APPLY_SHOPPER_DETAILS_API_URL = (
    "https://api.digitalriver.com/v1/shoppers/me/carts/active/apply-shopper"
)
DIGITAL_RIVER_SUBMIT_CART_API_URL = (
    "https://api.digitalriver.com/v1/shoppers/me/carts/active/submit-cart"
)
DIGITAL_RIVER_PAYMENT_METHODS_API_URL = (
    "https://api.digitalriver.com/v1/shoppers/me/payment-options"
)

NVIDIA_CART_URL = "https://store.nvidia.com/store/nvidia/en_US/buy/productID.{product_id}/clearCart.yes/nextPage.QuickBuyCartPage"
NVIDIA_TOKEN_URL = "https://store.nvidia.com/store/nvidia/SessionToken"

GPU_DISPLAY_NAMES = {
    "2060S": "NVIDIA GEFORCE RTX 2060 SUPER",
    "3080": "NVIDIA GEFORCE RTX 3080",
    "3090": "NVIDIA GEFORCE RTX 3090",
}

ACCEPTED_LOCALES = [
    "en_us",
    "en_gb",
    "de_de",
    "fr_fr",
    "it_it",
    "es_es",
    "nl_nl",
    "sv_se",
    "de_at",
    "fr_be",
    "da_dk",
    "cs_cz",
]

PAGE_TITLES_BY_LOCALE = {
    "en_us": {  # Verified
        "signed_in_help": "NVIDIA Online Store - Help",
        "checkout": "NVIDIA Online Store - Checkout",
        "verify_order": "NVIDIA Online Store - Verify Order",
        "address_validation": "NVIDIA Online Store - Address Validation Suggestion Page",
        "order_completed": "NVIDIA Online Store - Order Completed",
    },
    "fr_be": {
        "signed_in_help": "NVIDIA Online Store - Help",
        "checkout": "NVIDIA Online Store - Checkout",
        "verify_order": "NVIDIA Online Store - Verify Order",
        "address_validation": "NVIDIA Online Store - Address Validation Suggestion Page",
        "order_completed": "NVIDIA Online Store - Order Completed",
    },
    "es_es": {
        "signed_in_help": "NVIDIA Tienda electrónica - Ayuda",
        "checkout": "NVIDIA Tienda electrónica - Caja",
        "verify_order": "NVIDIA Tienda electrónica - Verificar pedido",
        "address_validation": "NVIDIA Tienda electrónica - Página de sugerencia para la validación de la dirección",
        "order_completed": "NVIDIA Online Store - Order Completed",
    },
    "fr_fr": {
        "signed_in_help": "NVIDIA Boutique en ligne - Aide",
        "checkout": "NVIDIA Boutique en ligne - panier et informations de facturation",
        "verify_order": "NVIDIA Boutique en ligne - vérification de commande",
        "address_validation": "NVIDIA Boutique en ligne - Page de suggestion et de validation d’adresse",
        "order_completed": "NVIDIA Boutique en ligne - confirmation de commande",
    },
    "it_it": {
        "signed_in_help": "NVIDIA Negozio Online - Guida",
        "checkout": "NVIDIA Negozio Online - Vai alla cassa",
        "verify_order": "NVIDIA Negozio Online - Verifica ordine",
        "address_validation": "NVIDIA Negozio Online - Pagina di suggerimento per la validazione dell'indirizzo",
        "order_completed": "NVIDIA Negozio Online - Ordine completato",
    },
    "nl_nl": {
        "signed_in_help": "NVIDIA Online winkel - Help",
        "checkout": "NVIDIA Online winkel - Kassa",
        "verify_order": "NVIDIA Online winkel - Bestelling controleren",
        "address_validation": "NVIDIA Online winkel - Adres Validatie Suggestie pagina",
        "order_completed": "NVIDIA Online winkel - Bestelling voltooid",
    },
    "sv_se": {
        "signed_in_help": "NVIDIA Online Store - Help",
        "checkout": "NVIDIA Online Store - Checkout",
        "verify_order": "NVIDIA Online Store - Verify Order",
        "address_validation": "NVIDIA Online Store - Address Validation Suggestion Page",
        "order_completed": "NVIDIA Online Store - Order Completed",
    },
    "de_de": {
        "signed_in_help": "NVIDIA Online-Shop - Hilfe",
        "checkout": "NVIDIA Online-Shop - einkaufswagen",
        "verify_order": "NVIDIA Online-Shop - bestellung überprüfen und bestätigen",
        "address_validation": "NVIDIA Online-Shop - Adressüberprüfung Vorschlagsseite",
        "order_completed": "NVIDIA Online Store - Order Completed",
    },
    "de_at": {
        "signed_in_help": "NVIDIA Online-Shop - Hilfe",
        "checkout": "NVIDIA Online-Shop - einkaufswagen",
        "verify_order": "NVIDIA Online-Shop - bestellung überprüfen und bestätigen",
        "address_validation": "NVIDIA Online-Shop - Adressüberprüfung Vorschlagsseite",
        "order_completed": "NVIDIA Online Store - Order Completed",
    },
    "en_gb": {
        "signed_in_help": "NVIDIA Online Store - Help",
        "checkout": "NVIDIA Online Store - Checkout",
        "verify_order": "NVIDIA Online Store - Verify Order",
        "address_validation": "NVIDIA Online Store - Address Validation Suggestion Page",
        "order_completed": "NVIDIA Online Store - Order Completed",
    },
    "da_dk": {
        "signed_in_help": "NVIDIA Online Store - Help",
        "checkout": "NVIDIA Online Store - Checkout",
        "verify_order": "NVIDIA Online Store - Verify Order",
        "address_validation": "NVIDIA Online Store - Address Validation Suggestion Page",
        "order_completed": "NVIDIA Online Store - Order Completed",
    },
    "cs_cz": {
        "signed_in_help": "NVIDIA Online Store - Help",
        "checkout": "NVIDIA Online Store - Checkout",
        "verify_order": "NVIDIA Online Store - Verify Order",
        "address_validation": "NVIDIA Online Store - Address Validation Suggestion Page",
        "order_completed": "NVIDIA Online Store - Order Completed",
    },
}

autobuy_locale_btns = {
    "fr_be": ["continuer", "envoyer"],
    "es_es": ["continuar", "enviar"],
    "fr_fr": ["continuer", "envoyer"],
    "it_it": ["continua", "invia"],
    "nl_nl": ["doorgaan", "indienen"],
    "sv_se": ["continue", "submit"],
    "de_de": ["Weiter", "Senden"],
    "de_at": ["Weiter", "Senden"],
    "en_gb": ["Continue Checkout", "submit"],
    "en_us": ["continue", "submit"],
    "da_dk": ["continue", "submit"],
    "cs_cz": ["continue", "submit"],
}

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36",
}
CART_SUCCESS_CODES = {201, requests.codes.ok}

AUTOBUY_CONFIG_PATH = "autobuy_config.json"
AUTOBUY_CONFIG_KEYS = ["NVIDIA_LOGIN", "NVIDIA_PASSWORD"]


class ProductIDChangedException(Exception):
    def __init__(self):
        super().__init__("Product IDS changed. We need to re run.")


class InvalidAutoBuyConfigException(Exception):
    def __init__(self, provided_json):
        super().__init__(
            f"Check the README and update your `autobuy_config.json` file. Your autobuy config is {json.dumps(provided_json, indent=2)}"
        )


class NvidiaBuyer:
    def __init__(self, gpu, locale="en_us"):
        self.product_ids = set([])
        self.cli_locale = locale.lower()
        self.locale = self.map_locales()
        self.session = requests.Session()
        self.gpu = gpu
        self.enabled = True
        self.auto_buy_enabled = False
        self.attempt = 0
        self.started_at = datetime.now()

        self.gpu_long_name = GPU_DISPLAY_NAMES[gpu]

        if path.exists(AUTOBUY_CONFIG_PATH):
            with open(AUTOBUY_CONFIG_PATH) as json_file:
                try:
                    self.config = json.load(json_file)
                except Exception as e:
                    log.error("Your `autobuy_config.json` file is not valid json.")
                    raise e
                if self.has_valid_creds():
                    self.nvidia_login = self.config["NVIDIA_LOGIN"]
                    self.nvidia_password = self.config["NVIDIA_PASSWORD"]
                    self.auto_buy_enabled = self.config["FULL_AUTOBUY"]
                    self.cvv = self.config.get("CVV")
                else:
                    raise InvalidAutoBuyConfigException(self.config)
        else:
            log.info("No Autobuy creds found.")

        # Disable auto_buy_enabled if the user does not provide a bool.
        if type(self.auto_buy_enabled) != bool:
            self.auto_buy_enabled = False

        adapter = TimeoutHTTPAdapter(
            max_retries=Retry(
                total=10,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"],
            )
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.notification_handler = NotificationHandler()

        log.info("Opening Webdriver")
        self.driver = webdriver.Chrome(
            executable_path=binary_path, options=options, chrome_options=chrome_options
        )
        self.sign_in()
        selenium_utils.add_cookies_to_session_from_driver(self.driver, self.session)
        log.info("Adding driver cookies to session")

        log.info("Getting product IDs")
        self.token_data = self.get_nvidia_access_token()
        self.payment_option = self.get_payment_options()
        if not self.payment_option.get("id") or not self.cvv:
            log.error("No payment option on account or missing CVV. Disable Autobuy")
            self.auto_buy_enabled = False
        else:
            log.debug(self.payment_option)
            self.ext_ip = self.get_ext_ip()

        if not self.auto_buy_enabled:
            log.info("Closing webdriver")
            self.driver.close()

        self.get_product_ids()
        while len(self.product_ids) == 0:
            log.info(
                f"We have no product IDs for {self.gpu_long_name}, retrying until we get a product ID"
            )
            self.get_product_ids()
            sleep(5)

    @property
    def access_token(self):
        if datetime.today().timestamp() >= self.token_data.get('expires_at'):
            log.debug('Access token expired')
            self.token_data = self.get_nvidia_access_token()
        return self.token_data['access_token']

    def has_valid_creds(self):
        if all(item in self.config.keys() for item in AUTOBUY_CONFIG_KEYS):
            return True
        else:
            return False

    def map_locales(self):
        if self.cli_locale == "de_at":
            return "de_de"
        if self.cli_locale == "fr_be":
            return "fr_fr"
        if self.cli_locale == "da_dk":
            return "en_gb"
        if self.cli_locale == "cs_cz":
            return "en_gb"
        return self.cli_locale

    def get_product_ids(self, url=DIGITAL_RIVER_PRODUCT_LIST_URL):
        log.debug(f"Calling {url}")
        payload = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "expand": "product",
            "fields": "product.id,product.displayName,product.pricing",
            "locale": self.locale,
            "format": "json"
        }
        headers = DEFAULT_HEADERS.copy()
        headers["locale"] = self.locale
        response = self.session.get(url, headers=headers, params=payload)

        log.debug(response.status_code)
        response_json = response.json()
        for product_obj in response_json["products"]["product"]:
            if product_obj["displayName"] == self.gpu_long_name:
                if self.check_if_locale_corresponds(product_obj["id"]):
                    self.product_ids.add(product_obj["id"])
        if response_json["products"].get("nextPage"):
            self.get_product_ids(url=response_json["products"]["nextPage"]["uri"])

    def run_items(self):
        log.info(
            f"We have {len(self.product_ids)} product IDs for {self.gpu_long_name}"
        )
        log.info(f"Product IDs: {self.product_ids}")
        try:
            with ThreadPoolExecutor(max_workers=len(self.product_ids)) as executor:
                product_futures = [
                    executor.submit(self.buy, product_id)
                    for product_id in self.product_ids
                ]
                concurrent.futures.wait(product_futures)
                for fut in product_futures:
                    log.info(fut.result())
        except ProductIDChangedException as ex:
            log.warning("Product IDs changed.")
            self.product_ids = set([])
            self.get_product_ids()
            self.run_items()

    def buy(self, product_id, delay=5):
        try:
            log.info(f"Checking stock for {product_id} at {delay} second intervals.")
            while not self.add_to_cart(product_id) and self.enabled:
                self.attempt = self.attempt + 1
                time_delta = str(datetime.now() - self.started_at).split(".")[0]
                with Spinner.get(
                    f"Still working (attempt {self.attempt}, have been running for {time_delta})..."
                ) as s:
                    sleep(delay)
            if self.enabled:
                self.apply_shopper_details()
                if self.auto_buy_enabled:
                    self.notification_handler.send_notification(
                        f" {self.gpu_long_name} with product ID: {product_id} available!"
                    )
                    log.info("Auto buy enabled.")
                    # self.submit_cart()
                    self.selenium_checkout()
                else:
                    log.info("Auto buy disabled.")
                    cart_url = self.open_cart_url()
                    self.notification_handler.send_notification(
                        f" {self.gpu_long_name} with product ID: {product_id} in stock: {cart_url}"
                    )
                self.enabled = False
        except Timeout:
            log.error("Had a timeout error.")
            self.buy(product_id)

    def open_cart_url(self):
        log.info("Opening cart.")
        params = {"token": self.access_token}
        url = furl(DIGITAL_RIVER_CHECKOUT_URL).set(params)
        webbrowser.open_new_tab(url.url)
        return url.url

    def selenium_checkout(self):
        log.info("Checking out.")
        autobuy_btns = autobuy_locale_btns[self.locale]
        params = {"token": self.access_token}
        url = furl(DIGITAL_RIVER_CHECKOUT_URL).set(params)
        self.driver.get(url.url)
        log.debug(
            f"Waiting for page title: {PAGE_TITLES_BY_LOCALE[self.locale]['checkout']}"
        )
        selenium_utils.wait_for_page(
            self.driver, PAGE_TITLES_BY_LOCALE[self.locale]["checkout"]
        )

        log.info("Next.")
        log.debug(f"Clicking on button: {autobuy_btns[0]}")
        self.driver.find_element_by_xpath(f'//*[@value="{autobuy_btns[0]}"]').click()
        log.debug(f"Entering security code to 'cardSecurityCode'")
        security_code = selenium_utils.wait_for_element(self.driver, "cardSecurityCode")
        security_code.send_keys(self.cvv)
        log.info("Next.")
        log.debug(f"Clicking on button: {autobuy_btns[0]}")
        self.driver.find_element_by_xpath(f'//*[@value="{autobuy_btns[0]}"]').click()

        try:
            log.debug(
                f"Waiting for page title: {PAGE_TITLES_BY_LOCALE[self.locale]['verify_order']}"
            )
            selenium_utils.wait_for_page(
                self.driver, PAGE_TITLES_BY_LOCALE[self.locale]["verify_order"], 5
            )
        except TimeoutException:
            log.debug("Address validation required?")
            self.address_validation_page()

        log.debug(
            f"Waiting for page title: {PAGE_TITLES_BY_LOCALE[self.locale]['verify_order']}"
        )
        selenium_utils.wait_for_page(
            self.driver, PAGE_TITLES_BY_LOCALE[self.locale]["verify_order"], 5
        )

        log.info("F this captcha lmao. Submitting cart.")
        self.submit_cart()
        # log.info("Submit.")
        # log.debug("Reached order validation page.")
        # self.driver.save_screenshot("nvidia-order-validation.png")
        # self.driver.find_element_by_xpath(f'//*[@value="{autobuy_btns[1]}"]').click()
        # selenium_utils.wait_for_page(
        #     self.driver, PAGE_TITLES_BY_LOCALE[self.locale]["order_completed"], 5
        # )
        # self.driver.save_screenshot("nvidia-order-finshed.png")
        # log.info("Done.")

    def address_validation_page(self):
        try:
            selenium_utils.wait_for_page(
                self.driver,
                PAGE_TITLES_BY_LOCALE[self.locale]["address_validation"],
                5,
            )
            log.debug("Setting suggested shipping information.")
            selenium_utils.wait_for_element(
                self.driver, "billingAddressOptionRow2"
            ).click()
            selenium_utils.button_click_using_xpath(
                self.driver, "//input[@id='selectionButton']"
            )
        except TimeoutException:
            log.error("Address validation not required?")

    def add_to_cart(self, product_id):
        try:
            log.debug(f"Checking if item ({product_id}) in stock")
            params = {
                "apiKey": DIGITAL_RIVER_API_KEY,
                "token": self.access_token,
                "productId": product_id,
                "format": "json",
            }
            response = self.session.post(
                DIGITAL_RIVER_ADD_TO_CART_API_URL,
                headers=DEFAULT_HEADERS,
                params=params,
            )

            if response.status_code == 200:
                log.info(f"{self.gpu_long_name} ({product_id}) in stock!")
                return True
            elif response.status_code == 409:
                try:
                    response_json = response.json()
                    log.debug(f"Error: {response_json['errors']['error']}")
                    for error in response_json["errors"]["error"]:
                        if error["code"] == "invalid-product-id":
                            raise ProductIDChangedException()
                except json.decoder.JSONDecodeError as er:
                    log.warning(f"Failed to decode json: {response.text}")
            else:
                log.debug("item not in stock")
                return False
        except Exception as ex:
            log.warning(str(ex))
            log.warning("The connection has been reset.")
            return False

    def get_ext_ip(self):
        response = self.session.get("https://api.ipify.org?format=json")
        if response.status_code == 200:
            return response.json()["ip"]

    def get_payment_options(self):
        params = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "token": self.access_token,
            "format": "json",
            "expand": "all",
        }
        response = self.session.get(
            DIGITAL_RIVER_PAYMENT_METHODS_API_URL,
            headers=DEFAULT_HEADERS,
            params=params,
        )
        log.debug(response.status_code)
        log.debug(response.json())
        if response.status_code == 200:
            response_json = response.json()
            try:
                return response_json["paymentOptions"]["paymentOption"][0]
            except:
                return {}

    def apply_shopper_details(self):
        log.info("Apply shopper details")
        params = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "token": self.access_token,
            "billingAddressId": "",
            "paymentOptionId": self.payment_option.get("id", ""),
            "shippingAddressId": "",
            "expand": "all",
        }
        response = self.session.post(
            DIGITAL_RIVER_APPLY_SHOPPER_DETAILS_API_URL,
            headers=DEFAULT_HEADERS,
            params=params,
        )
        log.debug(f"Apply shopper details response: {response.status_code}")
        if response.status_code == 200:
            log.info("Success apply_shopper_details")
        else:
            log.info("Error applying shopper details")
            log.debug(json.dumps(response.json(), indent=1))

    def submit_cart(self):
        params = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "token": self.access_token,
            "format": "json",
            "expand": "all",
        }

        body = {"cart": {"ipAddress": self.ext_ip, "termsOfSalesAcceptance": "true"}}
        response = self.session.post(
            DIGITAL_RIVER_SUBMIT_CART_API_URL,
            headers=DEFAULT_HEADERS,
            params=params,
            json=body,
        )
        log.debug(response.status_code)
        log.debug(response.json())
        if response.status_code == 200:
            log.info("Success submit_cart")

    def check_if_locale_corresponds(self, product_id):
        special_locales = [
            "en_gb",
            "de_at",
            "de_de",
            "fr_fr",
            "fr_be",
            "da_dk",
            "cs_cz",
        ]
        if self.cli_locale in special_locales:
            url = f"{DIGITAL_RIVER_PRODUCT_LIST_URL}/{product_id}"
            log.debug(f"Calling {url}")
            payload = {
                "apiKey": DIGITAL_RIVER_API_KEY,
                "expand": "product",
                "locale": self.locale,
                "format": "json",
            }

            response = self.session.get(url, headers=DEFAULT_HEADERS, params=payload)
            log.debug(response.status_code)
            response_json = response.json()
            return self.cli_locale[3:].upper() in response_json["product"]["name"]
        return True

    def get_nvidia_access_token(self):
        log.debug("Getting session token")
        now = datetime.today()
        payload = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "format": "json",
            "locale": self.locale,
            "currency": "USD",
            "_": now,
        }
        response = self.session.get(
            NVIDIA_TOKEN_URL, headers=DEFAULT_HEADERS, params=payload
        )
        log.debug(response.status_code)
        data = response.json()
        log.debug(f"Nvidia access token: {data['access_token']}")
        data['expires_at'] = round(now.timestamp() + data['expires_in']) - 60
        return data

    def is_signed_in(self):
        try:
            self.driver.find_element_by_id("dr_logout")
            log.info("Already signed in.")
            return True
        except NoSuchElementException:
            return False

    def sign_in(self):
        log.info("Signing in.")
        self.driver.get(
            f"https://store.nvidia.com/DRHM/store?Action=Logout&SiteID=nvidia&Locale={self.locale}&ThemeID=326200&Env=BASE&nextAction=help"
        )
        selenium_utils.wait_for_page(
            self.driver, PAGE_TITLES_BY_LOCALE[self.locale]["signed_in_help"]
        )

        if not self.is_signed_in():
            email = selenium_utils.wait_for_element(self.driver, "loginEmail")
            pwd = selenium_utils.wait_for_element(self.driver, "loginPassword")
            try:
                email.send_keys(self.nvidia_login)
                pwd.send_keys(self.nvidia_password)
            except AttributeError as e:
                log.error("Missing 'nvidia_login' or 'nvidia_password'")
                raise e
            try:
                action = ActionChains(self.driver)
                button = self.driver.find_element_by_xpath(
                    '//*[@id="dr_siteButtons"]/input'
                )

                action.move_to_element(button).click().perform()
                WebDriverWait(self.driver, 5).until(ec.staleness_of(button))
            except NoSuchElementException:
                log.error("Error signing in.")
