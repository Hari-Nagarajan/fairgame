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
import os
import aiohttp
from typing import Optional, List


import time
from datetime import datetime

import psutil
import requests
from chromedriver_py import binary_path
from lxml import html
from selenium import webdriver

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC, wait
from selenium.webdriver.support.expected_conditions import staleness_of
from selenium.webdriver.support.ui import WebDriverWait

from utils.logger import log
from utils.selenium_utils import enable_headless

DEFAULT_MAX_TIMEOUT = 5


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
        exit(1)


def selenium_initialization(
    options, profile_path, no_image=False, slow_mode=True, headless=False
):
    if headless:
        enable_headless()
    prefs = get_prefs()
    set_options(options=options, profile_path=profile_path, prefs=prefs)
    modify_browser_profile()


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


def set_options(options, profile_path, prefs, slow_mode=True):
    options.add_experimental_option("prefs", prefs)
    options.add_argument(f"user-data-dir={profile_path}")
    if not slow_mode:
        options.set_capability("pageLoadStrategy", "none")


def get_prefs(no_image=False):
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
