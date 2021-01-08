import fileinput
import http.client
import json
import os
import pathlib
import random
import time
import typing
from decimal import Decimal

import attr
import psutil
import requests
from amazoncaptcha import AmazonCaptcha
from chromedriver_py import binary_path
from furl import furl
from hyper import HTTP20Connection
from lxml import html
from price_parser import parse_price, Price
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait

from notifications.notifications import NotificationHandler
from stores.basestore import BaseStoreHandler
from utils.logger import log
from utils.selenium_utils import enable_headless, options

# PDP_URL = "https://smile.amazon.com/gp/product/"
# AMAZON_DOMAIN = "www.amazon.com.au"
# AMAZON_DOMAIN = "www.amazon.com.br"
AMAZON_DOMAIN = "www.amazon.ca"
# NOT SUPPORTED AMAZON_DOMAIN = "www.amazon.cn"
# AMAZON_DOMAIN = "www.amazon.fr"
# AMAZON_DOMAIN = "www.amazon.de"
# NOT SUPPORTED AMAZON_DOMAIN = "www.amazon.in"
# AMAZON_DOMAIN = "www.amazon.it"
# AMAZON_DOMAIN = "www.amazon.co.jp"
# AMAZON_DOMAIN = "www.amazon.com.mx"
# AMAZON_DOMAIN = "www.amazon.nl"
# AMAZON_DOMAIN = "www.amazon.es"
# AMAZON_DOMAIN = "www.amazon.co.uk"
# AMAZON_DOMAIN = "www.amazon.com"
# AMAZON_DOMAIN = "www.amazon.se"

PDP_PATH = f"/dp/"
# REALTIME_INVENTORY_URL = f"{AMAZON_DOMAIN}gp/aod/ajax/ref=aod_f_new?asin="
REALTIME_INVENTORY_PATH = f"/gp/aod/ajax/ref=aod_f_new?isonlyrenderofferlist=true&asin="
# REALTIME_INVENTORY_URL = "https://www.amazon.com/gp/aod/ajax/ref=dp_aod_NEW_mbc?asin="
CONFIG_FILE_PATH = "config/amazon_ajax_config.json"
STORE_NAME = "Amazon"
FREE_SHIPPING_PRICE = parse_price("0.00")

CONDITION_NEW = 1
CONDITION_USED = 10
CONDITION_COLLECTIBLE = 20
CONDITION_UNKNOWN = 100

# Request
# HEADERS = {
#     "authority": "www.amazon.ca",
#     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
#     "Accept-Encoding": "gzip, deflate, sdch, br",
#     "Accept-Language": "en-US,en;q=0.8",
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
# }
HEADERS = {
    "cache-control": "max-age=0",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.101 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "service-worker-navigation-preload": "true",
    "sec-gpc": "1",
    "sec-fetch-site": "none",
    "sec-fetch-mode": "navigate",
    "sec-fetch-user": "?1",
    "sec-fetch-dest": "document",
    "accept-language": "en-US,en;q=0.9",
}


@attr.s(auto_attribs=True)
class SellerDetail:
    name: str
    price: Price
    shipping_cost: Price
    condition: int = CONDITION_NEW
    atc_url: str = None
    offering_id: str = None
    xpath = f"//form[@action='{atc_url}'//input[@name='submit.addToCart']"

    @property
    def selling_price(self) -> Decimal:
        return self.price.amount + self.shipping_cost.amount


@attr.s(auto_attribs=True)
class FGItem:
    id: str
    min_price: Price
    max_price: Price
    name: str = None
    short_name: str = None
    url: str = None
    condition: int = CONDITION_NEW
    status_code: int = 200


def get_merchant_names(tree):
    # Merchant Link XPath:
    # //a[@target='_blank' and contains(@href, "merch_name")]
    merchant_nodes = tree.xpath(
        "//a[@target='_blank' and contains(@href, 'merch_name')]"
    )
    log.debug(f"found {len(merchant_nodes)} merchant nodes.")
    merchants = []
    for idx, merchant_node in enumerate(merchant_nodes):
        log.debug(f"Found merchant {idx + 1}: {merchant_node.text.strip()}")
        merchants.append(merchant_node.text.strip())
    return merchants


