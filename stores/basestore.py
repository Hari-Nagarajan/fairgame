import time
from datetime import datetime

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.webdriver import WebDriver
from notifications.notifications import NotificationHandler
from utils.logger import log


class BaseStoreHandler:
    notification_handler: NotificationHandler
    driver: WebDriver

    def login(self):
        pass

    def parse_config(self):
        pass

    def run(self):
        pass

    def check_stock(self, item):
        pass

    @staticmethod
    def get_elapsed_time(start_time):
        return int(time.time()) - start_time

    def send_notification(self, message, page_name, take_screenshot=True):
        """Sends a notification to registered agents """
        if take_screenshot:
            file_name = save_screenshot(self.driver, page_name)
            self.notification_handler.send_notification(message, file_name)
        else:
            self.notification_handler.send_notification(message)


def save_screenshot(webdriver, page):
    file_name = get_timestamp_filename("screenshots/screenshot-" + page, ".png")
    try:
        webdriver.save_screenshot(file_name)
        return file_name
    except TimeoutException:
        log.info("Timed out taking screenshot, trying to continue anyway")
        pass
    except Exception as e:
        log.error(f"Trying to recover from error: {e}")
        pass
    return None


def get_timestamp_filename(name, extension):
    """Utility method to create a filename with a timestamp appended to the root and before
    the provided file extension"""
    now = datetime.now()
    date = now.strftime("%m-%d-%Y_%H_%M_%S")
    if extension.startswith("."):
        return name + "_" + date + extension
    else:
        return name + "_" + date + "." + extension
