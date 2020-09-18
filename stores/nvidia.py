import logging
import webbrowser
from datetime import date

import requests

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

DIGITAL_RIVER_ADD_TO_CART_URL = "https://api.digitalriver.com/v1/shoppers/me/carts/active/line-items"

NVIDIA_CART_URL = "https://store.nvidia.com/store/nvidia/en_US/buy/productID.{product_id}/clearCart.yes/nextPage.QuickBuyCartPage"

NVIDIA_TOKEN_URL = "https://store.nvidia.com/store/nvidia/SessionToken"

GPU_DISPLAY_NAMES = {
    "2060S": "NVIDIA GEFORCE RTX 2060 SUPER",
    "3080": "NVIDIA GEFORCE RTX 3080",
    "3090": "NVIDIA GEFORCE RTX 3090",
}


def add_to_cart(product_id):
    """

    Old nvidia cart link. Broke around 5pm 2020-09-18
    """
    log.info(f"Adding {product_id} to cart!")
    webbrowser.open_new(NVIDIA_CART_URL.format(product_id=product_id))


def get_nividia_access_token():
    payload = {
        "apiKey": DIGITAL_RIVER_API_KEY,
        "format": "json",
        "locale": "en-us",
        "currency": "USD",
        "_": date.today()
    }
    response = requests.get(NVIDIA_TOKEN_URL, headers={"Accept": "application/json"}, params=payload)
    return response.json()['access_token']


def add_to_cart_silent(product_id):
    log.debug("Getting session token")
    access_token = get_nividia_access_token()
    payload = {
        "apiKey": DIGITAL_RIVER_API_KEY,
        "format": "json",
        "method": "post",
        "productId": product_id,
        "quantity": 1,
        "token": access_token,
        "_": date.today()
    }
    log.debug("Adding to cart")
    response = requests.get(DIGITAL_RIVER_ADD_TO_CART_URL, headers={"Accept": "application/json"}, params=payload)
    log.debug(response.status_code)
    webbrowser.open_new(f"https://api.digitalriver.com/v1/shoppers/me/carts/active/web-checkout?token={access_token}")


def is_in_stock(product_id):
    payload = {
        "apiKey": DIGITAL_RIVER_API_KEY,
    }

    url = DIGITAL_RIVER_STOCK_CHECK_URL.format(product_id=product_id)

    log.debug(f"Calling {url}")
    response = requests.get(url, headers={"Accept": "application/json"}, params=payload)
    log.debug(f"Returned {response.status_code}")
    response_json = response.json()
    product_status_message = response_json["inventoryStatus"]["status"]
    log.info(f"Stock status is {product_status_message}")
    return product_status_message != DIGITAL_RIVER_OUT_OF_STOCK_MESSAGE


class NvidiaBuyer:
    def __init__(self):
        self.product_data = {}
        self.get_product_ids()
        print(self.product_data)

    def get_product_ids(self, url=DIGITAL_RIVER_PRODUCT_LIST_URL):
        log.debug(f"Calling {url}")
        payload = {
            "apiKey": DIGITAL_RIVER_API_KEY,
            "expand": "product",
            "fields": "product.id,product.displayName,product.pricing",
        }
        response = requests.get(
            url, headers={"Accept": "application/json"}, params=payload
        )

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
        while not is_in_stock(product_id):
            sleep(5)
        add_to_cart_silent(product_id)