def get_prices(tree):
    # Price collection xpath:
    # //div[@id='aod-offer']//div[contains(@id, "aod-price-")]//span[contains(@class,'a-offscreen')]
    price_nodes = tree.xpath(
        "//div[@id='aod-offer']//div[contains(@id, 'aod-price-')]//span[contains(@class,'a-offscreen')]"
    )
    log.debug(f"Found {len(price_nodes)} price nodes.")
    prices = []
    for idx, price_node in enumerate(price_nodes):
        log.debug(f"Found price {idx + 1}: {price_node.text}")
        prices.append(parse_price(price_node.text))
    return prices


def get_shipping_costs(tree, free_shipping_string):
    # Assume Free Shipping and change otherwise

    # Shipping collection xpath:
    # .//div[starts-with(@id, 'aod-bottlingDepositFee-')]/following-sibling::span
    shipping_nodes = tree.xpath(
        ".//div[starts-with(@id, 'aod-bottlingDepositFee-')]/following-sibling::*[1]"
    )
    count = len(shipping_nodes)
    log.debug(f"Found {count} shipping nodes.")
    if count == 0:
        log.warning("No shipping nodes found.  Assuming zero.")
        return FREE_SHIPPING_PRICE
    elif count > 1:
        log.warning("Found multiple shipping nodes.  Using the first.")

    shipping_node = shipping_nodes[0]
    # Shipping information is found within either a DIV or a SPAN following the bottleDepositFee DIV
    # What follows is logic to parse out the various pricing formats within the HTML.  Not ideal, but
    # it's what we have to work with.
    if shipping_node.tag == "div":
        if shipping_node.text.strip() == "":
            # Assume zero shipping for an empty div
            log.debug(
                "Empty div found after bottleDepositFee.  Assuming zero shipping."
            )
        else:
            # Assume zero shipping for unknown values in
            log.warning(
                f"Non-Empty div found after bottleDepositFee.  Assuming zero. Stripped Value: '{shipping_node.text.strip()}'"
            )
    elif shipping_node.tag == "span":
        # Shipping values in the span are contained in either another SPAN or hanging out alone in a B tag
        shipping_spans = shipping_node.findall("span")
        shipping_bs = shipping_node.findall("b")
        shipping_is = shipping_node.findall("i")
        if len(shipping_spans) > 0:
            # If the span starts with a "& " it's free shipping (right?)
            if shipping_spans[0].text.strip() == "&":
                # & Free Shipping message
                log.debug("Found '& Free', assuming zero.")
            elif shipping_spans[0].text.startswith("+"):
                return parse_price(shipping_spans[0].text.strip())
        elif len(shipping_bs) > 0:
            for message_node in shipping_bs:

                if message_node.text.upper() in free_shipping_string:
                    log.debug("Found free shipping string.")
                else:
                    log.error(
                        f"Couldn't parse price from <B>. Assuming 0. Do we need to add: '{message_node.text.upper()}'"
                    )
        elif len(shipping_is) > 0:
            # If it has prime icon class, assume free Prime shipping
            if "Free" in shipping_is[0].attrib["aria-label"]:
                log.debug("Found Free shipping with Prime")
        else:
            log.error(
                f"Unable to locate price.  Assuming 0.  Found this: '{shipping_node.text.strip()}'"
            )
    return FREE_SHIPPING_PRICE


def get_form_actions(tree):
    # ATC form actions
    # //div[@id='aod-offer']//form[contains(@action,'add-to-cart')]
    form_action_nodes = tree.xpath(
        "//div[@id='aod-offer']//form[contains(@action,'add-to-cart')]"
    )
    log.debug(f"Found {len(form_action_nodes)} form action nodes.")
    form_actions = []
    for idx, form_action in enumerate(form_action_nodes):
        form_actions.append(form_action.action)
    return form_actions


def get_item_condition(form_action) -> int:
    if "_new_" in form_action:
        log.debug(f"Item condition is new")
        return CONDITION_NEW
    elif "_used_" in form_action:
        log.debug(f"Item condition is used")
        return CONDITION_USED
    elif "_col_" in form_action:
        log.debug(f"Item condition is collectible")
        return CONDITION_COLLECTIBLE
    else:
        log.debug(f"Item condition is unknown: {form_action}")
        return CONDITION_UNKNOWN


