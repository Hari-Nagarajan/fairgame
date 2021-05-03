#      FairGame - Automated Purchasing Program
#      Copyright (C) 2021  Hari Nagarajan
#
#      This program is free software: you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#      The author may be contacted through the project's GitHub, at:
#      https://github.com/Hari-Nagarajan/fairgame

import json
import os

import time
import typing
from typing import Optional, Iterable, NamedTuple, List, Dict
from utils.debugger import debug, timer
from fake_useragent import UserAgent
from amazoncaptcha import AmazonCaptcha

from urllib.parse import urlparse

import re

import requests
from furl import furl
from lxml import html
from price_parser import parse_price, Price
from utils.misc import (
    parse_html_source,
    get_timestamp_filename,
    save_html_response,
    check_response,
)

from common.amazon_support import (
    AmazonItemCondition,
    condition_check,
    FGItem,
    get_shipping_costs,
    price_check,
    SellerDetail,
    solve_captcha,
    merchant_check,
    has_captcha,
    free_shipping_check,
)
from notifications.notifications import NotificationHandler
from stores.basestore import BaseStoreHandler
from utils.logger import log
import asyncio
import aiohttp
from aiohttp_proxy import ProxyConnector, ProxyType

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
# AMAZON_DOMAIN = "www.amazon.com"
# AMAZON_DOMAIN = "www.amazon.se"

AMAZON_URLS = {
    "BASE_URL": "https://{domain}/",
    "ALT_OFFER_URL": "https://{domain}/gp/offer-listing/",
    "OFFER_URL": "https://{domain}/dp/",
    "CART_URL": "https://{domain}/gp/cart/view.html",
    "ATC_URL": "https://{domain}/gp/aws/cart/add.html",
    "PTC_GET": "https://{domain}/gp/cart/view.html/ref=lh_co_dup?ie=UTF8&proceedToCheckout.x=129",
    "PYO_POST": "https://{domain}/gp/buy/spc/handlers/static-submit-decoupled.html/ref=ox_spc_place_order?",
}

PDP_PATH = f"/dp/"
REALTIME_INVENTORY_PATH = f"gp/aod/ajax?asin="

CONFIG_FILE_PATH = "config/amazon_requests_config.json"
PROXY_FILE_PATH = "config/proxies.json"
STORE_NAME = "Amazon"
DEFAULT_MAX_TIMEOUT = 10

# Request
HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, sdch, br",
    "content-type": "application/x-www-form-urlencoded",
}
amazon_config = {}


class AmazonMonitoringHandler(BaseStoreHandler):
    http_client = False
    http_20_client = False
    http_session = True

    def __init__(
        self,
        notification_handler: NotificationHandler,
        item_list: List[FGItem],
        amazon_config,
        tasks=1,
        checkshipping=False,
    ) -> None:
        log.debug("Initializing AmazonMonitoringHandler")
        super().__init__()

        self.shuffle = True

        self.notification_handler = notification_handler
        self.check_shipping = checkshipping
        self.item_list: typing.List[FGItem] = item_list
        self.stock_checks = 0
        self.start_time = int(time.time())
        self.amazon_config = amazon_config
        ua = UserAgent()

        self.proxies = get_proxies(path=PROXY_FILE_PATH)

        # Initialize the Session we'll use for stock checking
        log.debug("Initializing Monitoring Sessions")
        self.sessions_list: Optional[List[AmazonMonitor]] = []
        for idx in range(len(item_list)):
            connector = None
            if self.proxies and idx < len(self.proxies):
                connector = ProxyConnector.from_url(self.proxies[idx]["https"])
            self.sessions_list.append(
                AmazonMonitor(
                    headers=HEADERS,
                    item=item_list[idx],
                    amazon_config=self.amazon_config,
                    connector=connector,
                )
            )
            self.sessions_list[idx].headers.update({"user-agent": ua.random})


