import http.client
import json
import random
import time
from decimal import Decimal

import attr
import typing

from lxml import html
from price_parser import parse_price, Price

from notifications.notifications import NotificationHandler
from stores.basestore import BaseStoreHandler
from utils.logger import log

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
            if shipping_is[0].attrib["aria-label"].contains == 'Free':
                log.debug("Found Free Prime Shipping")
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


class AmazonStoreHandler(BaseStoreHandler):
    def __init__(self, notification_handler: NotificationHandler) -> None:
        super().__init__()
        self.notification_handler = notification_handler
        self.item_list: typing.List[PreyItem] = []
        self.stock_checks = 0
        self.start_time = int(time.time())

        from cli.cli import global_config

        self.amazon_config = global_config.get_amazon_config()

        # Load up our configuration
        self.parse_config()

        # Initialize the Session we'll use for this run
        # self.session = requests.Session()
        self.conn = http.client.HTTPSConnection(AMAZON_DOMAIN)

    def __del__(self):
        message = f"Shutting down {STORE_NAME} Store Handler."
        log.info(message)
        self.notification_handler.send_notification(message)

    def run(self, delay=45):
        # Load real-time inventory for the provided SM list and clean it up as we go
        self.verify()
        message = f"Starting to hunt items at {STORE_NAME}"
        log.info(message)
        self.notification_handler.send_notification(message)

        while True:
            for item in self.item_list:
                item_sellers = self.get_item_sellers(item)

                for seller in item_sellers:
                    if (
                        item.max_price.amount
                        > seller.selling_price
                        > item.min_price.amount
                    ):
                        log.info("BUY THIS ITEM!!!!")
                    else:
                        log.info("No dice.")

                # log.info(f"Default order")
                # for seller in item_sellers:
                #     log.info(
                #         f"{seller.name} selling for a total of {seller.selling_price}"
                #     )
                #
                # log.info(f"Price order")
                # item_sellers.sort(key=min_total_price)
                # for seller in item_sellers:
                #     log.info(
                #         f"{seller.name} selling for a total of {seller.selling_price}"
                #     )
                #
                # log.info(f"Condition order")
                # item_sellers.sort(key=new_first)
                # for seller in item_sellers:
                #     log.info(
                #         f"{seller.name} selling for a total of {seller.selling_price}"
                #     )

                # if self.check_stock(item_info):
                #     url = f"https://store.asus.com/us/item/{sm_id}"
                #     log.debug(f"Spawning browser to URL {url}")
                #     webbrowser.open_new(url)
                #     log.debug(f"Removing {sm_id} from hunt list.")
                #     self.item_list.remove(sm_id)
                #     self.notification_handler.send_notification(
                #         f"Found in-stock item at ASUS: {url}"
                #     )
                # if self.stock_checks > 0 and self.stock_checks % 1000 == 0:
                #     checks_per_second = self.stock_checks / self.get_elapsed_time(
                #         self.start_time
                #     )
                #     log.info(
                #         f"Performed {self.stock_checks} stock checks so far ({checks_per_second} cps). Continuing to "
                #         f"scan... "
                #     )
            time.sleep(delay + random.randint(1, 3))
            break

    def parse_config(self):
        log.info(f"Processing config file from {CONFIG_FILE_PATH}")
        # Parse the configuration file to get our hunt list
        try:
            with open(CONFIG_FILE_PATH) as json_file:
                config = json.load(json_file)
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
                        PreyItem(
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
            pdp_url = PDP_PATH + item.id
            self.conn.request("GET", pdp_url, "", HEADERS)
            log.debug(f"Verifying at {AMAZON_DOMAIN}{pdp_url} ...")
            response = self.conn.getresponse()
            if response.status == 200:
                item.url = REALTIME_INVENTORY_PATH + item.id
                data = response.read()
                tree = html.fromstring(data.decode("utf-8"))
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
                response.read()  # Flush the buffer
                log.error(
                    f"Unable to locate details for {item.id} at {AMAZON_DOMAIN}{pdp_url}.  Removing from hunt."
                )
                items_to_purge.append(item)

        # Purge any items we didn't find while verifying
        for item in items_to_purge:
            self.item_list.remove(item)

        log.info(
            f"Verified {verified} out of {len(self.item_list)} items on {STORE_NAME}"
        )

    def get_item_sellers(self, item):
        """Parse out information to from the aod-offer nodes populate ItemDetail instances for each item """
        payload = self.get_real_time_data(item)
        # This is where the parsing magic goes
        log.debug(f"payload is {len(payload)} bytes")
        tree = html.fromstring(payload)

        offers = tree.xpath("//div[@id='aod-offer']")
        sellers = []
        if not offers:
            log.debug(f"No offers found for {item.id} = {item.short_name}")
        else:
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
                shipping_cost = get_shipping_costs(
                    offer, self.amazon_config["FREE_SHIPPING"]
                )
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
        self.conn.request("GET", item.url, "", HEADERS)
        response = self.conn.getresponse()
        data = response.read()
        return data.decode("utf-8")


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
class PreyItem:
    id: str
    min_price: Price
    max_price: Price
    name: str = None
    short_name: str = None
    url: str = None
    condition: int = CONDITION_NEW


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