def solve_captcha(session, form_element, pdp_url):
    log.warning("Encountered CAPTCHA. Attempting to solve.")
    # Starting from the form, get the inputs and image
    captcha_images = form_element.xpath('//img[contains(@src, "amazon.com/captcha/")]')
    if captcha_images:
        link = captcha_images[0].attrib["src"]
        # link = 'https://images-na.ssl-images-amazon.com/captcha/usvmgloq/Captcha_kwrrnqwkph.jpg'
        captcha = AmazonCaptcha.fromlink(link)
        solution = captcha.solve()

        if solution:
            form_inputs = form_element.xpath(".//input")
            input_dict = {}
            for form_input in form_inputs:
                if form_input.type == "text":
                    input_dict[form_input.name] = solution
                else:
                    input_dict[form_input.name] = form_input.value
            f = furl(pdp_url) # Use the original URL to get the schema and host
            f = f.set(path=form_element.attrib["action"])
            f.add(args=input_dict)
            payload = ""

            # conn.request("GET", f.url, payload, HEADERS)
            # response = conn.get_response()
            response = session.get(f.url)
            log.debug(f"Captcha response was {response.status_code}")
            return response.text, response.status_code

    return html.fromstring(""), 404


class AmazonStoreHandler(BaseStoreHandler):
    http_client = False
    http_20_client = False
    http_session = True

    def __init__(
        self,
        notification_handler: NotificationHandler,
        headless=False,
        checkshipping=False,
        detailed=False,
        used=False,
        single_shot=False,
        no_screenshots=False,
        disable_presence=False,
        slow_mode=False,
        no_image=False,
        encryption_pass=None,
        log_stock_check=False,
        shipping_bypass=False,
    ) -> None:
        super().__init__()

        self.notification_handler = notification_handler
        self.item_list: typing.List[FGItem] = []
        self.stock_checks = 0
        self.start_time = int(time.time())
        self.amazon_domain = "smile.amazon.com"
        self.driver = None
        self.webdriver_child_pids = []
        from cli.cli import global_config

        self.amazon_config = global_config.get_amazon_config()

        # Load up our configuration
        self.parse_config()

        # Set up the Chrome options based on user flags
        if headless:
            enable_headless()

        prefs = get_prefs(no_image)
        set_options(prefs, slow_mode)
        modify_browser_profile()

        # Initialize the Session we'll use for this run
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.conn = http.client.HTTPSConnection(self.amazon_domain)
        self.conn20 = HTTP20Connection(self.amazon_domain)

    def __del__(self):
        message = f"Shutting down {STORE_NAME} Store Handler."
        log.info(message)
        self.notification_handler.send_notification(message)

    def run(self, delay=45):
        # Verify the configuration file
        if not self.verify():
            # try one more time
            log.info("Failed to verify... trying more more time")
            self.verify()

        # To keep the user busy https://github.com/jakesgordon/javascript-tetris
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        uri = pathlib.Path(f"{ROOT_DIR}/../tetris/index.html").as_uri()
        log.debug(f"Tetris URL: {uri}")

        # Spawn the web browser
        self.driver = create_driver(options)
        self.webdriver_child_pids = get_webdriver_pids(self.driver)
        self.driver.get(uri)

        message = f"Starting to hunt items at {STORE_NAME}"
        log.info(message)
        self.notification_handler.send_notification(message)

        while self.item_list:
            qualified_seller, item = self.find_qualified_seller(delay)
            self.attempt_purchase(item, qualified_seller)

    def find_qualified_seller(self, delay) -> (SellerDetail, FGItem):
        while True:
            for item in self.item_list:
                item_sellers = self.get_item_sellers(
                    item, self.amazon_config["FREE_SHIPPING"]
                )
                for seller in item_sellers:
                    if (
                        item.max_price.amount
                        > seller.selling_price
                        > item.min_price.amount
                    ):
                        log.info("BUY THIS ITEM!!!!")
                        return seller, item
                    else:
                        log.info("No dice.")
            time.sleep(delay + random.randint(1, 3))

    def parse_config(self):
        log.info(f"Processing config file from {CONFIG_FILE_PATH}")
        # Parse the configuration file to get our hunt list
        try:
            with open(CONFIG_FILE_PATH) as json_file:
                config = json.load(json_file)
                self.amazon_domain = config.get("amazon_domain", "smile.amazon.com")

                json_items = config.get("items")
                self.parse_items(json_items)

        except FileNotFoundError:
            log.error(
                f"Configuration file not found at {CONFIG_FILE_PATH}.  Please see {CONFIG_FILE_PATH}_template."
            )
            exit(1)
        log.info(f"Found {len(self.item_list)} items to track at {STORE_NAME}.")

    def parse_items(self, json_items):
        for json_item in json_items:
            if (
                "max-price" in json_item
                and "asins" in json_item
                and "min-price" in json_item
            ):
                max_price = json_item["max-price"]
                min_price = json_item["min-price"]
                if type(max_price) is str:
                    max_price = parse_price(max_price)
                else:
                    max_price = Price(max_price, currency=None, amount_text=None)
                if type(min_price) is str:
                    min_price = parse_price(min_price)
                else:
                    min_price = Price(min_price, currency=None, amount_text=None)

                if "condition" in json_item:
                    condition = parse_condition(json_item["condition"])
                else:
                    condition = CONDITION_NEW

                # Create new instances of an item for each asin specified
                asins_collection = json_item["asins"]
                if isinstance(asins_collection, str):
                    log.warning(
                        f"\"asins\" node needs be an list/array and included in braces (e.g., [])  Attempting to recover {json_item['asins']}"
                    )
                    # did the user forget to put us in an array?
                    asins_collection = asins_collection.split(",")
                for asin in asins_collection:
                    self.item_list.append(
                        FGItem(
                            asin,
                            min_price,
                            max_price,
                            condition=condition,
                        )
                    )
            else:
                log.error(
                    f"Item isn't fully qualified.  Please include asin, min-price and max-price. {json_item}"
                )

    def verify(self):
        log.info("Verifying item list...")
        items_to_purge = []
        verified = 0
        for item in self.item_list:
            # Verify that the ASIN hits and that we have a valid inventory URL
            pdp_url = f"https://{self.amazon_domain}{PDP_PATH}{item.id}"
            log.debug(f"Verifying at {pdp_url} ...")
            # self.conn20.request("GET", pdp_url, "", HEADERS)
            # response = self.conn.getresponse()
            # response = self.conn.get_response()
            data, status = self.get_html(pdp_url)
            if status == 503:
                # Check for CAPTCHA
                tree = html.fromstring(data)
                captcha_form_element = tree.xpath(
                    "//form[contains(@action,'validateCaptcha')]"
                )
                if captcha_form_element:
                    # Solving captcha and resetting data
                    data, status = solve_captcha(self.session, captcha_form_element[0], pdp_url)

            if status == 200:
                item.url = f"{self.amazon_domain}{REALTIME_INVENTORY_PATH}{item.id}"
                tree = html.fromstring(data)
                captcha_form_element = tree.xpath(
                    "//form[contains(@action,'validateCaptcha')]"
                )
                if captcha_form_element:
                    tree = solve_captcha(self.session, captcha_form_element[0])

                title = tree.xpath('//*[@id="productTitle"]')
                if len(title) > 0:
                    item.name = title[0].text.strip()
                    item.short_name = (
                        item.name[:40].strip() + "..."
                        if len(item.name) > 40
                        else item.name
                    )
                    log.info(f"Verified ASIN {item.id} as '{item.short_name}'")
                    verified += 1
                else:
                    log.info(
                        f"Unable to verify ASIN {item.id}.  Continuing without verification."
                    )
            else:
                log.error(
                    f"Unable to locate details for {item.id} at {pdp_url}.  Removing from hunt."
                )
                items_to_purge.append(item)

        # Purge any items we didn't find while verifying
        for item in items_to_purge:
            self.item_list.remove(item)

        log.info(
            f"Verified {verified} out of {len(self.item_list)} items on {STORE_NAME}"
        )
        return True

    def get_item_sellers(self, item, free_shipping_strings):
        """Parse out information to from the aod-offer nodes populate ItemDetail instances for each item """
        payload = self.get_real_time_data(item)
        sellers = []
        # This is where the parsing magic goes
        log.debug(f"payload is {len(payload)} bytes")
        if len(payload) == 0:
            log.error("Empty Response.  Skipping...")
            return sellers

        tree = html.fromstring(payload)

        offers = tree.xpath("//div[@id='aod-offer']")
        if not offers:
            log.debug(f"No offers found for {item.id} = {item.short_name}")
            return sellers
        for idx, offer in enumerate(offers):
            # This is preferred, but Amazon itself has unique URL parameters that I haven't identified yet
            # merchant_name = offer.xpath(
            #     ".//a[@target='_blank' and contains(@href, 'merch_name')]"
            # )[0].text.strip()
            merchant_name = offer.xpath(".//a[@target='_blank']")[0].text.strip()
            price_text = offer.xpath(
                ".//div[contains(@id, 'aod-price-')]//span[contains(@class,'a-offscreen')]"
            )[0].text
            price = parse_price(price_text)

            shipping_cost = get_shipping_costs(offer, free_shipping_strings)
            form_action = offer.xpath(".//form[contains(@action,'add-to-cart')]")[
                0
            ].action
            condition = get_item_condition(form_action)
            offers = offer.xpath(f".//input[@name='offeringID.1']")
            offer_id = None
            if len(offers) > 0:
                offer_id = offers[0].value
            else:
                log.error("No offer ID found!")

            seller = SellerDetail(
                merchant_name,
                price,
                shipping_cost,
                condition,
                form_action,
                offer_id,
            )
            sellers.append(seller)
            log.debug(f"{merchant_name} {price.amount} {shipping_cost.amount}")

        return sellers

    def get_real_time_data(self, item):
        log.debug(f"Calling {STORE_NAME} for {item.short_name} using {item.url}")
        # self.conn20.request("GET", item.url, "", HEADERS)
        # response = self.conn.getresponse()
        # response = self.conn20.get_response()
        data, status = self.get_html(item.url)
        if item.status_code != status:
            # Track when we flip-flop between status codes.  200 -> 204 may be intelligent caching at Amazon.
            # We need to know if it ever goes back to a 200
            log.warning(
                f"{item.short_name} started responding with Status Code {status} instead of {item.status_code}"
            )
            item.status_code = status
        return data

    def attempt_purchase(self, item, qualified_seller):
        # Open the item URL in Selenium

        pass

    def get_html(self, url):
        """Unified mechanism to get content to make changing connection clients easier"""
        f = furl(url)

        if self.http_client:
            # http.client method
            self.conn.request("GET", str(f.path), "", HEADERS)
            response = self.conn.getresponse()
            data = response.read()
            return data.decode("utf-8"), response.status
        elif self.http_20_client:
            # hyper HTTP20Connection method
            self.conn20.request("GET", str(f.path), "", HEADERS)
            response = self.conn20.get_response()
            data = response.read()
            return data.decode("utf-8"), response.status
        else:
            response = self.session.get(f.url, headers=HEADERS)
            return response.text, response.status_code



