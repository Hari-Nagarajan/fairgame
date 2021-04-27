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


import fileinput
import json
import os
import pickle
import platform
import random

import stdiomask
import time
import typing
from contextlib import contextmanager
from datetime import datetime
from utils.debugger import debug
import secrets
from fake_useragent import UserAgent

import re

import psutil
import requests
from furl import furl
from lxml import html
from price_parser import parse_price, Price
from typing import Optional

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
from typing import NamedTuple
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


class AmazonMonitoring(BaseStoreHandler):
    http_client = False
    http_20_client = False
    http_session = True

    def __init__(
        self,
        asin_list,
        notification_handler: NotificationHandler,
        loop: asyncio.BaseEventLoop,
        domain="smile.amazon.com",
        tasks=1,
        checkshipping=False,
        random_user_agent=False,
    ) -> None:
        super().__init__()

        self.shuffle = True

        self.notification_handler = notification_handler
        self.check_shipping = checkshipping
        self.item_list: typing.List[FGItem] = []
        self.stock_checks = 0
        self.start_time = int(time.time())
        self.amazon_domain = domain
        self.webdriver_child_pids = []
        self.amazon_cookies = {}
        self.random_user_agent = random_user_agent

        if type(asin_list) != list:
            self.asin_list = [asin_list]
        else:
            self.asin_list = asin_list

        self.ua = UserAgent()

        # Initialize the Session we'll use for stock checking
        sessions_list = []
        for idx in range(tasks):
            sessions_list = requests.Session()

        self.session_stock_check = requests.Session()
        self.session_stock_check.headers.update(HEADERS)
        self.session_stock_check.headers.update({"user-agent": self.ua.random})
        # self.conn = http.client.HTTPSConnection(self.amazon_domain)
        # self.conn20 = HTTP20Connection(self.amazon_domain)

        # Initialize proxies for stock check session:
        self.initialize_proxies()

    def initialize_proxies(self):
        """Initialize proxies from json configuration file"""
        self.proxies = []
        self.proxy_sessions = []
        self.used_proxy_sessions = []

        if os.path.exists(PROXY_FILE_PATH):
            proxy_json = json.load(open(PROXY_FILE_PATH))
            self.proxies = proxy_json.get("proxies", [])

            # TODO: verify format of json?

            # initialize sessions for each proxy
            for proxy in self.proxies:
                s = requests.Session()
                s.headers.update(HEADERS)
                if self.random_user_agent:
                    s.headers.update({"user-agent": self.ua.random})
                s.proxies.update(proxy)

                self.proxy_sessions.append(s)

            random.shuffle(self.proxy_sessions)

            # initialize first 2 proxies with Amazon cookies
            for s in self.proxy_sessions[:2]:
                s.get(f"https://{self.amazon_domain}")
                time.sleep(1)

            log.info(f"Created {len(self.proxy_sessions)} proxy sessions")

    def get_stock_check_session(self):
        rval = self.session_stock_check
        if self.proxies:
            if not self.proxy_sessions:
                self.proxy_sessions = self.used_proxy_sessions
                self.used_proxy_sessions = []
                log.debug("Shuffling proxies...")

                # shuffle the two halves to maintain a large-ish delay
                # between 2 consecutive uses of the same proxy
                len_proxies = len(self.proxy_sessions)
                a = self.proxy_sessions[: len_proxies // 2]
                b = self.proxy_sessions[len_proxies // 2 :]
                random.shuffle(a)
                random.shuffle(b)
                self.proxy_sessions = a + b

            if self.proxy_sessions:
                rval = self.proxy_sessions.pop(0)
                self.used_proxy_sessions.append(rval)

        return rval

    @debug
    def find_qualified_seller(self, item) -> SellerDetail or None:
        item_sellers = self.get_item_sellers(item, amazon_config["FREE_SHIPPING"])
        if item_sellers:
            for seller in item_sellers:
                if not self.check_shipping and not free_shipping_check(seller):
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
                        )
                    )
            else:
                log.error(
                    f"Item isn't fully qualified.  Please include asin, min-price and max-price. {json_item}"
                )

    def get_real_time_data(self, item: FGItem, session: requests.Session):
        log.debug(f"Calling {STORE_NAME} for {item.short_name} using {item.furl.url}")
        if self.proxies:
            log.debug(f"Using proxy: {self.proxies[0]}")
        params = {"anticache": str(secrets.token_urlsafe(32))}
        item.furl.args.update(params)
        data, status = get_html(item.furl.url, s=session)

        if item.status_code != status:
            # Track when we flip-flop between status codes.  200 -> 204 may be intelligent caching at Amazon.
            # We need to know if it ever goes back to a 200
            log.warning(
                f"{item.short_name} started responding with Status Code {status} instead of {item.status_code}"
            )
            item.status_code = status
        return data

    @debug
    def get_item_sellers(self, item, free_shipping_strings):
        """Parse out information to from the aod-offer nodes populate ItemDetail instances for each item """
        session = self.get_stock_check_session()
        payload = self.get_real_time_data(item, session)
        sellers = []
        if payload is None or len(payload) == 0:
            log.error("Empty Response.  Skipping...")
            return sellers
        # This is where the parsing magic goes
        log.debug(f"payload is {len(payload)} bytes")

        tree = parse_html_source(payload)
        if tree is None:
            return sellers
        if item.status_code == 503:
            with open("503-page.html", "w", encoding="utf-8") as f:
                f.write(payload)
            log.info("Status Code 503, Checking for Captcha")
            # Check for CAPTCHA
            captcha_form_element = tree.xpath(
                "//form[contains(@action,'validateCaptcha')]"
            )
            if captcha_form_element:
                log.info("captcha found")
                url = f"https://{self.amazon_domain}/{REALTIME_INVENTORY_PATH}{item.id}"
                # Solving captcha and resetting data
                data, status = solve_captcha(session, captcha_form_element[0], url)
                if status != 503:
                    payload = data
                    tree = parse_html_source(payload)
                    if tree is None:
                        return sellers
                else:
                    log.info(f"No valid page for ASIN {item.id}")
                    return sellers
            else:
                log.info("captcha not found")

        # look for product ASIN
        page_asin = tree.xpath("//input[@id='ftSelectAsin']")
        if page_asin:
            try:
                found_asin = page_asin[0].value.strip()
            except (AttributeError, IndexError):
                found_asin = "[NO ASIN FOUND ON PAGE]"
        else:
            find_asin = re.search(r"asin\s?(?:=|\.)?\s?\"?([A-Z0-9]+)\"?", payload)
            if find_asin:
                found_asin = find_asin.group(1)
            else:
                found_asin = "[NO ASIN FOUND ON PAGE]"

        if found_asin != item.id:
            log.debug(
                f"Aborting Check, ASINs do not match. Found {found_asin}; Searching for {item.id}."
            )
            return None

        # Get all the offers (pinned and others)
        offers = tree.xpath(
            "//div[@id='aod-sticky-pinned-offer'] | //div[@id='aod-offer']"
        )

        # I don't really get the OR part of this, how could the first part fail, but the second part not fail?
        # if not pinned_offer or not tree.xpath(
        #     "//div[@id='aod-sticky-pinned-offer']//input[@name='submit.addToCart'] | //div[@id='aod-offer']//input[@name='submit.addToCart']"
        # ):
        #
        if not offers:
            log.debug(f"No offers for {item.id} = {item.short_name}")
        else:
            for idx, offer in enumerate(offers):
                try:
                    merchant_id = offer.xpath(
                        ".//input[@id='ftSelectMerchant' or @id='ddmSelectMerchant']"
                    )[0].value
                except IndexError:
                    try:
                        merchant_script = offer.xpath(".//script")[0].text.strip()
                        find_merchant_id = re.search(
                            r"merchantId = \"(\w+?)\";", merchant_script
                        )
                        if find_merchant_id:
                            merchant_id = find_merchant_id.group(1)
                        else:
                            log.debug("No Merchant ID found")
                            merchant_id = ""
                    except IndexError:
                        log.debug("No Merchant ID found")
                        merchant_id = ""
                try:
                    price_text = offer.xpath(".//span[@class='a-price-whole']")[
                        0
                    ].text.strip()
                except IndexError:
                    log.debug("No price found for this offer, skipping")
                    continue
                price = parse_price(price_text)
                shipping_cost = get_shipping_costs(offer, free_shipping_strings)
                condition_heading = offer.xpath(".//div[@id='aod-offer-heading']/h5")
                if condition_heading:
                    condition = AmazonItemCondition.from_str(
                        condition_heading[0].text.strip()
                    )
                else:
                    condition = AmazonItemCondition.Unknown
                offer_ids = offer.xpath(f".//input[@name='offeringID.1']")
                offer_id = None
                if len(offer_ids) > 0:
                    offer_id = offer_ids[0].value
                else:
                    log.error("No offer ID found for this offer, skipping")
                    continue
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


