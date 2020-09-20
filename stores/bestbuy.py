
import json
from time import sleep

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from notifications.notifications import NotificationHandler
from utils.json_utils import find_values
from utils.logger import log

DEFAULT_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.92 Safari/537.36",
}


class BestBuyHandler:
    def __init__(self, sku_id):
        self.notification_handler = NotificationHandler()
        self.sku_id = sku_id
        self.session = requests.Session()

        adapter = HTTPAdapter(
            max_retries=Retry(
                total=10,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"],
            )
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def run_item(self):
        while not self.in_stock():
            sleep(5)
        log.info(f"Item {self.sku_id} is in stock!")

    def in_stock(self):
        log.info("Checking stock")
        url = "https://www.bestbuy.com/api/tcfb/model.json?paths=%5B%5B%22shop%22%2C%22scds%22%2C%22v2%22%2C%22page%22%2C%22tenants%22%2C%22bbypres%22%2C%22pages%22%2C%22globalnavigationv5sv%22%2C%22header%22%5D%2C%5B%22shop%22%2C%22buttonstate%22%2C%22v5%22%2C%22item%22%2C%22skus%22%2C{}%2C%22conditions%22%2C%22NONE%22%2C%22destinationZipCode%22%2C%22%2520%22%2C%22storeId%22%2C%22%2520%22%2C%22context%22%2C%22cyp%22%2C%22addAll%22%2C%22false%22%5D%5D&method=get".format(
            self.sku_id
        )
        response = self.session.get(url, headers=DEFAULT_HEADERS)
        log.info(f"Stock check response code: {response.status_code}")
        try:
            response_json = response.json()
            item_json = find_values(json.dumps(response_json),'buttonStateResponseInfos')
            item_state = item_json[0][0]['buttonState']
            log.info(f"Item state is: {item_state}")
            if item_json[0][0]['skuId'] == self.sku_id and item_state == 'ADD_TO_CART':
                return True
            else:
                return False
        except Exception as e:
            log.warning("Error parsing json. Using string search to determine state.")
            log.info(response_json)
            log.error(e)
            if "ADD_TO_CART" in response.text:
                log.info("Item is in stock!")
                return True
            else:
                log.info("Item is out of stock")
                return False
