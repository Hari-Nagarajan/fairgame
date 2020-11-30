import json
import webbrowser
import time
import os
from datetime import datetime
from time import sleep

from chromedriver_py import binary_path  # this will get you the path variable
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

try:
    from Crypto.PublicKey import RSA
    from Crypto.Cipher import PKCS1_OAEP
except:
    from Cryptodome.PublicKey import RSA
    from Cryptodome.Cipher import PKCS1_OAEP

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from utils.json_utils import find_values
from utils.logger import log
from utils.selenium_utils import enable_headless

BEST_BUY_PDP_URL = "https://api.bestbuy.com/click/5592e2b895800000/{sku}/pdp"
BEST_BUY_CART_URL = "https://api.bestbuy.com/click/5592e2b895800000/{sku}/cart"

BEST_BUY_ADD_TO_CART_API_URL = "https://www.bestbuy.com/cart/api/v1/addToCart"
BEST_BUY_CHECKOUT_URL = "https://www.bestbuy.com/checkout/c/orders/{order_id}/"

DEFAULT_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36",
    "origin": "https://www.bestbuy.com",
}

options = Options()
options.page_load_strategy = "eager"
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
prefs = {"profile.managed_default_content_settings.images": 2,"profile.default_content_setting_values.media_stream_mic": 2,"profile.default_content_setting_values.media_stream_camera": 2} #Disable camera and mic by default.
options.add_experimental_option("prefs", prefs)
options.add_argument("user-data-dir=.profile-bb")
AUTOBUY_CONFIG_PATH = "bestbuy_config.json"