# class Offers(NamedTuple):
#     asin: str
#     offerlistingid: str
#     merchantid: str
#     price: float
#     timestamp: float
#     __slots__ = ()
#
#     def __str__(self):
#         return f"ASIN: {self.asin}; offerListingId: {self.offerlistingid}; merchantId: {self.merchantid}; price: {self.price}"


class AmazonMonitor(aiohttp.ClientSession):
    def __init__(
        self,
        item: FGItem,
        amazon_config: Dict,
        *args,
        **kwargs,
    ):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.item = item
        self.amazon_config = amazon_config
        self.domain = urlparse(self.item.furl.url).netloc

        self.delay: float = 5
        log.debug("Initializing Monitoring Task")

    def assign_config(self, azn_config):
        self.amazon_config = azn_config

    def assign_delay(self, delay: float = 5):
        self.delay = delay

    def assign_item(self, item: FGItem):
        self.item = item

    def fail_recreate(self):
        # Something wrong, start a new task then kill this one
        log.debug("Max consecutive request fails reached. Restarting session")
        session = AmazonMonitor(
            headers=HEADERS,
            item=self.item,
            amazon_config=self.amazon_config,
            connector=self.connector,
        )
        session.headers.update({"user-agent": UserAgent().random})
        log.debug("Sesssion Created")
        return session

    async def stock_check(self, queue: asyncio.Queue, future: asyncio.Future):
        # Do first response outside of while loop, so we can continue on captcha checks
        # and return to start of while loop with that response. Requires the next response
        # to be grabbed at end of while loop
        log.debug(f"Monitoring Task Started for {self.item.id}")

        fail_counter = 0  # Count sequential get fails
        delay = 5
        end_time = time.time() + delay
        status, response_text = await self.aio_get(url=self.item.furl.url)

        save_html_response("stock-check", status, response_text)

        # do this after each request
        fail_counter = check_fail(status=status, fail_counter=fail_counter)
        if fail_counter == -1:
            session = self.fail_recreate()
            future.set_result(session)
            return

        check_count = 1
        # Loop will only exit if a qualified seller is returned.
        while True:
            log.debug(f"{self.item.id} Stock Check Count: {check_count}")
            tree = check_response(response_text)
            if tree is not None:
                if captcha_element := has_captcha(tree):
                    log.debug("Captcha found during monitoring task")
                    # wait a second so it doesn't continuously hit captchas very quickly
                    # TODO: maybe track captcha hits so that it aborts after several?
                    await asyncio.sleep(1)
                    # get the next response after solving captcha and then continue to next loop iteration
                    status, response_text = await self.async_captcha_solve(
                        captcha_element[0], self.domain
                    )

                    # do this after each request
                    fail_counter = check_fail(status=status, fail_counter=fail_counter)
                    if fail_counter == -1:
                        session = self.fail_recreate()
                        future.set_result(session)
                        return

                    await wait_timer(end_time)
                    end_time = time.time() + delay
                    continue
                if tree is not None and (
                    sellers := get_item_sellers(
                        tree,
                        item=self.item,
                        free_shipping_strings=self.amazon_config["FREE_SHIPPING"],
                    )
                ):
                    qualified_seller = get_qualified_seller(
                        item=self.item, sellers=sellers
                    )
                    if qualified_seller:
                        log.debug("Found an offer which meets criteria")
                        await queue.put(qualified_seller)
                        log.debug("Offer placed in queue")
                        log.debug("Quitting monitoring task")
                        future.set_result(None)
                        return None
            # failed to find seller. Wait a delay period then check again
            log.debug("No offers found which meet product criteria")
            await wait_timer(end_time)
            end_time = time.time() + delay
            status, response_text = await self.aio_get(url=self.item.furl.url)
            save_html_response("stock-check", status, response_text)
            # do this after each request
            fail_counter = check_fail(status=status, fail_counter=fail_counter)
            if fail_counter == -1:
                session = self.fail_recreate()
                future.set_result(session)
                return

            check_count += 1

    async def aio_get(self, url):
        status = 404
        text = None
        try:
            async with self.get(url) as resp:
                status = resp.status
                text = await resp.text()
        except aiohttp.ClientError as e:
            log.debug(e)
            status = 999
        return status, text

    async def async_captcha_solve(self, captcha_element, domain):
        log.debug("Encountered CAPTCHA. Attempting to solve.")
        # Starting from the form, get the inputs and image
        captcha_images = captcha_element.xpath(
            '//img[contains(@src, "amazon.com/captcha/")]'
        )
        if captcha_images:
            link = captcha_images[0].attrib["src"]
            # link = 'https://images-na.ssl-images-amazon.com/captcha/usvmgloq/Captcha_kwrrnqwkph.jpg'
            captcha = AmazonCaptcha.fromlink(link)
            solution = captcha.solve()
            if solution:
                log.info(f"solution is:{solution} ")
                form_inputs = captcha_element.xpath(".//input")
                input_dict = {}
                for form_input in form_inputs:
                    if form_input.type == "text":
                        input_dict[form_input.name] = solution
                    else:
                        input_dict[form_input.name] = form_input.value
                f = furl(domain)  # Use the original URL to get the schema and host
                f = f.set(path=captcha_element.attrib["action"])
                f.add(args=input_dict)
                status, response = await self.aio_get(f.url)
                return status, response
        return None


