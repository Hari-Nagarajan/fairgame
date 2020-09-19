import logging
import webbrowser
from datetime import datetime
from time import sleep

import requests
from furl import furl
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

log = logging.getLogger(__name__)
formatter = logging.Formatter(
    "%(asctime)s : %(message)s : %(levelname)s -%(name)s", datefmt="%d%m%Y %I:%M:%S %p"
)
handler = logging.StreamHandler()
handler.setFormatter(formatter)
log.setLevel(10)
log.addHandler(handler)

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

NVIDIA_CART_URL = "https://store.nvidia.com/store/nvidia/en_US/buy/productID.{product_id}/clearCart.yes/nextPage.QuickBuyCartPage"
NVIDIA_TOKEN_URL = "https://store.nvidia.com/store/nvidia/SessionToken"

GPU_DISPLAY_NAMES = {
    "2060S": "NVIDIA GEFORCE RTX 2060 SUPER",
    "3080": "NVIDIA GEFORCE RTX 3080",
    "3090": "NVIDIA GEFORCE RTX 3090",
}

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36",
}


class NvidiaBuyer:
    def __init__(self, locale="en_us"):
        self.product_data = {}
        self.session = requests.Session()

        adapter = HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"],
            )
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.locale = locale
        self.get_product_ids()

    def get_product_ids(self, url=DIGITAL_RIVER_PRODUCT_LIST_URL):
        log.debug(f"Calling {url}")
        payload = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "expand": "product",
            "fields": "product.id,product.displayName,product.pricing",
            "locale": self.locale
        }
        headers = DEFAULT_HEADERS.copy()
        headers['locale'] = self.locale
        response = self.session.get(url, headers=headers, params=payload)

        log.debug(response.status_code)
        response_json = response.json()
        for product_obj in response_json["products"]["product"]:
            if product_obj["displayName"] in GPU_DISPLAY_NAMES.values():
                self.product_data[product_obj["displayName"]] = {
                    "id": product_obj["id"],
                    "price": product_obj["pricing"]["formattedListPrice"],
                }
        if response_json["products"].get("nextPage"):
            self.get_product_ids(url=response_json["products"]["nextPage"]["uri"])

    def buy(self, gpu):
        product_id = self.product_data.get(GPU_DISPLAY_NAMES[gpu])["id"]
        log.info(f"Checking stock for {GPU_DISPLAY_NAMES[gpu]}...")
        while not self.is_in_stock(product_id):
            sleep(5)
        self.add_to_cart_silent(product_id)

    def is_in_stock(self, product_id):
        payload = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "locale": self.locale
        }

        url = DIGITAL_RIVER_STOCK_CHECK_URL.format(product_id=product_id)

        log.debug(f"Calling {url}")
        response = self.session.get(url, headers=DEFAULT_HEADERS, params=payload)
        log.debug(f"Returned {response.status_code}")
        response_json = response.json()
        product_status_message = response_json["inventoryStatus"]["status"]
        log.info(f"Stock status is {product_status_message}")
        return product_status_message != DIGITAL_RIVER_OUT_OF_STOCK_MESSAGE

    def get_nividia_access_token(self):
        log.debug("Getting session token")
        payload = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "format": "json",
            "locale": self.locale,
            "currency": "USD",
            "_": datetime.today(),
        }
        response = self.session.get(
            NVIDIA_TOKEN_URL, headers=DEFAULT_HEADERS, params=payload
        )
        log.debug(response.status_code)
        return response.json()["access_token"]

    def add_to_cart_silent(self, product_id):
        access_token = self.get_nividia_access_token()
        payload = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "format": "json",
            "method": "post",
            "productId": product_id,
            "locale": self.locale,
            "quantity": 1,
            "token": access_token,
            "_": datetime.now(),
        }
        log.debug("Adding to cart")
        response = self.session.get(
            DIGITAL_RIVER_ADD_TO_CART_URL, headers=DEFAULT_HEADERS, params=payload
        )
        log.debug(response.status_code)
        log.debug(self.session.cookies)
        params = {"token": access_token}
        url = furl(DIGITAL_RIVER_CHECKOUT_URL).set(params)
        webbrowser.open_new(url.url)
