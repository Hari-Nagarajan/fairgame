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

import stdiomask
import fileinput
import os
import platform
import time
import typing
from contextlib import contextmanager
from datetime import datetime
import queue
import asyncio
import aiohttp
from typing import Optional, List

import secrets
import re

import psutil
import requests
from amazoncaptcha import AmazonCaptcha
from chromedriver_py import binary_path
from furl import furl
from lxml import html
from price_parser import parse_price, Price
from selenium import webdriver
from utils.debugger import debug, timer

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

from notifications.notifications import NotificationHandler
from stores.basestore import BaseStoreHandler
from utils.logger import log
from utils.selenium_utils import (
    enable_headless,
    options,
    get_cookies,
    save_screenshot,
    selenium_initialization,
    create_driver,
)

from common.amazon_support import SellerDetail, has_captcha
from utils.misc import (
    check_response,
    parse_html_source,
    join_xpaths,
    wait_for_element_by_xpath,
    save_html_response,
    get_timestamp_filename,
    get_webdriver_pids,
)

from functools import wraps

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
STORE_NAME = "Amazon"
DEFAULT_MAX_TIMEOUT = 10

# Request
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, sdch, br",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36",
    "content-type": "application/x-www-form-urlencoded",
}


class AmazonCheckoutHandler(BaseStoreHandler):
    def __init__(
        self,
        notification_handler: NotificationHandler,
        amazon_config,
        profile_path,
        headless=False,
        username=None,
        password=None,
        timer=7200,
        cookie_list=None,
    ):
        log.debug("Initializing AmazonCheckoutHandler")
        self.profile_path = profile_path
        # Set up the Chrome options based on user flags
        if headless:
            enable_headless()
        self.amazon_config = amazon_config
        self.notification_handler = notification_handler

        # Selenium setup
        selenium_initialization(options=options, profile_path=self.profile_path)
        self.homepage_titles = amazon_config["HOME_PAGE_TITLES"]
        self.time_interval = timer
        self.cookie_list = cookie_list

        self.checkout_session = aiohttp.ClientSession()

    def pull_cookies(self):
        # Spawn the web browser
        self.driver = create_driver(options)
        self.webdriver_child_pids = get_webdriver_pids(self.driver)
        # Get a valid amazon session for our requests
        self.login()

        time.sleep(2)
        cookies = get_cookies(self.driver, cookie_list=self.cookie_list)
        self.delete_driver()

        return cookies

    def login(self):
        domain = "smile.amazon.com"
        log.info(f"Logging in to {domain}...")

        amazonsmile_url = "https://smile.amazon.com/ap/signin/ref=smi_ge2_ul_si_rl?_encoding=UTF8&ie=UTF8&openid.assoc_handle=amzn_smile&openid.claimed_id=http://specs.openid.net/auth/2.0/identifier_select&openid.identity=http://specs.openid.net/auth/2.0/identifier_select&openid.mode=checkid_setup&openid.ns=http://specs.openid.net/auth/2.0&openid.ns.pape=http://specs.openid.net/extensions/pape/1.0&openid.pape.max_auth_age=0&openid.return_to=https://smile.amazon.com/gp/charity/homepage.html?ie=UTF8&newts=1&orig=%2F"
        amazoncom_url = "https://www.amazon.com/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.com%2F%3Fref_%3Dnav_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=usflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0&"
        email_field: Optional[WebElement] = None
        remember_me: Optional[WebElement] = None
        password_field: Optional[WebElement] = None

        if "smile" in domain:
            url = amazonsmile_url
        else:
            url = amazoncom_url

        self.driver.get(url=url)

        log.debug("Inputting email...")
        email_field = self.get_amazon_element("EMAIL_TEXT_FIELD")
        if not email_field:
            log.debug("email field not found")
        else:
            # Entering in email field
            with self.wait_for_page_content_change():
                try:
                    email_field.clear()
                    email_field.send_keys(self.amazon_config["username"] + Keys.RETURN)
                except WebDriverException as e:
                    log.debug("Could not interact with email field")
                    log.debug(e)
            if self.driver.find_elements_by_xpath(
                '//input[@id="auth-error-message-box"]'
            ):
                log.error("Login failed, delete your credentials file")
                time.sleep(240)
                exit(1)

        log.debug("Checking 'rememberMe' checkbox...")
        remember_me = self.wait_get_clickable_amazon_element("LOGIN_REMEMBER_ME")
        if remember_me:
            try:
                remember_me.click()
            except WebDriverException as e:
                log.debug("Could not click remember me checkbox")
        else:
            log.error("Remember me checkbox did not exist")

        log.info("Inputting Password")
        captcha_entry: Optional[WebElement] = None
        password_field = self.wait_get_amazon_element("PASSWORD_TEXT_FIELD")

        if not password_field:
            log.debug("No password field")

        try:
            password_field.clear()
            password_field.send_keys(self.amazon_config["password"])
        except WebDriverException as e:
            log.debug("Password field entry error")

        captcha_entry = self.get_amazon_element("LOGIN_CAPTCHA_TEXT_FIELD")
        if captcha_entry:
            try:
                log.debug("Stuck on a captcha... Lets try to solve it.")
                captcha = AmazonCaptcha.fromdriver(self.driver)
                solution = captcha.solve()
                log.debug(f"The solution is: {solution}")
                if solution == "Not solved":
                    log.debug(
                        f"Failed to solve {captcha.image_link}, lets reload and get a new captcha."
                    )
                    self.send_notification("Unsolved Captcha", "unsolved_captcha")
                    self.driver.refresh()
                else:
                    self.send_notification("Solving catpcha", "captcha")
                    with self.wait_for_page_content_change(timeout=10):
                        captcha_entry.clear()
                        captcha_entry.send_keys(solution)
            except Exception as e:
                log.debug(e)
                log.debug("Error trying to solve captcha. User Intervention Required.")
                with self.wait_for_page_content_change(timeout=300):
                    pass

        with self.wait_for_page_content_change(timeout=10):
            try:
                password_field.send_keys(Keys.RETURN)
            except WebDriverException:
                pass

        # Deal with 2FA
        if self.driver.title in self.amazon_config["TWOFA_TITLES"]:
            otp_select = self.get_amazon_element("OTP_DEVICE")
            if otp_select:
                log.info("OTP choice selection, trying to check TOTP (app) option")
                totp_select = self.wait_get_clickable_amazon_element("OTP_TOTP")
                if totp_select:
                    try:
                        totp_select.click()
                    except WebDriverException:
                        log.debug("Could not click totp selection")

                topt_advance = self.wait_get_clickable_amazon_element(
                    "OTP_DEVICE_SELECT"
                )
                if topt_advance:
                    if not self.do_button_click(topt_advance):
                        with self.wait_for_page_content_change(timeout=300):
                            log.warning("USER INTERVENTION REQUIRED")

            self.notification_handler.play_notify_sound()
            self.send_notification(
                "Bot requires OTP input, please see console and/or browser window!",
                "otp-page",
            )
            otp_field = self.wait_get_amazon_element("OTP_FIELD")
            if otp_field:
                log.info("OTP Remember me checkbox")
                remember_device = self.wait_get_clickable_amazon_element(
                    "OTP_REMEMBER_ME"
                )
                if remember_device:
                    try:
                        remember_device.click()
                    except WebDriverException:
                        log.error("OTP Remember me checkbox could not be clicked")
                otp = stdiomask.getpass(
                    prompt="enter in your two-step verification code: ", mask="*"
                )
                with self.wait_for_page_content_change():
                    otp_field.send_keys(otp + Keys.RETURN)
                time.sleep(2)
                if self.driver.title in self.amazon_config["TWOFA_TITLES"]:
                    log.error("Something went wrong, please check browser manually...")
                while self.driver.title in self.amazon_config["TWOFA_TITLES"]:
                    time.sleep(2)
            else:
                log.error("OTP entry box did not exist, please fill in OTP manually...")
                while self.driver.title in self.amazon_config["TWOFA_TITLES"]:
                    # Wait for the user to enter 2FA
                    time.sleep(2)

        # Should be on home page now, if not, there is a problem
        if self.driver.title not in self.amazon_config["HOME_PAGE_TITLES"]:
            log.warning("Problem With Login, User Intervention Required")
            self.send_notification("Problem with login", "login-issue")
            DOTS = [".", "..", "..."]
            idx = 0
            while self.driver.title not in self.amazon_config["HOME_PAGE_TITLES"]:
                print(
                    "Waiting for homepage, user input may be required",
                    DOTS[idx],
                    end="\r",
                )
                idx = (idx + 1) % len(DOTS)
                time.sleep(0.5)
            print("", end="\r")
        log.info(f'Logged in as {self.amazon_config["username"]}')

    def delete_driver(self):
        try:
            self.driver.quit()
            if platform.system() == "Windows" and self.driver:
                log.debug("Cleaning up after web driver...")
                # brute force kill child Chrome pids with fire
                for pid in self.webdriver_child_pids:
                    try:
                        log.debug(f"Killing {pid}...")
                        process = psutil.Process(pid)
                        process.kill()
                    except psutil.NoSuchProcess:
                        log.debug(f"{pid} not found. Continuing...")
                        pass

        except Exception as e:
            log.debug(e)
            log.debug(
                "Failed to clean up after web driver.  Please manually close browser."
            )
            return False
        return True

    def do_button_click(
        self,
        button,
        clicking_text="Clicking button",
        clicked_text="Button clicked",
        fail_text="Could not click button",
    ):
        try:
            with self.wait_for_page_content_change():
                log.debug(clicking_text)
                button.click()
                log.debug(clicked_text)
            return True
        except WebDriverException as e:
            log.debug(fail_text)
            log.debug(e)
            return False

    def wait_get_amazon_element(self, key):
        """Waits for element called by XPATHS key in fairgame.conf. Returns None if no element found by timeout"""
        xpath = join_xpaths(self.amazon_config["XPATHS"][key])
        if wait_for_element_by_xpath(self.driver, xpath):
            return self.get_amazon_element(key=key)
        else:
            return None

    def wait_get_clickable_amazon_element(self, key):
        xpath = join_xpaths(self.amazon_config["XPATHS"][key])
        if wait_for_element_by_xpath(self.driver, xpath):
            try:
                return WebDriverWait(self.driver, timeout=5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
            except TimeoutException:
                return None
        else:
            return None

    def wait_get_amazon_elements(self, key):
        xpath = join_xpaths(self.amazon_config["XPATHS"][key])
        if wait_for_element_by_xpath(self.driver, xpath):
            return self.get_amazon_elements(key=key)
        else:
            return None

    def get_amazon_element(self, key):
        try:
            return self.driver.find_element_by_xpath(
                join_xpaths(self.amazon_config["XPATHS"][key])
            )
        except NoSuchElementException:
            return None

    def get_amazon_elements(self, key):
        return self.driver.find_elements_by_xpath(
            join_xpaths(self.amazon_config["XPATHS"][key])
        )

    def get_page(self, url):
        try:
            with self.wait_for_page_content_change():
                self.driver.get(url=url)
            return True
        except TimeoutException:
            log.debug("Failed to load page within timeout period")
            return False
        except Exception as e:
            log.debug(f"Other error encountered while loading page: {e}")

    async def checkout_worker(self, queue: asyncio.Queue, login_interval=7200):
        log.debug("Checkout Task Started")
        log.debug("Logging in and pulling cookies from Selenium")
        cookies = self.pull_cookies()
        log.debug("Cookies from Selenium:")
        for cookie in cookies:
            log.debug(f"{cookie}: {cookies[cookie]}")
        session = aiohttp.ClientSession(
            headers=HEADERS, cookies={cookie: cookies[cookie] for cookie in cookies}
        )
        domain = "smile.amazon.com"
        resp = await session.get(f"https://{domain}")
        html_text = await resp.text()
        save_html_response("session-get", resp.status, html_text)
        selenium_refresh_time = time.time() + login_interval  # not used yet
        while True:
            log.debug("Checkout task waiting for item in queue")
            qualified_seller = await queue.get()
            queue.task_done()
            if not qualified_seller:
                continue
            start_time = time.time()
            TURBO_INITIATE_MAX_RETRY = 50
            retry = 0
            pid = None
            anti_csrf = None
            while (not (pid and anti_csrf)) and retry < TURBO_INITIATE_MAX_RETRY:
                pid, anti_csrf = await turbo_initiate(
                    s=session, qualified_seller=qualified_seller
                )
                retry += 1
            if pid and anti_csrf:
                if await turbo_checkout(s=session, pid=pid, anti_csrf=anti_csrf):
                    log.info("Maybe completed checkout")
                    time_difference = time.time() - start_time
                    log.info(
                        f"Time from stock found to checkout: {round(time_difference,2)} seconds."
                    )
                    try:
                        status, text = await aio_get(
                            session,
                            f"https://{domain}/gp/buy/thankyou/handlers/display.html?_from=cheetah&checkMFA=1&purchaseId={pid}&referrer=yield&pid={pid}&pipelineType=turbo&clientId=retailwebsite&temporaryAddToCart=1&hostPage=detail&weblab=RCX_CHECKOUT_TURBO_DESKTOP_PRIME_87783",
                        )
                        save_html_response("order-confirm", status, text)
                    except aiohttp.ClientError:
                        log.debug("could not save order confirmation page")
                    await session.close()
                    break

    @contextmanager
    def wait_for_page_content_change(self, timeout=5):
        """Utility to help manage selenium waiting for a page to load after an action, like a click"""
        old_page = self.driver.find_element_by_tag_name("html")
        yield
        try:
            WebDriverWait(self.driver, timeout).until(EC.staleness_of(old_page))
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, "//title"))
            )
        except TimeoutException:
            log.info("Timed out reloading page, trying to continue anyway")
            pass
        except Exception as e:
            log.error(f"Trying to recover from error: {e}")
            pass
        return None

    def send_notification(self, message, page_name, take_screenshot=True):
        """Sends a notification to registered agents """
        if take_screenshot:
            file_name = save_screenshot(self.driver, page_name)
            self.notification_handler.send_notification(message, file_name)
        else:
            self.notification_handler.send_notification(message)