def check_fail(status, fail_counter, fail_list=None) -> int:
    """Checks status against failure status codes. Checks consecutive failure count.
    Returns -1 if maximum failure count reached. Otherwise returns 0 for not a failure, or
    n, where n is the current consecutive failure count"""

    if fail_list is None:
        fail_list = [503, 999]
    MAX_FAILS = 5
    n = fail_counter
    if status in fail_list:
        n += 1
        if n >= MAX_FAILS:
            return -1
        return n
    else:
        return 0


async def wait_timer(end_time):
    if (wait_delay := end_time - time.time()) > 0:
        await asyncio.sleep(wait_delay)


@timer
def get_item_sellers(
    tree: html.HtmlElement, item: FGItem, free_shipping_strings, atc_method=False
):
    """Parse out information to from the aod-offer nodes populate ItemDetail instances for each item """
    sellers: Optional[List[SellerDetail]] = []
    if tree is None:
        return sellers

    # Default response
    found_asin = "[NO ASIN FOUND ON PAGE]"
    # First see if ASIN can be found with xpath
    # look for product ASIN
    page_asin = tree.xpath("//input[@id='ftSelectAsin']")
    if page_asin:
        try:
            found_asin = page_asin[0].value.strip()
        except (AttributeError, IndexError):
            pass
    # if cannot find with xpath, try regex
    else:
        find_asin = re.search(
            r"asin\s?(?:=|\.)?\s?\"?([A-Z0-9]+)\"?", tree.text_content()
        )
        if find_asin:
            found_asin = find_asin.group(1)

    if found_asin != item.id:
        log.debug(
            f"Aborting Check, ASINs do not match. Found {found_asin}; Searching for {item.id}."
        )
        return sellers

    # Get all the offers (pinned and others)
    offers = tree.xpath("//div[@id='aod-sticky-pinned-offer'] | //div[@id='aod-offer']")
    # Exit if no offers found
    if not offers:
        log.debug(f"No offers for {item.id} = {item.short_name}")
        return sellers
    log.debug(f"Found {len(offers)} offers.")
    # Parse the found offers

    sellers = parse_offers(offers, free_shipping_strings, atc_method=atc_method)

    return sellers


