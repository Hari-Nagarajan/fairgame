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
from chromedriver_py import binary_path
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.remote.remote_connection import LOGGER as selenium_logger
from selenium.common.exceptions import TimeoutException
from urllib3.connectionpool import log as urllib_logger
from logging import WARNING as logging_WARNING
from utils.misc import get_timestamp_filename
from utils.logger import log

options = Options()
options.add_experimental_option(
    "excludeSwitches", ["enable-automation", "enable-logging"]
)
options.add_experimental_option("useAutomationExtension", False)
# CHROME ONLY option to prevent Restore Session popup
options.add_argument("--disable-session-crashed-bubble")
selenium_logger.setLevel(logging_WARNING)
urllib_logger.setLevel(logging_WARNING)


class AnyEc:
    """Use with WebDriverWait to combine expected_conditions
    in an OR.
    """

    def __init__(self, *args):
        self.ecs = args

    def __call__(self, driver):
        for fn in self.ecs:
            try:
                if fn(driver):
                    return True
            except:
                pass


def wait_for_element(d, e_id, time=30):
    """
    Uses webdriver(d) to wait for page title(title) to become visible
    """
    return WebDriverWait(d, time).until(ec.presence_of_element_located((By.ID, e_id)))


def wait_for_element_by_xpath(d, e_path, time=30):
    return WebDriverWait(d, time).until(
        ec.presence_of_element_located((By.XPATH, e_path))
    )


def wait_for_element_by_class(d, e_class, time=30):
    """
    Uses webdriver(d) to wait for page title(title) to become visible
    """
    return WebDriverWait(d, time).until(
        ec.presence_of_element_located((By.CLASS_NAME, e_class))
    )


def wait_for_title(d, title, path):
    """
    Uses webdriver(d) to navigate to get(path) until it equals title(title)
    """
    while d.title != title:
        d.get(path)
        WebDriverWait(d, 1000)


def wait_for_page(d, title, time=30):
    """
    Uses webdriver(d) to wait for page title(title) to become visible
    """
    WebDriverWait(d, time).until(ec.title_is(title))


def wait_for_either_title(d, title1, title2, time=30):
    """
    Uses webdriver(d) to wait for page title(title1 or title2) to become visible
    """
    try:
        WebDriverWait(d, time).until(AnyEc(ec.title_is(title1), ec.title_is(title2)))
    except Exception:
        pass


def wait_for_any_title(d, titles, time=30):
    """
    Uses webdriver(d) to wait for page title(any in the list of titles) to become visible
    """
    WebDriverWait(d, time).until(AnyEc(*[ec.title_is(title) for title in titles]))


def button_click_using_xpath(d, xpath):
    """
    Uses webdriver(d) to click a button using an XPath(xpath)
    """
    button_menu = WebDriverWait(d, 10).until(
        ec.element_to_be_clickable((By.XPATH, xpath))
    )
    action = ActionChains(d)
    action.move_to_element(button_menu).pause(1).click().perform()


def field_send_keys(d, field, keys):
    """
    Uses webdriver(d) to fiend a field(field), clears it and sends keys(keys)
    """
    elem = d.find_element_by_name(field)
    elem.clear()
    elem.send_keys(keys)


def has_class(element, class_name):
    classes = element.get_attribute("class")

    return class_name in classes


def add_cookies_to_session_from_driver(driver, session):
    cookies = driver.get_cookies()

    [
        session.cookies.set_cookie(
            requests.cookies.create_cookie(
                domain=cookie["domain"],
                name=cookie["name"],
                value=cookie["value"],
            )
        )
        for cookie in cookies
    ]


def enable_headless():
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")


def disable_gpu():
    options.add_argument("--disable-gpu")


def get_cookies(d: webdriver.Chrome, cookie_list=None):
    cookies = {}
    for c in d.get_cookies():
        if cookie_list is None or c["name"] in cookie_list:
            cookies[c["name"]] = c["value"]
    return cookies


def save_screenshot(d, page):
    file_name = get_timestamp_filename("screenshots/screenshot-" + page, ".png")
    try:
        d.save_screenshot(file_name)
        return file_name
    except TimeoutException:
        log.info("Timed out taking screenshot, trying to continue anyway")
        pass
    except Exception as e:
        log.error(f"Trying to recover from error: {e}")
        pass
    return None


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