def parse_condition(condition: str) -> AmazonItemCondition:
    return AmazonItemCondition[condition]


def min_total_price(seller: SellerDetail):
    return seller.selling_price


def new_first(seller: SellerDetail):
    return seller.condition


def get_timestamp_filename(name, extension):
    """Utility method to create a filename with a timestamp appended to the root and before
    the provided file extension"""
    now = datetime.now()
    date = now.strftime("%m-%d-%Y_%H_%M_%S")
    if extension.startswith("."):
        return name + "_" + date + extension
    else:
        return name + "_" + date + "." + extension


def save_html_response(filename, status, body):
    """Saves response body"""
    file_name = get_timestamp_filename(
        "html_saves/" + filename + "_" + str(status) + "_requests_source", "html"
    )

    page_source = body
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(page_source)


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


def parse_html_source(data):
    tree = None
    try:
        tree = html.fromstring(data)
    except html.etree.ParserError:
        log.debug("html parser error")
    return tree


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


class Offers(NamedTuple):
    asin: str
    offerlistingid: str
    merchantid: str
    price: float
    timestamp: float
    __slots__ = ()

    def __str__(self):
        return f"ASIN: {self.asin}; offerListingId: {self.offerlistingid}; merchantId: {self.merchantid}; price: {self.price}"