def parse_condition(condition: str) -> int:
    if "new" in condition:
        log.debug(f"Item condition is new")
        return CONDITION_NEW
    elif "used" in condition:
        log.debug(f"Item condition is used")
        return CONDITION_USED
    elif "col" in condition:
        log.debug(f"Item condition is collectible")
        return CONDITION_COLLECTIBLE
    else:
        log.debug(f"Item condition is unknown: {condition}")
        return CONDITION_UNKNOWN


def min_total_price(seller: SellerDetail):
    return seller.selling_price


def new_first(seller: SellerDetail):
    return seller.condition


def create_driver(options):
    try:
        return webdriver.Chrome(executable_path=binary_path, options=options)
    except Exception as e:
        log.error(e)
        log.error(
            "If you have a JSON warning above, try deleting your .profile-amz folder"
        )
        log.error(
            "If that's not it, you probably have a previous Chrome window open. You should close it."
        )


def modify_browser_profile():
    # Delete crashed, so restore pop-up doesn't happen
    path_to_prefs = os.path.join(
        os.path.dirname(os.path.abspath("__file__")),
        ".profile-amz",
        "Default",
        "Preferences",
    )
    try:
        with fileinput.FileInput(path_to_prefs, inplace=True) as file:
            for line in file:
                print(line.replace("Crashed", "none"), end="")
    except FileNotFoundError:
        pass


def set_options(prefs, slow_mode):
    options.add_experimental_option("prefs", prefs)
    options.add_argument(f"user-data-dir=.profile-amz")
    if not slow_mode:
        options.set_capability("pageLoadStrategy", "none")


def get_prefs(no_image):
    prefs = {
        "profile.password_manager_enabled": False,
        "credentials_enable_service": False,
    }
    if no_image:
        prefs["profile.managed_default_content_settings.images"] = 2
    else:
        prefs["profile.managed_default_content_settings.images"] = 0
    return prefs


def create_webdriver_wait(driver, wait_time=10):
    return WebDriverWait(driver, wait_time)


def get_webdriver_pids(driver):
    pid = driver.service.process.pid
    driver_process = psutil.Process(pid)
    children = driver_process.children(recursive=True)
    webdriver_child_pids = []
    for child in children:
        webdriver_child_pids.append(child.pid)
    return webdriver_child_pids