@timer
async def aio_post(client, url, data=None):
    async with client.post(url=url, data=data) as resp:
        text = await resp.text()
        return resp.status, text


@timer
async def aio_get(client, url, data=None):
    async with client.get(url=url, data=data) as resp:
        text = await resp.text()
        return resp.status, text


@timer
async def turbo_initiate(
    s: aiohttp.ClientSession, qualified_seller: Optional[SellerDetail] = None
):
    domain = "smile.amazon.com"
    url = f"https://{domain}/checkout/turbo-initiate?ref_=dp_start-bbf_1_glance_buyNow_2-1&pipelineType=turbo&weblab=RCX_CHECKOUT_TURBO_DESKTOP_NONPRIME_87784&temporaryAddToCart=1"
    pid = None
    anti_csrf = None

    if not qualified_seller:
        log.info("qualified seller not provided")
        return pid, anti_csrf
    payload_inputs = {
        "offerListing.1": qualified_seller.offering_id,
        "quantity.1": "1",
    }
    retry = 0
    MAX_RETRY = 5
    captcha_element = True  # to initialize loop
    status, text = await aio_post(client=s, url=url, data=payload_inputs)
    save_html_response("turbo-initiate", status, text)
    tree: Optional[html.HtmlElement] = None
    while retry < MAX_RETRY and captcha_element:
        tree = check_response(text)
        if tree is None:
            return pid, anti_csrf
        if captcha_element := has_captcha(tree):
            log.debug("Found captcha")
            text = await async_captcha_solve(s, captcha_element, domain)
            if text is None:
                return pid, anti_csrf
            retry += 1

    find_pid = re.search(r"pid=(.*?)&amp;", text)
    if find_pid:
        pid = find_pid.group(1)
    find_anti_csrf = re.search(r"'anti-csrftoken-a2z' value='(.*?)'", text)
    if find_anti_csrf:
        anti_csrf = find_anti_csrf.group(1)
    if pid and anti_csrf:
        log.debug("turbo-initiate successful")
        return pid, anti_csrf
    log.debug("turbo-initiate unsuccessful")
    save_html_response(
        filename="turbo_ini_unsuccessful", status=000, body=tree.text_content()
    )
    return pid, anti_csrf


@timer
async def turbo_checkout(s: aiohttp.ClientSession, pid, anti_csrf):
    domain = "smile.amazon.com"
    log.debug("trying to checkout")
    url = f"https://{domain}/checkout/spc/place-order?ref_=chk_spc_placeOrder&clientId=retailwebsite&pipelineType=turbo&pid={pid}"
    header_update = {"anti-csrftoken-a2z": anti_csrf}
    s.headers.update(header_update)

    status, text = await aio_post(client=s, url=url)
    save_html_response("turbo_checkout", status, text)
    if status == 200 or status == 500:
        log.debug("Checkout maybe successful, check order page!")
        # TODO: Implement GET request to confirm checkout
        return True

    log.debug(f"Status Code: {status} was returned")
    return False


async def async_captcha_solve(s: aiohttp.ClientSession, captcha_element, domain):
    log.debug("Encountered CAPTCHA. Attempting to solve.")
    # Starting from the form, get the inputs and image
    captcha_images = captcha_element.xpath(
        '//img[contains(@src, "amazon.com/captcha/")]'
    )
    text = None
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
            status, text = await aio_get(client=s, url=f.url)
    return text
