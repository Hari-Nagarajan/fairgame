import concurrent
import json
import webbrowser
from concurrent.futures.thread import ThreadPoolExecutor
from datetime import datetime
from time import sleep

import requests
from requests.packages.urllib3.util.retry import Retry
from spinlog import Spinner

from notifications.notifications import NotificationHandler
from utils.http import TimeoutHTTPAdapter
from utils.logger import log

NVIDIA_PRODUCT_API = "https://api.nvidia.partners/edge/product/search?page=1&limit=9&locale=en-us&category=GPU"
NVIDIA_CART_URL = "https://store.nvidia.com/store?Action=AddItemToRequisition&SiteID=nvidia&Locale=en_US&productID={product_id}&quantity=1"
NVIDIA_TOKEN_URL = "https://store.nvidia.com/store/nvidia/SessionToken"
NVIDIA_STOCK_API = "https://api-prod.nvidia.com/direct-sales-shop/DR/products/{locale}/{currency}/{product_id}"
NVIDIA_ADD_TO_CART_API = "https://api-prod.nvidia.com/direct-sales-shop/DR/add-to-cart"

GPU_DISPLAY_NAMES = {
    "2060S": "NVIDIA GEFORCE RTX 2060 SUPER",
    "3080": "NVIDIA GEFORCE RTX 3080",
    "3090": "NVIDIA GEFORCE RTX 3090",
}

CURRENCY_LOCALE_MAP = {
    "en_us": "USD",
    "en_gb": "GBP",
    "de_de": "EUR",
    "fr_fr": "EUR",
    "it_it": "EUR",
    "es_es": "EUR",
    "nl_nl": "EUR",
    "sv_se": "SEK",
    "de_at": "EUR",
    "fr_be": "EUR",
    "da_dk": "DKK",
    "cs_cz": "CZK",
}

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36",
}
CART_SUCCESS_CODES = {201, requests.codes.ok}


class ProductIDChangedException(Exception):
    def __init__(self):
        super().__init__("Product IDS changed. We need to re run.")


PRODUCT_IDS_FILE = "stores/store_data/nvidia_product_ids.json"
PRODUCT_IDS = json.load(open(PRODUCT_IDS_FILE))


class NvidiaBuyer:
    def __init__(self, gpu, locale="en_us", test=False, interval=5):
        self.product_ids = set([])
        self.cli_locale = locale.lower()
        self.locale = self.map_locales()
        self.session = requests.Session()
        self.gpu = gpu
        self.enabled = True
        self.auto_buy_enabled = False
        self.attempt = 0
        self.started_at = datetime.now()
        self.test = test
        self.interval = interval

        self.gpu_long_name = GPU_DISPLAY_NAMES[gpu]

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

        self.get_product_ids()

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

    def get_product_ids(self):
        if isinstance(PRODUCT_IDS[self.cli_locale][self.gpu], list):
            self.product_ids = PRODUCT_IDS[self.cli_locale][self.gpu]
        if isinstance(PRODUCT_IDS[self.cli_locale][self.gpu], str):
            self.product_ids = [PRODUCT_IDS[self.cli_locale][self.gpu]]

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
                    log.debug(f"Future Result: {fut.result()}")
        except ProductIDChangedException as ex:
            log.warning("Product IDs changed.")
            self.product_ids = set([])
            self.get_product_ids()
            self.run_items()

    def buy(self, product_id):
        try:
            log.info(f"Stock Check {product_id} at {self.interval} second intervals.")
            while not self.is_in_stock(product_id):
                self.attempt = self.attempt + 1
                time_delta = str(datetime.now() - self.started_at).split(".")[0]
                with Spinner.get(
                    f"Stock Check ({self.attempt}, have been running for {time_delta})..."
                ) as s:
                    sleep(self.interval)
            if self.enabled:
                cart_success, cart_url = self.get_cart_url(product_id)
                if cart_success:
                    log.info(f"{self.gpu_long_name} added to cart.")
                    self.enabled = False
                    webbrowser.open(cart_url)
                    self.notification_handler.send_notification(
                        f" {self.gpu_long_name} with product ID: {product_id} in "
                        f"stock: {cart_url}"
                    )
                else:
                    self.buy(product_id)
        except requests.exceptions.RequestException as e:
            self.notification_handler.send_notification(
                f"Got an unexpected reply from the server, API may be down, nothing we can do but try again"
            )
            self.buy(product_id)

    def is_in_stock(self, product_id):
        try:
            response = self.session.get(
                NVIDIA_STOCK_API.format(
                    product_id=product_id,
                    locale=self.locale,
                    currency=CURRENCY_LOCALE_MAP.get(self.locale, "USD"),
                ),
                headers=DEFAULT_HEADERS,
            )
            log.debug(f"Stock check response code: {response.status_code}")
            if response.status_code != 200:
                log.debug(response.text)
            if "PRODUCT_INVENTORY_IN_STOCK" in response.text:
                return True
            else:
                return False
        except requests.exceptions.RequestException as e:
            self.notification_handler.send_notification(
                f"Got an unexpected reply from the server, API may be down, nothing we can do but try again"
            )
            return False

    def get_cart_url(self, product_id):
        try:
            success, token = self.get_session_token()
            if not success:
                return False, ""

            data = {"products": [{"productId": product_id, "quantity": 1}]}
            headers = DEFAULT_HEADERS.copy()
            headers["locale"] = self.locale
            headers["nvidia_shop_id"] = token
            headers["Content-Type"] = "application/json"
            response = self.session.post(
                url=NVIDIA_ADD_TO_CART_API, headers=headers, data=json.dumps(data)
            )
            if response.status_code == 203:
                response_json = response.json()
                if "location" in response_json:
                    return True, response_json["location"]
            else:
                log.error(response.text)
                log.error(
                    f"Add to cart failed with {response.status_code}. This is likely an error with nvidia's API."
                )
            return False, ""
        except requests.exceptions.RequestException as e:
            self.notification_handler.send_notification(
                f"Got an unexpected reply from the server, API may be down, nothing we can do but try again"
            )
            return False, ""

    def get_session_token(self):
        params = {"format": "json", "locale": self.locale}
        headers = DEFAULT_HEADERS.copy()
        headers["locale"] = self.locale

        try:
            response = self.session.get(
                NVIDIA_TOKEN_URL, headers=DEFAULT_HEADERS, params=params
            )
            if response.status_code == 200:
                response_json = response.json()
                if "session_token" not in response_json:
                    log.error("Error getting session token.")
                    return False, ""
                return True, response_json["session_token"]
            else:
                log.debug(f"Get Session Token: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.notification_handler.send_notification(
                f"Got an unexpected reply from the server, API may be down, nothing we can do but try again"
            )
            return False