class AmazonMonitor(aiohttp.ClientSession):
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.response: Optional[aiohttp.ClientResponse] = None

    async def stock_check(self, item: FGItem, check_furl: furl, delay: float = 5):
        # Do first response outside of while loop, so we can continue on captcha checks
        # and return to start of while loop with that response. Requires the next response
        # to be grabbed at end of while loop
        start_time = time.time()
        self.response = await self.get(url=check_furl.url)
        # Loop will only exit if a qualified seller is returned.
        while True:
            if tree := check_response(self.response):
                if captcha_element := has_captcha(tree):
                    # wait a second so it doesn't continuously hit captchas very quickly
                    # TODO: maybe track captcha hits so that it aborts after several?
                    await asyncio.sleep(1)
                    # get the next response after solving captcha and then continue to next loop iteration
                    self.response = await self.async_captcha_solve(captcha_element)
                    await wait_timer(start_time=start_time)
                    continue
                if tree is not None and (sellers := get_item_sellers(tree)):
                    qualified_seller = get_qualified_seller(item=item, sellers=sellers)
                    if qualified_seller:
                        return qualified_seller
            # failed to find seller. Wait a delay period then check again
            await wait_timer(start_time=start_time)
            self.response = await self.get(url=check_furl.url)

    async def async_captcha_solve(self, captcha_element):
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


async def wait_timer(start_time):
    if (wait_delay := time.time() - start_time) > 0:
        await asyncio.sleep(wait_delay)


def check_response(response: aiohttp.ClientResponse):
    # Check response text is valid
    payload = str(response.text())
    if payload is None or len(payload) == 0:
        log.debug("Empty response")
        return None
    log.debug(f"payload is {len(payload)} bytes")
    # Get parsed html, if there is an error during parsing, it will return None.
    return parse_html_source(payload)


