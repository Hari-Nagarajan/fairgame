import json
import webbrowser
from time import sleep

try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_OAEP
except:
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Cipher import PKCS1_OAEP
from base64 import b64encode

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from notifications.notifications import NotificationHandler
from utils.json_utils import find_values
from utils.logger import log

BEST_BUY_PDP_URL = "https://api.bestbuy.com/click/5592e2b895800000/{sku}/pdp"
BEST_BUY_CART_URL = "https://api.bestbuy.com/click/5592e2b895800000/{sku}/cart"

BEST_BUY_ADD_TO_CART_API_URL = "https://www.bestbuy.com/cart/api/v1/addToCart"
BEST_BUY_CHECKOUT_URL = "https://www.bestbuy.com/checkout/c/orders/{order_id}/"

DEFAULT_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.92 Safari/537.36",
}

cookie = ""  # Been manually adding the cookie string for testing.


class BestBuyHandler:
    def __init__(self, sku_id):
        self.notification_handler = NotificationHandler()
        self.sku_id = sku_id
        self.session = requests.Session()
        self.auto_buy = False

        adapter = HTTPAdapter(
            max_retries=Retry(
                total=10,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS", "POST"],
            )
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        response = self.session.get(
            BEST_BUY_PDP_URL.format(sku=self.sku_id), headers=DEFAULT_HEADERS
        )
        log.info(response.status_code)
        self.product_url = response.url
        self.session.get(self.product_url)
        log.info(response.status_code)

    def run_item(self):
        while not self.in_stock():
            sleep(5)
        log.info(f"Item {self.sku_id} is in stock!")
        if self.auto_buy:
            self.auto_checkout()
        else:
            cart_url = self.add_to_cart()
            self.notification_handler.send_notification(
                f"SKU: {self.sku_id} in stock: {cart_url}"
            )

    def in_stock(self):
        log.info("Checking stock")
        url = "https://www.bestbuy.com/api/tcfb/model.json?paths=%5B%5B%22shop%22%2C%22scds%22%2C%22v2%22%2C%22page%22%2C%22tenants%22%2C%22bbypres%22%2C%22pages%22%2C%22globalnavigationv5sv%22%2C%22header%22%5D%2C%5B%22shop%22%2C%22buttonstate%22%2C%22v5%22%2C%22item%22%2C%22skus%22%2C{}%2C%22conditions%22%2C%22NONE%22%2C%22destinationZipCode%22%2C%22%2520%22%2C%22storeId%22%2C%22%2520%22%2C%22context%22%2C%22cyp%22%2C%22addAll%22%2C%22false%22%5D%5D&method=get".format(
            self.sku_id
        )
        response = self.session.get(url, headers=DEFAULT_HEADERS)
        log.info(f"Stock check response code: {response.status_code}")
        try:
            response_json = response.json()
            item_json = find_values(
                json.dumps(response_json), "buttonStateResponseInfos"
            )
            item_state = item_json[0][0]["buttonState"]
            log.info(f"Item state is: {item_state}")
            if item_json[0][0]["skuId"] == self.sku_id and item_state == "ADD_TO_CART":
                return True
            else:
                return False
        except Exception as e:
            log.warning("Error parsing json. Using string search to determine state.")
            log.info(response_json)
            log.error(e)
            if "ADD_TO_CART" in response.text:
                log.info("Item is in stock!")
                return True
            else:
                log.info("Item is out of stock")
                return False

    def add_to_cart(self):
        webbrowser.open_new(BEST_BUY_CART_URL.format(sku=self.sku_id))
        return BEST_BUY_CART_URL.format(sku=self.sku_id)

    def auto_checkout(self):
        tas_data = self.get_tas_data()
        self.auto_add_to_cart()
        self.start_checkout()
        self.submit_shipping()
        webbrowser.open_new("https://www.bestbuy.com/checkout/r/payment")
        # self.submit_payment(tas_data)

    def auto_add_to_cart(self):
        log.info("Attempting to auto add to cart...")
        headers = {
            "accept": "application/json",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "content-type": "application/json; charset=UTF-8",
            "origin": "https://www.bestbuy.com",
            "referer": self.product_url,
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.92 Safari/537.36",
            "cookie": cookie,
        }
        body = {"items": [{"skuId": self.sku_id}]}

        log.info("Making request")
        response = self.session.post(
            BEST_BUY_ADD_TO_CART_API_URL, json=body, headers=headers, timeout=5
        )
        log.info(response.status_code)
        if (
                response.status_code == 200
                and response.json()["cartCount"] > 0
                and self.sku_id in response.text
        ):
            log.info(f"Added {self.sku_id} to cart!")
        else:
            log.info(response.status_code)
            log.info(response.json())

    def start_checkout(self):
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.92 Safari/537.36",
            "cookie": cookie,
        }
        while True:
            log.info("Starting Checkout")
            response = self.session.post(
                "https://www.bestbuy.com/cart/d/checkout", headers=headers, timeout=5
            )
            if response.status_code == 200:
                response_json = response.json()
                log.info(response_json)
                self.order_id = response_json["updateData"]['order']['id']
                self.item_id = response_json['updateData']["order"]['lineItems'][0]["id"]
                log.info("Started Checkout")
                return
            log.info("Error Starting Checkout")
            sleep(5)

    def submit_shipping(self):
        log.info("Starting Checkout")
        headers = {
            "accept": "application/com.bestbuy.order+json",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "content-type": "application/json",
            "origin": "https://www.bestbuy.com",
            "referer": "https://www.bestbuy.com/checkout/r/fulfillment",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.92 Safari/537.36",
            "x-user-interface": "DotCom-Optimized",
            "cookie": cookie
        }
        while True:
            log.info("Submitting Shipping")
            body = {"phoneNumber": "", "smsNotifyNumber": ""}
            response = self.session.patch(
                "https://www.bestbuy.com/checkout/orders/{order_id}/".format(order_id=self.order_id),
                headers=headers,
                json=body,
            )
            response_json = response.json()
            if response.status_code == 200 and response_json["id"] == self.order_id:
                order_state = response_json["state"]
                log.info(f"Order State: {order_state}")
                log.info("Submitted Shipping")
                return True
            else:
                log.info(response.text)
                log.info("Error Submitting Shipping")

    def submit_payment(self, tas_data):
        card = {  # https://developers.bluesnap.com/docs/test-credit-cards
            'card_number': "4263982640269299",
            'card_month': '04',
            'card_year': '2023',
            'cvv': '738'
        }
        key = RSA.importKey(tas_data["publicKey"])
        cipher = PKCS1_OAEP.new(key)
        encrypted_card = b64encode(cipher.encrypt(("00926999" + card['card_number']).encode("utf-8"))).decode("utf-8")
        zero_string = ""
        for i in range(len(card['card_number']) - 10):
            zero_string += "0"
        self.bin_number = card['card_number'][:6]
        encrypted_card += ":3:" + tas_data["keyId"] + ":" + self.bin_number + zero_string + card['card_number'][-4:]

        body = {
            "billingAddress": {
                "country": "US",
                "useAddressAsBilling": True,
                "middleInitial": "",
                "lastName": "",
                "isWishListAddress": False,
                "city": "",
                "state": "",
                "firstName": "",
                "addressLine1": "",
                "addressLine2": "",
                "dayPhone": "",
                "postalCode": "",
                "userOverridden": False,
            },
            "creditCard": {
                "hasCID": False,
                "isNewCard": False,
                "invalidCard": False,
                "number": encrypted_card,
                "binNumber": self.bin_number,
                "isVisaCheckout": False,
                "isCustomerCard": False,
                "isPWPRegistered": False,
                "saveToProfile": False,
                "cid": card["cvv"],
                "type": "VISA",
                "virtualCard": False,
                "expiration": {"month": card["card_month"], "year": card["card_year"]},
            },
        }
        headers = {
            "accept": "application/com.bestbuy.order+json",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "content-type": "application/json",
            "origin": "https://www.bestbuy.com",
            "referer": "https://www.bestbuy.com/checkout/r/fulfillment",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.92 Safari/537.36",
            "x-user-interface": "DotCom-Optimized",
            "cookie": cookie
        }
        r = self.session.patch("https://www.bestbuy.com/checkout/orders/{}/paymentMethods".format(self.order_id),
                               json=body, headers=headers)

        log.info(r.status_code)
        log.info(r.text)

    def get_tas_data(self):
        headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "content-type": "application/json",
            "referer": "https://www.bestbuy.com/checkout/r/payment",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.92 Safari/537.36",
        }
        while True:
            try:
                log.info("Getting TAS Data")
                r = requests.get(
                    "https://www.bestbuy.com/api/csiservice/v2/key/tas", headers=headers
                )
                log.info("Got TAS Data")
                return json.loads(r.text)
            except Exception as e:
                sleep(5)