class BestBuyHandler:
    def __init__(self, notification_handler, headless=False):
        self.notification_handler = notification_handler
        self.session = requests.Session()
        self.auto_buy = False #not working, is currently disabled.
        self.sku_list = []
        self.reserve = []
        self.account = {"username": "", "password": ""}
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS", "POST"],
            )
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        if os.path.exists(AUTOBUY_CONFIG_PATH):
            with open(AUTOBUY_CONFIG_PATH) as json_file:
                try:
                    config = json.load(json_file)
                    self.account["username"] = config["username"]
                    self.account["password"] = config["password"]
                    self.sku_groups = int(config["sku_groups"])
                    for x in range(self.sku_groups):
                        self.sku_list.append(config[f"sku_list_{x + 1}"])
                        self.reserve.append(float(config[f"reserve_{x + 1}"]))
                except Exception as e:
                    print(e)
                    log.error(
                        "bestbuy_config.json file not formatted properly: https://github.com/Hari-Nagarajan/nvidia-bot/wiki/Usage#json-configuration"
                    )
                    exit(0)
        else:
            log.error(
                "No bestbuy_config.json file found, see here on how to fix this: https://github.com/Hari-Nagarajan/nvidia-bot/wiki/Usage#json-configuration"
            )
            exit(0)
        try:
            self.driver = webdriver.Chrome(executable_path=binary_path, options=options)
            self.wait = WebDriverWait(self.driver, 10)
        except Exception as e:
            log.error(e)
            exit(1)
        self.driver.get("https://www.bestbuy.com/")
        log.info("Loading home page.")
        
        if self.is_logged_in():
            log.info("Already logged in")
        else:
            log.info("Lets log in.")
            self.login()
            log.info("Waiting 6- seconds for SMS 2FA verification if requested.")
            time.sleep(
                60
            )  # We can remove this once I get more info on the phone verification page.
        self.save_screenshot("start-up")
        self.driver.close() #Close the window, but leave the session running. When autobuying it will popup the add cart window.
        #Test all the SKUs for validity.
        for i in range(len(self.sku_list)):
            for skuid in self.sku_list[i]:
                response = self.session.get(
                    BEST_BUY_PDP_URL.format(sku=skuid), headers=DEFAULT_HEADERS
                )
                log.info(f"PDP Request: {response.status_code}")
                self.product_url = response.url
                log.info(f"Product URL: {self.product_url}")

                self.session.get(self.product_url)
                log.info(f"Product URL Request: {response.status_code}")
                

    def is_logged_in(self):
        try:
            text = self.driver.find_element_by_xpath("/html/body/div[2]/div/div/div/header/div[2]/div[2]/div/nav[2]/ul/li[1]/button/div[2]/span").text
            print(text)
            return "Account" != text
        except Exception as e:
            print (repr(e))
            return False

    def login(self):
        self.driver.get("https://www.bestbuy.com/identity/global/signin")
        try:
            self.driver.find_element_by_xpath('//*[@id="fld-e"]').send_keys(
                self.account["username"]
            )
            self.driver.find_element_by_xpath('//*[@id="fld-p1"]').send_keys(
                self.account["password"]
            )
            self.driver.find_element_by_xpath(
                '//*[@id="ca-remember-me"]'
            ).click()
            self.driver.find_element_by_xpath(
                "/html/body/div[1]/div/section/main/div[1]/div/div/div/div/form/div[4]/button"
            ).click()
        except:
            pass
        WebDriverWait(self.driver, 10).until(
            lambda x: "Official Online Store" in self.driver.title
        )
            
    def run_item(self, delay=3, test=False):
        log.info("Checking stock for items.")
        checkout_success = False
        while not checkout_success:
            pop_list = []
            for i in range(len(self.sku_list)):
                for sku in self.sku_list[i]:
                    checkout_success = self.in_stock(sku, self.reserve[i]) #reserve is not used yet.
                    if checkout_success:
                        log.info(f"attempting to buy {sku}")
                        if self.auto_buy:
                            self.auto_checkout(sku)
                        else:
                            cart_url = self.add_to_cart(sku)
                            self.notification_handler.send_notification(
                                f"SKU: {sku} in stock: {cart_url}"
                            )
                            time.sleep(delay)
                    time.sleep(delay)
            if pop_list:
                for sku in pop_list:
                    for i in range(len(self.sku_list)):
                        if sku in self.sku_list[i]:
                            self.sku_list.pop(i)
                            self.reserve.pop(i)
                            break
            if self.sku_list:  # keep bot going if additional ASINs left
                checkout_success = False

    def in_stock(self,skuid,reserve):
        log.info("Checking stock")
        url = "https://www.bestbuy.com/api/tcfb/model.json?paths=%5B%5B%22shop%22%2C%22scds%22%2C%22v2%22%2C%22page%22%2C%22tenants%22%2C%22bbypres%22%2C%22pages%22%2C%22globalnavigationv5sv%22%2C%22header%22%5D%2C%5B%22shop%22%2C%22buttonstate%22%2C%22v5%22%2C%22item%22%2C%22skus%22%2C{}%2C%22conditions%22%2C%22NONE%22%2C%22destinationZipCode%22%2C%22%2520%22%2C%22storeId%22%2C%22%2520%22%2C%22context%22%2C%22cyp%22%2C%22addAll%22%2C%22false%22%5D%5D&method=get".format(
            skuid
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
            if item_json[0][0]["skuId"] == skuid and item_state in [
                "ADD_TO_CART",
                "PRE_ORDER",
            ]:
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

    def add_to_cart(self,skuid):
        webbrowser.open_new(BEST_BUY_CART_URL.format(sku=skuid))
        return BEST_BUY_CART_URL.format(sku=skuid)

    def auto_checkout(self,skuid):
        self.auto_add_to_cart(skuid)
        self.start_checkout()
        self.driver.get("https://www.bestbuy.com/checkout/c/r/fast-track")

    def auto_add_to_cart(self,skuid):
        log.info("Attempting to auto add to cart...")

        body = {"items": [{"skuId": skuid}]}
        headers = {
            "Accept": "application/json",
            "authority": "www.bestbuy.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36",
            "Content-Type": "application/json; charset=UTF-8",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "origin": "https://www.bestbuy.com",
            "referer": self.product_url,
            "Content-Length": str(len(json.dumps(body))),
        }
        # [
        #     log.info({'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path})
        #     for c in self.session.cookies
        # ]
        log.info("Making request")
        response = self.session.post(
            BEST_BUY_ADD_TO_CART_API_URL, json=body, headers=headers, timeout=5
        )
        log.info(response.status_code)
        if (
            response.status_code == 200
            and response.json()["cartCount"] > 0
            and skuid in response.text
        ):
            log.info(f"Added {skuid} to cart!")
            log.info(response.json())
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
        }
        while True:
            log.info("Starting Checkout")
            response = self.session.post(
                "https://www.bestbuy.com/cart/d/checkout", headers=headers, timeout=5
            )
            if response.status_code == 200:
                response_json = response.json()
                log.info(response_json)
                self.order_id = response_json["updateData"]["order"]["id"]
                self.item_id = response_json["updateData"]["order"]["lineItems"][0][
                    "id"
                ]
                log.info(f"Started Checkout for order id: {self.order_id}")
                log.info(response_json)
                if response_json["updateData"]["redirectUrl"]:
                    self.session.get(
                        response_json["updateData"]["redirectUrl"], headers=headers
                    )
                return
            log.info("Error Starting Checkout")
            sleep(5)

    def submit_shipping(self):
        log.info("Starting Checkout")
        headers = {
            "accept": "application/json, text/javascript, */*; q=0.01",
            "accept-encoding": "gzip, deflate, br",
            "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "content-type": "application/json",
            "origin": "https://www.bestbuy.com",
            "referer": "https://www.bestbuy.com/cart",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.92 Safari/537.36",
            "x-user-interface": "DotCom-Optimized",
            "x-order-id": self.order_id,
        }
        while True:
            log.info("Submitting Shipping")
            body = {"selected": "SHIPPING"}
            response = self.session.put(
                "https://www.bestbuy.com/cart/item/{item_id}/fulfillment".format(
                    item_id=self.item_id
                ),
                headers=headers,
                json=body,
            )
            response_json = response.json()
            log.info(response.status_code)
            log.info(response_json)
            if (
                response.status_code == 200
                and response_json["order"]["id"] == self.order_id
            ):
                log.info("Submitted Shipping")
                return True
            else:
                log.info("Error Submitting Shipping")

    def submit_payment(self, tas_data):
        body = {
            "items": [
                {
                    "id": self.item_id,
                    "type": "DEFAULT",
                    "selectedFulfillment": {"shipping": {"address": {}}},
                    "giftMessageSelected": False,
                }
            ]
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
        }
        r = self.session.patch(
            "https://www.bestbuy.com/checkout/d/orders/{}/".format(self.order_id),
            json=body,
            headers=headers,
        )
        [
            log.info(
                {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
            )
            for c in self.session.cookies
        ]
        log.info(r.status_code)
        log.info(r.text)
        
    def save_screenshot(self, page):
        file_name = get_timestamp_filename("bestbuy-screenshot-" + page, ".png")

        if self.driver.save_screenshot(file_name):
            try:
                self.notification_handler.send_notification(page, file_name)
            except TimeoutException:
                log.info("Timed out taking screenshot, trying to continue anyway")
                pass
            except Exception as e:
                log.error(f"Trying to recover from error: {e}")
                pass
        else:
            log.error("Error taking screenshot due to File I/O error")

    def save_page_source(self, page):
        """Saves DOM at the current state when called.  This includes state changes from DOM manipulation via JS"""
        file_name = get_timestamp_filename("bestbuy-" + page + "_source", "html")

        page_source = self.driver.page_source
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(page_source)
            
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

def get_timestamp_filename(name, extension):
    """Utility method to create a filename with a timestamp appended to the root and before
    the provided file extension"""
    now = datetime.now()
    date = now.strftime("%m-%d-%Y_%H_%M_%S")
    if extension.startswith("."):
        return name + "_" + date + extension
    else:
        return name + "_" + date + "." + extension