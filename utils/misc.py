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
from typing import Optional, List

import time
import os.path
import json
from datetime import datetime
from itertools import cycle

import psutil
import requests

from lxml import html
from selenium import webdriver

from selenium.common.exceptions import (
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils.logger import log


DEFAULT_MAX_TIMEOUT = 5


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


def get_timeout(timeout=DEFAULT_MAX_TIMEOUT):
    return time.time() + timeout


def wait_for_element_by_xpath(d, xpath, timeout=10):
    try:
        WebDriverWait(d, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
    except TimeoutException:
        log.debug(f"failed to find {xpath}")
        return False

    return True


def join_xpaths(xpath_list, separator=" | "):
    return separator.join(xpath_list)


def get_timestamp_filename(name, extension):
    """Utility method to create a filename with a timestamp appended to the root and before
    the provided file extension"""
    now = datetime.now()
    date = now.strftime("%m-%d-%Y_%H_%M_%S")
    if extension.startswith("."):
        return name + "_" + date + extension
    else:
        return name + "_" + date + "." + extension


def transfer_selenium_cookies(
    d: webdriver.Chrome, s: requests.Session, cookie_list: Optional[List[str]] = None
):
    """Utility to transfer cookies from a Selenium webdriver session to a Requests session"""
    # get cookies, might use these for checkout later, with no cookies on
    # cookie_names = ["session-id", "ubid-main", "x-main", "at-main", "sess-at-main"]
    # for c in self.driver.get_cookies():
    #     if c["name"] in cookie_names:
    #         self.amazon_cookies[c["name"]] = c["value"]

    # update session with cookies from Selenium
    all_cookies = False
    if cookie_list is None:
        all_cookies = True
    # cookie_names = ["session-id", "ubid-main", "x-main", "at-main", "sess-at-main"]
    for c in d.get_cookies():
        if all_cookies or c["name"] in cookie_list:
            s.cookies.set(name=c["name"], value=c["value"])
            log.dev(f'Set Cookie {c["name"]} as value {c["value"]}')


def save_html_response(filename, status, body):
    """Saves response body"""
    file_name = get_timestamp_filename(
        "html_saves/" + filename + "_" + str(status) + "_requests_source", "html"
    )
    if body is None:
        body = ""
    page_source = body
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(page_source)


def check_response(response_text):
    if response_text is None:
        return None
    # Check response text is valid
    payload = str(response_text)
    if payload is None or len(payload) == 0:
        log.debug("Empty response")
        return None
    log.debug(f"payload is {len(payload)} bytes")
    # Get parsed html, if there is an error during parsing, it will return None.
    return parse_html_source(payload)


def parse_html_source(data):
    tree = None
    try:
        tree = html.fromstring(data)
    except html.etree.ParserError:
        log.debug("html parser error")
    return tree


class UserAgentBook:
    def __init__(self, fp="config/user_agents.json"):
        self.fp = fp
        self.user_agents = dict()
        if os.path.exists(fp):
            with open(fp) as f:
                self.user_agents = json.load(f)

    def save(self):
        with open(self.fp, "w") as f:
            json.dump(self.user_agents, f, indent=4)


class ItemsHandler:
    @classmethod
    def create_items_pool(cls, item_list):
        cls.item_ids = {}
        for item in item_list:
            cls.item_ids.update({item.id: time.time()})
        cls.items = cycle(item_list)

    @classmethod
    def pop(cls):
        return next(cls.items)

    @classmethod
    def check_last_access(cls, item):
        last_access = cls.item_ids[item.id]
        difference = time.time() - last_access
        if difference < 1:
            return True
        cls.item_ids.update({item.id: time.time()})
        return False


class BadProxyCollector:
    @classmethod
    def start(cls):
        cls.last_save = time.time()
        cls.collection = set()

    @classmethod
    def record(cls, status, connector):
        url = str(connector.proxy_url)
        if status == 503:
            cls.collection.add(url)
        if status == 200 and url in cls.collection:
            cls.collection.discard(url)

    @classmethod
    def save(cls):
        if cls.collection:
            with open(BAD_PROXIES_PATH, "w") as f:
                temp = list(cls.collection)
                json.dump(temp, f, indent=4)
            cls.last_save = time.time()

    @classmethod
    def timer(cls):
        if time.time() - cls.last_save >= 300:
            return True
        return False
