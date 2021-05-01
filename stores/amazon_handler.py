import json
import time
import typing
import asyncio
from furl import furl
from price_parser import parse_price, Price
import inspect

from common.amazon_support import (
    AmazonItemCondition,
    condition_check,
    FGItem,
    get_shipping_costs,
    price_check,
    SellerDetail,
    solve_captcha,
    merchant_check,
    parse_condition,
)

from notifications.notifications import NotificationHandler
from stores.basestore import BaseStoreHandler
from utils.logger import log

from stores.amazon_monitoring import AmazonMonitoringHandler, AmazonMonitor
from stores.amazon_checkout import AmazonCheckoutHandler

CONFIG_FILE_PATH = "config/amazon_aio_config.json"
STORE_NAME = "Amazon"

amazon_config = {}

queue: asyncio.Queue


class AmazonStoreHandler(BaseStoreHandler):
    http_client = False
    http_20_client = False
    http_session = True

    def __init__(
        self,
        notification_handler: NotificationHandler,
        single_shot=False,
        encryption_pass=None,
    ) -> None:
        super().__init__()
        self.shuffle = True
        self.is_test = False
        self.selenium_refresh_offset = 7200
        self.selenium_refresh_time = 0

        self.notification_handler = notification_handler
        self.item_list: typing.List[FGItem] = []
        self.stock_checks = 0
        self.start_time = int(time.time())
        self.amazon_domain = "smile.amazon.com"
        self.webdriver_child_pids = []
        self.single_shot = single_shot
        # self.loop = asyncio.get_event_loop()

        from cli.cli import global_config

        global amazon_config
        amazon_config = global_config.get_amazon_config(encryption_pass)
        self.profile_path = global_config.get_browser_profile_path()

        # Load up our configuration
        self.parse_config()
        log.debug("AmazonStoreHandler initialization complete.")

    def __del__(self):
        message = f"Shutting down {STORE_NAME} Store Handler."
        log.info(message)
        self.notification_handler.send_notification(message)

    async def run_async(self, checkout_tasks=1):
        log.debug("Creating checkout queue")
        global queue
        queue = asyncio.Queue()
        log.debug("Creating checkout handler")
        amazon_checkout = AmazonCheckoutHandler(
            notification_handler=self.notification_handler,
            amazon_config=amazon_config,
            cookie_list=[
                "session-id",
                "x-amz-captcha-1",
                "x-amz-captcha-2",
                "ubid-main",
                "x-main",
                "at-main",
                "sess-at-main",
            ],
            profile_path=self.profile_path,
        )
        log.debug("Creating monitoring handler")
        amazon_monitoring = AmazonMonitoringHandler(
            notification_handler=self.notification_handler,
            item_list=self.item_list,
            amazon_config=amazon_config,
            tasks=checkout_tasks,
        )
        log.debug("Creating checkout worker and monitoring task(s)")
        future = []
        for idx in range(len(amazon_monitoring.sessions_list)):
            future.append(asyncio.Future())
            future[idx].add_done_callback(recreate_session_callback)

        await asyncio.gather(
            amazon_checkout.checkout_worker(queue=queue),
            *[
                amazon_monitoring.sessions_list[idx].stock_check(queue, future[idx])
                for idx in range(len(amazon_monitoring.sessions_list))
            ],
        )
        return

    def parse_config(self):
        log.debug(f"Processing config file from {CONFIG_FILE_PATH}")
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
        log.debug(f"Found {len(self.item_list)} items to track at {STORE_NAME}.")

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
                    condition = AmazonItemCondition.New

                if "merchant_id" in json_item:
                    merchant_id = json_item["merchant_id"]
                else:
                    merchant_id = "any"

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
                            merchant_id=merchant_id,
                            furl=furl(
                                url=f"https://smile.amazon.com/gp/aod/ajax?asin={asin}"
                            ),
                        )
                    )
            else:
                log.error(
                    f"Item isn't fully qualified.  Please include asin, min-price and max-price. {json_item}"
                )


def recreate_session_callback(future: asyncio.Future):
    log.debug("Checking session result")
    global queue
    if isinstance(future.result(), AmazonMonitor):
        log.debug("session result is a monitoring class, recreating monitor")
        session: AmazonMonitor = future.result()
        future = asyncio.Future()
        future.add_done_callback(recreate_session_callback)
        asyncio.create_task(session.stock_check(queue=queue, future=future))
        log.debug("New monitor task create")