@debug
def parse_offers(offers: html.HtmlElement, free_shipping_strings, atc_method=False):
    sellers: Optional[List[SellerDetail]] = []
    for idx, offer in enumerate(offers):
        # Get Seller merchant ID
        # Default Merchant ID
        merchant_id = ""
        # Try to find merchant ID with xpath
        try:
            merchant_id = offer.xpath(
                ".//input[@id='ftSelectMerchant' or @id='ddmSelectMerchant']"
            )[0].value
        except IndexError:
            # try to find merchant ID with regex
            try:
                merchant_script = offer.xpath(".//script")[0].text.strip()
                find_merchant_id = re.search(
                    r"merchantId = \"(\w+?)\";", merchant_script
                )
                if find_merchant_id:
                    merchant_id = find_merchant_id.group(1)
            except IndexError:
                pass
        log.info(f"merchant_id: {merchant_id}")
        # log failure to find merchant ID
        if not merchant_id:
            log.debug("No Merchant ID found")

        # Get Seller product price
        try:
            price_text = offer.xpath(".//span[@class='a-price-whole']")[0].text.strip()
        except IndexError:
            log.debug("No price found for this offer, skipping")
            continue
        price = parse_price(price_text)
        log.info(f"price: {price.amount_text}")
        # Get Seller shipping cost
        shipping_cost = get_shipping_costs(offer, free_shipping_strings)
        log.info(f"shipping: {shipping_cost.amount_text}")
        # Get Seller product condition
        condition_heading = offer.xpath(".//div[@id='aod-offer-heading']/h5")
        if condition_heading:
            condition = AmazonItemCondition.from_str(condition_heading[0].text.strip())
        else:
            condition = AmazonItemCondition.Unknown
        log.info(f"condition: {str(condition)}")

        # Get Seller item offerListingId
        offer_ids = offer.xpath(f".//input[@name='offeringID.1']")
        if len(offer_ids) > 0:
            offer_id = offer_ids[0].value
        else:
            log.error("No offer ID found for this offer, skipping")
            continue
        log.info(f"offer id: {offer_id}")

        # get info for ATC post
        # only use if doing ATC method
        atc_form = []
        if atc_method:
            try:
                atc_form = [
                    offer.xpath(".//form[@method='post']")[0].action,
                    offer.xpath(".//form//input"),
                ]
            except IndexError:
                log.error("ATC form items did not exist, skipping")
                continue

        seller = SellerDetail(
            merchant_id,
            price,
            shipping_cost,
            condition,
            offer_id,
            atc_form=atc_form,
        )
        sellers.append(seller)
    return sellers


@timer
def get_qualified_seller(item, sellers, check_shipping=False) -> SellerDetail or None:
    if not sellers:
        return None
    for seller in sellers:
        if not check_shipping and not free_shipping_check(seller):
            log.debug("Failed shipping hurdle.")
            continue
        log.debug("Passed shipping hurdle.")
        if item.condition == AmazonItemCondition.Any:
            log.debug("Skipping condition check")
        elif not condition_check(item, seller):
            log.debug("Failed item condition hurdle.")
            continue
        log.debug("Passed item condition hurdle.")
        if not price_check(item, seller):
            log.debug("Failed price condition hurdle.")
            continue
        log.debug("Passed price condition hurdle.")
        if not merchant_check(item, seller):
            log.debug("Failed merchant id condition hurdle.")
            continue
        log.debug("Passed merchant id condition hurdle.")

        # Returns first seller that passes condition checks
        return seller


