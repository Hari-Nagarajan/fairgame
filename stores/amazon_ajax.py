import http.client
import json
import random
import time

from lxml import html
from price_parser import parse_price

from stores.basestore import BaseStoreHandler
from utils.logger import log

# PDP_URL = "https://smile.amazon.com/gp/product/"
# AMAZON_DOMAIN = "www.amazon.com.au"
# AMAZON_DOMAIN = "www.amazon.com.br"
# AMAZON_DOMAIN = "www.amazon.ca"
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
AMAZON_DOMAIN = "www.amazon.com"
# AMAZON_DOMAIN = "www.amazon.se"

PDP_PATH = f"/dp/"
# REALTIME_INVENTORY_URL = f"{AMAZON_DOMAIN}gp/aod/ajax/ref=aod_f_new?asin="
REALTIME_INVENTORY_PATH = f"/gp/aod/ajax/ref=aod_f_new?isonlyrenderofferlist=true&asin="
# REALTIME_INVENTORY_URL = "https://www.amazon.com/gp/aod/ajax/ref=dp_aod_NEW_mbc?asin="
CONFIG_FILE_PATH = "config/amazon_ajax_config.json"
STORE_NAME = "Amazon"

# Request
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, sdch, br",
    "Accept-Language": "en-US,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
}
HEADERS = {
    "authority": "www.amazon.ca",
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


amazon_config = None


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


def get_shipping_costs(tree):
    # Shipping collection xpath:
    # //div[@id='aod-offer-list']//div[starts-with(@id, 'aod-bottlingDepositFee-')]/following-sibling::span
    shipping_nodes = tree.xpath(
        "//div[@id='aod-offer']//div[starts-with(@id, 'aod-bottlingDepositFee-')]/following-sibling::*[1]"
    )
    log.debug(f"Found {len(shipping_nodes)} shipping nodes.")
    shipping_costs = []
    for idx, shipping_node in enumerate(shipping_nodes):
        # Shipping information is found within either a DIV or a SPAN following the bottleDepositFee DIV
        # What follows is logic to parse out the various pricing formats within the HTML.  Not ideal, but
        # it's what we have to work with.
        if shipping_node.tag == "div":
            if shipping_node.text.strip() == "":
                # Assume zero shipping for an empty div
                shipping_costs.append(parse_price("0.00"))
            else:
                log.warning(
                    f"Non-Empty div found after bottle deposits.  Stripped Value: '{shipping_node.text.strip()}'"
                )
        elif shipping_node.tag == "span":
            # Shipping values in the span are contained in either another SPAN or hanging out alone in a B tag
            shipping_spans = shipping_node.findall("span")
            shipping_bs = shipping_node.findall("b")
            if len(shipping_spans) > 0:
                # If the span starts with a "& " it's free shipping (right?)
                if shipping_spans[0].text.strip() == "&":
                    # & Free Shipping message
                    shipping_costs.append("0.00")
                elif shipping_spans[0].text.startswith("+"):
                    shipping_costs.append(parse_price(shipping_spans[0].text.strip()))
            elif len(shipping_bs) > 0:
                for message_node in shipping_bs:
                    if message_node.text.upper() in amazon_config["FREE_SHIPPING"]:
                        shipping_costs.append(parse_price("0.00"))
                    else:
                        log.error(
                            f"Couldn't parse price from <B>. Assuming 0. Do we need to add: '{message_node.text.upper()}'"
                        )
                        shipping_costs.append(parse_price("0.00"))
            else:
                log.error(
                    f"Unable to locate price.  Assuming 0.  Found this: '{shipping_node.text.strip()}'"
                )
                shipping_costs.append(parse_price("0.00"))

        log.debug(f"Shipping cost {idx + 1}: {shipping_costs[idx]}")
    return shipping_costs


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


def get_item_condition(form_actions):
    item_conditions = []
    for idx, form_action in enumerate(form_actions):
        if "_new_" in form_action:
            log.debug(f"Item {idx + 1} is new")
            item_conditions.append("new")
        elif "_used_" in form_action:
            log.debug(f"Item {idx + 1} is used")
            item_conditions.append("used")
        elif "_col_" in form_action:
            log.debug(f"Item {idx+1} is collectible")
        else:
            log.debug(f"Item {idx + 1} is unknown: {form_action}")
            item_conditions.append("unknown")
    return item_conditions


class AmazonStoreHandler(BaseStoreHandler):
    def __init__(self, notification_handler) -> None:
        super().__init__()
        self.notification_handler = notification_handler
        self.item_list = []
        self.stock_checks = 0
        self.start_time = int(time.time())

        global amazon_config
        from cli.cli import global_config

        amazon_config = global_config.get_amazon_config()

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
                item_info = self.get_item_detail(item)
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
                self.item_list = config.get("items")
        except FileNotFoundError:
            log.error(
                f"Configuration file not found at {CONFIG_FILE_PATH}.  Please see {CONFIG_FILE_PATH}_template."
            )
            exit(1)
        log.info(f"Found {len(self.item_list)} items to track at {STORE_NAME}.")

    def verify(self):
        log.info("Verifying item list...")
        items_to_purge = []
        for item in self.item_list:
            # Verify that the ASIN hits and that we have a valid inventory URL
            pdp_url = PDP_PATH + item["asin"]
            self.conn.request("GET", pdp_url, "", HEADERS)
            response = self.conn.getresponse()
            if response.status == 200:
                item["url"] = REALTIME_INVENTORY_PATH + item["asin"]
                data = response.read()
                tree = html.fromstring(data.decode("utf-8"))
                title = tree.xpath('//*[@id="productTitle"]')
                if len(title) > 0:
                    item["name"] = title[0].text.strip()
                    item["short_name"] = (
                        item["name"][:40].strip() + "..."
                        if len(item["name"]) > 40
                        else item["name"]
                    )
                log.info(f"Verified ASIN {item['asin']} as '{item['short_name']}'")
            else:
                log.error(
                    f"Unable to locate details for {item['asin']} at {pdp_url}.  Removing from hunt."
                )
                items_to_purge.append(item)

        # Purge any items we didn't find while verifying
        for item in items_to_purge:
            self.item_list.remove(item)

        # for sm_id, sm_details in sm_status_list.items():
        #     if sm_details["not_found"]:
        #         log.error(
        #             f"ASUS store reports {sm_id} not found.  Removing {sm_id} from list"
        #         )
        #         # Remove from the list, since ASUS reports it as "not found"
        #         self.sm_list.remove(sm_id)
        #     else:
        #         name = sm_details["market_info"]["name"]
        #         stop_index = name.index(" (")
        #         short_name = name[0:stop_index]
        #         log.info(
        #             f"Found {sm_id}: {short_name} @ {sm_details['market_info']['price']['final_price']['price']}"
        #         )
        log.info(f"Verified {len(self.item_list)} items on {STORE_NAME}")

    def get_item_detail(self, item):
        """Parse out information to populate ItemDetail instances for each item """
        payload = self.get_real_time_data(item)
        # This is where the parsing magic goes
        log.info(f"payload is {len(payload)} bytes")
        tree = html.fromstring(payload)

        prices = get_prices(tree)
        shipping_costs = get_shipping_costs(tree)
        form_actions = get_form_actions(tree)
        item_conditions = get_item_condition(form_actions)

        log.info(f"Prices found {len(prices)}")
        log.info(f"Shipping found {len(shipping_costs)}")
        log.info(f"Forms found {len(form_actions)}")
        log.info(f"Item conditions found {len(item_conditions)}")
        if len(prices) != len(shipping_costs) or len(shipping_costs) != len(
            form_actions
        ):
            log.error("We have failed everyone.")
            exit(5)

        # TODO: build seller detail objects to compare and determine if we should buy

    def get_real_time_data(self, item):
        log.info(f"Calling {STORE_NAME} for {item['short_name']} using {item['url']}")
        url = item["url"]
        self.conn.request("GET", url, "", HEADERS)
        response = self.conn.getresponse()
        data = response.read()
        return data.decode("utf-8")

    def check_stock(self, item):
        price = item["market_info"]["price"]["final_price"]["price"]
        quantity = item["market_info"]["quantity"]
        if item["market_info"]["buy"]:
            log.info(
                f"Asus has {quantity} of {item['sm_seq']} available to buy for {price}"
            )
            return True
        else:
            # log.info(f"{sm_id} is unavailable.  Offer price listed as {price}")
            self.stock_checks += 1
        return False


class ItemDetail:
    def __init__(self, price, shipping_costs) -> None:
        super().__init__()


class SellerDetail:
    def __init__(self, name, price, shipping_cost, atc_url, atc_payload) -> None:
        super().__init__()