@debug
def get_item_sellers(tree, item, free_shipping_strings):
    """Parse out information to from the aod-offer nodes populate ItemDetail instances for each item """
    response = response
    sellers = []
    if response.text() is None or len(response.text()) == 0:
        log.error("Empty Response.  Skipping...")
        return sellers
    # This is where the parsing magic goes
    log.debug(f"payload is {len(str(payload))} bytes")

    tree = parse_html_source(payload)
    if tree is None:
        return sellers
    if item.status_code == 503:
        with open("503-page.html", "w", encoding="utf-8") as f:
            f.write(payload)
        log.info("Status Code 503, Checking for Captcha")
        # Check for CAPTCHA
        captcha_form_element = tree.xpath("//form[contains(@action,'validateCaptcha')]")
        if captcha_form_element:
            log.info("captcha found")
            url = f"https://{self.amazon_domain}/{REALTIME_INVENTORY_PATH}{item.id}"
            # Solving captcha and resetting data
            data, status = solve_captcha(session, captcha_form_element[0], url)
            if status != 503:
                payload = data
                tree = parse_html_source(payload)
                if tree is None:
                    return sellers
            else:
                log.info(f"No valid page for ASIN {item.id}")
                return sellers
        else:
            log.info("captcha not found")

    # look for product ASIN
    page_asin = tree.xpath("//input[@id='ftSelectAsin']")
    if page_asin:
        try:
            found_asin = page_asin[0].value.strip()
        except (AttributeError, IndexError):
            found_asin = "[NO ASIN FOUND ON PAGE]"
    else:
        find_asin = re.search(r"asin\s?(?:=|\.)?\s?\"?([A-Z0-9]+)\"?", payload)
        if find_asin:
            found_asin = find_asin.group(1)
        else:
            found_asin = "[NO ASIN FOUND ON PAGE]"

    if found_asin != item.id:
        log.debug(
            f"Aborting Check, ASINs do not match. Found {found_asin}; Searching for {item.id}."
        )
        return None

    # Get all the offers (pinned and others)
    offers = tree.xpath("//div[@id='aod-sticky-pinned-offer'] | //div[@id='aod-offer']")

    # I don't really get the OR part of this, how could the first part fail, but the second part not fail?
    # if not pinned_offer or not tree.xpath(
    #     "//div[@id='aod-sticky-pinned-offer']//input[@name='submit.addToCart'] | //div[@id='aod-offer']//input[@name='submit.addToCart']"
    # ):
    #
    if not offers:
        log.debug(f"No offers for {item.id} = {item.short_name}")
    else:
        for idx, offer in enumerate(offers):
            try:
                merchant_id = offer.xpath(
                    ".//input[@id='ftSelectMerchant' or @id='ddmSelectMerchant']"
                )[0].value
            except IndexError:
                try:
                    merchant_script = offer.xpath(".//script")[0].text.strip()
                    find_merchant_id = re.search(
                        r"merchantId = \"(\w+?)\";", merchant_script
                    )
                    if find_merchant_id:
                        merchant_id = find_merchant_id.group(1)
                    else:
                        log.debug("No Merchant ID found")
                        merchant_id = ""
                except IndexError:
                    log.debug("No Merchant ID found")
                    merchant_id = ""
            try:
                price_text = offer.xpath(".//span[@class='a-price-whole']")[
                    0
                ].text.strip()
            except IndexError:
                log.debug("No price found for this offer, skipping")
                continue
            price = parse_price(price_text)
            shipping_cost = get_shipping_costs(offer, free_shipping_strings)
            condition_heading = offer.xpath(".//div[@id='aod-offer-heading']/h5")
            if condition_heading:
                condition = AmazonItemCondition.from_str(
                    condition_heading[0].text.strip()
                )
            else:
                condition = AmazonItemCondition.Unknown
            offer_ids = offer.xpath(f".//input[@name='offeringID.1']")
            offer_id = None
            if len(offer_ids) > 0:
                offer_id = offer_ids[0].value
            else:
                log.error("No offer ID found for this offer, skipping")
                continue
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


@debug
def get_qualified_seller(item, sellers, check_shipping=False) -> SellerDetail or None:
    item_sellers = sellers
    if item_sellers:
        for seller in item_sellers:
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