def get_proxies(path=PROXY_FILE_PATH):
    """Initialize proxies from json configuration file"""
    proxies = []

    # TODO: verify format of json?
    if os.path.exists(path):
        proxy_json = json.load(open(path))
        proxies = proxy_json.get("proxies", [])

    return proxies

    # def verify(self):
    #     log.debug("Verifying item list...")
    #     items_to_purge = []
    #     verified = 0
    #     item_cache_file = os.path.join(
    #         os.path.dirname(os.path.abspath("__file__")),
    #         "stores",
    #         "store_data",
    #         "item_cache.p",
    #     )
    #
    #     if os.path.exists(item_cache_file) and os.path.getsize(item_cache_file) > 0:
    #         item_cache = pickle.load(open(item_cache_file, "rb"))
    #     else:
    #         item_cache = {}
    #
    #     for idx, item in enumerate(self.item_list):
    #         # Check the cache first to save the scraping...
    #         if item.id in item_cache.keys():
    #             cached_item = item_cache[item.id]
    #             log.debug(f"Verifying ASIN {cached_item.id} via cache  ...")
    #             # Update attributes that may have been changed in the config file
    #             cached_item.pdp_url = item.pdp_url
    #             cached_item.condition = item.condition
    #             cached_item.min_price = item.min_price
    #             cached_item.max_price = item.max_price
    #             cached_item.merchant_id = item.merchant_id
    #             self.item_list[idx] = cached_item
    #             log.debug(
    #                 f"Verified ASIN {cached_item.id} as '{cached_item.short_name}'"
    #             )
    #             verified += 1
    #             continue
    #
    #         # Verify that the ASIN hits and that we have a valid inventory URL
    #         item.pdp_url = f"https://{self.amazon_domain}{PDP_PATH}{item.id}"
    #         log.debug(f"Verifying at {item.pdp_url} ...")
    #
    #         session = self.session_checkout
    #         data, status = self.get_html(item.pdp_url, s=session)
    #         if not data and not status:
    #             log.debug("Response empty, skipping item")
    #             continue
    #         if status == 503:
    #             # Check for CAPTCHA
    #             tree = parse_html_source(data)
    #             if tree is None:
    #                 continue
    #             captcha_form_element = tree.xpath(
    #                 "//form[contains(@action,'validateCaptcha')]"
    #             )
    #             if captcha_form_element:
    #                 # Solving captcha and resetting data
    #                 data, status = solve_captcha(
    #                     session, captcha_form_element[0], item.pdp_url
    #                 )
    #
    #         if status == 200:
    #             item.furl = furl(
    #                 f"https://{self.amazon_domain}/{REALTIME_INVENTORY_PATH}{item.id}"
    #             )
    #             tree = parse_html_source(data)
    #             if tree is None:
    #                 continue
    #             captcha_form_element = tree.xpath(
    #                 "//form[contains(@action,'validateCaptcha')]"
    #             )
    #             if captcha_form_element:
    #                 data, status = solve_captcha(
    #                     session, captcha_form_element[0], item.pdp_url
    #                 )
    #                 if status != 200:
    #                     log.debug(f"ASIN {item.id} failed, skipping...")
    #                     continue
    #                 tree = parse_html_source(data)
    #                 if tree is None:
    #                     continue
    #
    #             title = tree.xpath('//*[@id="productTitle"]')
    #             if len(title) > 0:
    #                 item.name = title[0].text.strip()
    #                 item.short_name = (
    #                     item.name[:40].strip() + "..."
    #                     if len(item.name) > 40
    #                     else item.name
    #                 )
    #                 log.debug(f"Verified ASIN {item.id} as '{item.short_name}'")
    #                 item_cache[item.id] = item
    #                 verified += 1
    #             else:
    #                 # TODO: Evaluate if this happens with a 200 code
    #                 doggo = tree.xpath("//img[@alt='Dogs of Amazon']")
    #                 if doggo:
    #                     # Bad ASIN or URL... dump it
    #                     log.error(
    #                         f"Bad ASIN {item.id} for the domain or related failure.  Removing from hunt."
    #                     )
    #                     items_to_purge.append(item)
    #                 else:
    #                     log.debug(
    #                         f"Unable to verify ASIN {item.id}.  Continuing without verification."
    #                     )
    #         else:
    #             log.error(
    #                 f"Unable to locate details for {item.id} at {item.pdp_url}.  Removing from hunt."
    #             )
    #             items_to_purge.append(item)
    #
    #     # Purge any items we didn't find while verifying
    #     for item in items_to_purge:
    #         self.item_list.remove(item)
    #
    #     log.debug(
    #         f"Verified {verified} out of {len(self.item_list)} items on {STORE_NAME}"
    #     )
    #     pickle.dump(item_cache, open(item_cache_file, "wb"))
    #
    #     return True
