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
from typing import Optional, Iterable, NamedTuple, List
from datetime import datetime
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
)
from notifications.notifications import NotificationHandler
from stores.basestore import BaseStoreHandler
from utils.logger import log
import asyncio
import aiohttp

from functools import wraps

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
        loop: asyncio.AbstractEventLoop,
        item_list: List[FGItem],
        amazon_config,
        tasks=1,
        checkshipping=False,
    ) -> None:
        super().__init__()

        self.shuffle = True

        self.notification_handler = notification_handler
        self.check_shipping = checkshipping
        self.item_list: typing.List[FGItem] = []
        self.stock_checks = 0
        self.start_time = int(time.time())
        self.amazon_config = amazon_config
        self.ua = UserAgent()

        self.proxies = get_proxies(path=PROXY_FILE_PATH)

        # Initialize the Session we'll use for stock checking
        self.sessions_list: Optional[List[AmazonMonitor]] = []
        for idx in range(tasks):
            self.sessions_list.append(AmazonMonitor())
            self.sessions_list[idx].headers.update(HEADERS)
            self.sessions_list[idx].headers.update({"user-agent": self.ua.random})
            if self.proxies and idx < len(self.proxies):
                self.sessions_list[idx].assign_proxy(self.proxies[idx]["https"])
            self.sessions_list[idx].assign_item(item_list[idx % len(item_list)])
            self.sessions_list[idx].assign_config(self.amazon_config)

    def run_async(self, queue: asyncio.Queue):
        tasks = []
        for session in self.sessions_list:
            task = asyncio.create_task(session.stock_check(queue))
            tasks.append(task)
        return tasks


def parse_condition(condition: str) -> AmazonItemCondition:
    return AmazonItemCondition[condition]


def min_total_price(seller: SellerDetail):
    return seller.selling_price


def new_first(seller: SellerDetail):
    return seller.condition


def captcha_handler(session, page_source, domain):
    data = page_source
    status = 200
    tree = parse_html_source(data)
    if tree is None:
        data = None
        status = None
        return data, status
    CAPTCHA_RETRY = 5
    retry = 0
    # loop until no captcha in return page, or max captcha tries reached
    while (captcha_element := has_captcha(tree)) and (retry < CAPTCHA_RETRY):
        data, status = solve_captcha(
            session=session, form_element=captcha_element[0], domain=domain
        )
        tree = parse_html_source(data)
        if tree is None:
            data = None
            status = None
            return data, status
        retry += 1
    if captcha_element:
        data = None
        status = None
    return data, status


def has_captcha(tree):
    return tree.xpath("//form[contains(@action,'validateCaptcha')]")


def free_shipping_check(seller):
    if seller.shipping_cost.amount > 0:
        return False
    else:
        return True


@debug
def get_html(url, s: requests.Session):
    """Unified mechanism to get content to make changing connection clients easier"""
    f = furl(url)
    if not f.scheme:
        f.set(scheme="https")
    try:
        response = s.get(f.url, timeout=5)
    except requests.exceptions.RequestException as e:
        log.debug(e)
        log.debug("timeout on get_html")
        return None, None
    except Exception as e:
        log.debug(e)
        return None, None
    return response.text, response.status_code


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
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.response = None
        self.item_furl: Optional[furl] = None
        self.domain: str = ""
        self.proxy: str = ""
        self.delay: float = 5
        self.item: Optional[FGItem] = None
        self.amazon_config: dict() = {}

    def assign_config(self, azn_config):
        self.amazon_config = azn_config

    def assign_proxy(self, proxy: str = ""):
        self.proxy = proxy

    def assign_delay(self, delay: float = 5):
        self.delay = delay

    def assign_item(self, item: FGItem):
        self.item = item

    async def stock_check(self, queue: asyncio.Queue):
        # Do first response outside of while loop, so we can continue on captcha checks
        # and return to start of while loop with that response. Requires the next response
        # to be grabbed at end of while loop
        print("Monitoring Task Started")
        self.item_furl = self.item.furl
        self.domain = urlparse(self.item_furl.url).netloc
        delay = 5
        end_time = time.time() + delay
        r = await self.fetch(url=self.item_furl.url)
        check_count = 1
        # Loop will only exit if a qualified seller is returned.
        while True:
            print(f"Stock Check Count: {check_count}")
            tree = check_response(r)
            if tree is not None:
                if captcha_element := has_captcha(tree):
                    log.debug("Captcha found during monitoring task")
                    # wait a second so it doesn't continuously hit captchas very quickly
                    # TODO: maybe track captcha hits so that it aborts after several?
                    await asyncio.sleep(1)
                    # get the next response after solving captcha and then continue to next loop iteration
                    r = await self.async_captcha_solve(captcha_element[0], self.domain)
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
                        return
            # failed to find seller. Wait a delay period then check again
            log.debug("No offers found which meet product criteria")
            await wait_timer(end_time)
            end_time = time.time() + delay
            r = await self.fetch(url=self.item_furl.url)
            check_count += 1

    async def fetch(self, url):
        async with self.get(url) as resp:
            return await resp.text()

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
                response = await self.fetch(f.url)
                return response
        return None


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
