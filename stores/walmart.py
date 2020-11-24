import secrets
import time
import requests

from time import sleep
from os import path
from price_parser import parse_price

from chromedriver_py import binary_path  # this will get you the path variable
from furl import furl
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, SessionNotCreatedException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from utils import selenium_utils
from utils.json_utils import InvalidAutoBuyConfigException
from utils.logger import log
from utils.selenium_utils import options, enable_headless, wait_for_element
from price_parser import parse_price

API_KEY = '5998050db106e5e27fb04058d77854c9'  # Your 2captcha API KEY
site_key = '6Lcj-R8TAAAAABs3FrRPuQhLMbp5QrHsHufzLf7b'  # site-key, read the 2captcha docs on how to get this

WALMART_URLS = {
    "BASE_URL": "https://{domain}/",
    "CART_URL": "https://{domain}/cart",
    "OFFER_URL": "https://{domain}/",
}

CAPTCHA_URL = {
    "Verify your identity",
}

CHECKOUT_URL = "https://{domain}/checkout/#/fulfillment"

AUTOBUY_CONFIG_PATH = "walmart_config.json"

SIGN_IN_TITLES = [
    "Login",
    "Sign In",
]

HOME_PAGE_TITLES = [
    "Walmart.com | Save Money. Live Better.",
]

CHECKOUT_TITLES = [
    "Choose delivery or pickup",
]
ORDER_COMPLETE_TITLES = [
    "Walmart.com Thanks You",
]
ADD_TO_CART_TITLES = [
    "Item added to cart - Walmart.com"
]

class Walmart:
    def __init__(self, notification_handler, headless=False):
        self.notification_handler = notification_handler
        self.url_list = []
        self.reserve = []
        if headless:
            enable_headless()
        options.add_argument(f"user-data-dir=.profile-wmrt")
        try:
            self.driver = webdriver.Chrome(executable_path=binary_path, options=options)
            self.wait = WebDriverWait(self.driver, 5)
        except Exception as e:
            log.error(e)
            exit(1)
        if path.exists(AUTOBUY_CONFIG_PATH):
            with open(AUTOBUY_CONFIG_PATH) as json_file:
                try:
                    config = json.load(json_file)
                    self.username = config["username"]
                    self.password = config["password"]
                    self.civ = config["civ"]
                    self.url_groups = int(config["url_groups"])
                    self.walmart_website = config.get(
                        "walmart_website", "walmart.com"
                    )
                    for x in range(self.url_groups):
                        self.url_list.append(config[f"url_list_{x+1}"])
                        self.reserve.append(float(config[f"reserve_{x+1}"]))
                    # assert isinstance(self.url_list, list)
                except Exception:
                    log.error(
                        "walmart_config.json file not formatted properly: https://github.com/Hari-Nagarajan/nvidia-bot/wiki/Usage#json-configuration"
                    )
                    exit(0)
        else:
            log.error(
                "No config file found, see here on how to fix this: https://github.com/Hari-Nagarajan/nvidia-bot/wiki/Usage#json-configuration"
            )
            exit(0)

        for key in WALMART_URLS.keys():
            WALMART_URLS[key] = WALMART_URLS[key].format(domain=self.walmart_website)
        self.driver.get(WALMART_URLS["BASE_URL"])
        log.info("Waiting for home page.")
        if self.driver.title in CAPTCHA_URL:
                self.defeat_captcha(self.driver.current_url)
        if self.is_logged_in():
            log.info("Already logged in")
        else:
            log.info("Lets log in.")
            log.info("Wait for Sign In page")
            self.login()
            self.notification_handler.send_notification("Logged in and running", False)
            log.info("Waiting 5 seconds.")
            time.sleep(
                5
            )  # We can remove this once I get more info on the phone verification page.
    
    def is_logged_in(self):
        try:
            time.sleep(5)
            accountbutt = self.driver.find_element_by_xpath('/html/body/div[1]/div/div/div[1]/section/div[2]/div/div[3]/div[2]/div/div[2]/div[1]/button')
            accountbutt.click()
            signin = self.driver.find_element_by_xpath('/html/body/div[1]/div[1]/div/div[1]/section/div[3]/div[2]/div/div/div[1]/div/span').text
            log.info("Logged in account " + signin)
            log.info("Checking login")
            if signin == "Account":
                return False
            else:
                return True
        except Exception:
            return False

    def login(self):
    
        signin = self.driver.find_element_by_xpath('/html/body/div[1]/div/div/div[1]/section/div[3]/div[2]/div/div/div[2]/div/a[1]/div/span/div')
        signin.click()
        time.sleep(1)
 
        if self.driver.title == "Login":
            try:
                log.info("Email")
                self.driver.find_element_by_xpath('//*[@id="email"]').send_keys(
                    self.username + Keys.RETURN
                )
                log.info("Password")
                self.driver.find_element_by_xpath('//*[@id="password"]').send_keys(
                    self.password + Keys.RETURN
                )
                time.sleep(2)
            except:
                pass
        else:
            try:
                log.info("Email")
                self.driver.find_element_by_xpath('//*[@id="sign-in-email"]').send_keys(
                    self.username + Keys.RETURN
                )
                log.info("Password")
                self.driver.find_element_by_xpath('//*[@name="password"]').send_keys(
                    self.password + Keys.RETURN
                )
                time.sleep(2)
            except:
                pass
                
        if self.driver.find_elements_by_xpath('//*[@id="global-error"]'):
            log.error("Login failed, check your username in walmart_config.json")
            time.sleep(240)
            exit(1)
        log.info(f"Logged in as {self.username}")

    def run_item(self, delay=5, test=False):
        checkout_success = False
        while not checkout_success:
            pop_list = []
            for i in range(len(self.url_list)):
                for url in self.url_list[i]:
                    self.check_captcha(url)
                    checkout_success = self.check_stock(url, self.reserve[i])
                    if checkout_success:
                        log.info(f"Attempting to buy {url}")
                        if self.checkout(test=test):
                            log.info(f"bought {url}")
                            pop_list.append(url)
                            break
                        else:
                            log.info(f"checkout for {url} failed")
                            checkout_success = False
                    time.sleep(1)
            if pop_list:
                for url in pop_list:
                    for i in range(len(self.url_list)):
                        if url in self.url_list[i]:
                            self.url_list.pop(i)
                            self.reserve.pop(i)
                            break
            if self.url_list:  # keep bot going if additional URLs left
                checkout_success = False
                #log.info("Additional lists remaining, bot will continue")

    def check_captcha(self, url):
        if self.driver.title in CAPTCHA_URL:
                self.defeat_captcha(self.driver.current_url)
    
    def check_stock(self, url, reserve):
        log.info("Checking stock for items.")
        f = furl(WALMART_URLS["OFFER_URL"] + url)
        self.driver.get(f.url)
        self.check_captcha(url)
        try:
            element = self.check_exists_by_xpath("/html/body/div[1]/div[1]/div/div[2]/div/div[1]/div[1]/div[1]/div/div/div/div/div[3]/div[5]/div/div[3]/div/div[2]/div[2]/div[1]/section/div[1]/div[3]/button/span")
            str_price = self.driver.find_element_by_xpath('//*[@id="price"]')
            log.info("Found price " + str_price.text)
        except NoSuchElementException:
            return False
            
        if not element:
            log.info("Product not available")
            self.check_stock(url, reserve)
        
        price = parse_price(str_price.text)
        priceFloat = price.amount
        if priceFloat is None:
            log.error("Error reading price information on row.")
        elif priceFloat <= reserve:
            if element:
                log.info("Item in stock and under reserve!")
            log.info("Clicking add to cart")
            element.click()
            return True
        return False
        
    def check_exists_by_xpath(self, xpath):
        log.info("Testing XPath")
        try:
            xpathvar = self.driver.find_element_by_xpath(xpath)
        except NoSuchElementException:
            return False
        return xpathvar

    def wait_for_pages(self, page_titles, t=30):
        log.debug(f"wait_for_pages({page_titles}, {t})")
        try:
            title = selenium_utils.wait_for_any_title(self.driver, page_titles, t)
            if not title in page_titles:
                log.error(
                    "{} is not a recognized title, report to #tech-support or open an issue on github".format()
                )
            pass
        except Exception as e:
            log.debug(e)
            pass

    def wait_for_order_page(self):

        if self.driver.title in SIGN_IN_TITLES:
            log.info("Need to sign in again")
            self.login()

    def finalize_order_button(self, test, retry=0):
        button = ['/html/body/div[1]/div/div[1]/div/div[1]/div[3]/div/div/div[2]/div[1]/div[2]/div/div/div[2]/div/form/div/button']

        if button:
            log.info(f"Clicking Place Order")
            if not test:
                button.click()
            return

    def wait_for_order_completed(self, test):
        if not test:
            log.info(
                "This is not a test"
            )
        else:
            log.info(
                "This is a test, so we don't need to wait for the order completed page."
            )
    def defeat_captcha(self, url):
        
        s = requests.Session()
        
        # here we post site key to 2captcha to get captcha ID (and we parse it here too)
        captcha_id = s.post("https://2captcha.com/in.php?key={}&method=userrecaptcha&googlekey={}&pageurl={}".format(
            API_KEY, site_key, url)).text.split('|')[1] 
        log.info("Testing captcha id")
        log.info(captcha_id)
        # then we parse gresponse from 2captcha response
        recaptcha_answer = s.get(
            "http://2captcha.com/res.php?key={}&action=get&id={}".format(API_KEY, captcha_id)).text  
        log.info("Solving captcha...")
        sleep(15)
        while 'CAPCHA_NOT_READY' in recaptcha_answer:
            recaptcha_answer = s.get(
                "http://2captcha.com/res.php?key={}&action=get&id={}".format(API_KEY, captcha_id)).text
            sleep(5)
        if recaptcha_answer == "ERROR_CAPTCHA_UNSOLVABLE":
            self.defeat_captcha(url)
        recaptcha_answer = recaptcha_answer.split('|')[1]
        log.info(recaptcha_answer)
        
        log.info("Submitting Captcha")
        #self.driver.execute_script("document.getElementById('g-recaptcha-response').innerHTML = '{0}';".format(
        #    recaptcha_answer))
        callback_method = self.driver.find_element_by_class_name("g-recaptcha").get_attribute("data-callback")
        #log.info("waiting to execute Callback")
        #sleep(30)
        self.driver.execute_script("{0}(\"{1}\");".format(
            callback_method, recaptcha_answer))
        sleep(90)
        self.check_captcha(url)
        self.driver.execute_script("___grecaptcha_cfg_client[0].l.l.callback('{}')".format(g_response))
        return
    
    def checkout(self, test):
        # log.info("Clicking continue.")
        # self.driver.save_screenshot("screenshot.png")
        # self.notification_handler.send_notification("Starting Checkout", True)
        # self.driver.find_element_by_xpath('//input[@value="add"]').click()

        log.info("Waiting for Cart Page")
        self.driver.save_screenshot("screenshot.png")
        self.notification_handler.send_notification("Cart Page", True)

        log.info("Clicking checkout.")
        try:
            self.driver.find_element_by_xpath('/html/body/div[1]/div/div/div/div/div/div[1]/div/div[1]/div/div[2]/div/div/div/div/div[3]/div/div/div[2]/div[1]/div[2]/div').click()
            log.info("Waiting for order page")
            self.wait_for_order_page()
            log.info("Continuing to confirm product")
            self.driver.find_element_by_xpath('/html/body/div[1]/div/div[1]/div/div[1]/div[3]/div/div/div/div[1]/div/div[2]/div/div/div/div[3]/div/div/div[2]/button').click()
            time.sleep(5)
            log.info("Continuing to confirm address")
            self.driver.find_element_by_xpath('/html/body/div[1]/div/div[1]/div/div[1]/div[3]/div/div/div/div[2]/div[1]/div[2]/div/div/div/div[3]/div/div/div/div/div[3]/div[2]/button').click()
            time.sleep(5)
            log.info("Enter CIV")
            self.driver.find_element_by_xpath('//*[@id="cvv-confirm"]').send_keys(
                    self.civ
            )
            log.info("Clicking Review Order")
            self.driver.find_element_by_xpath('/html/body/div[1]/div/div[1]/div/div[1]/div[3]/div/div/div/div[3]/div[1]/div[2]/div/div/div/div[3]/div[2]/div/button').click()
            time.sleep(3)
        except:
            self.driver.save_screenshot("screenshot.png")
            self.notification_handler.send_notification("Failed to checkout. Returning to stock check.", True)
            log.info("Failed to checkout. Returning to stock check.")
            return False

        log.info("Finishing checkout")
        self.driver.save_screenshot("screenshot.png")
        self.notification_handler.send_notification("Finishing checkout", True)

        self.finalize_order_button(test)

        log.info("Waiting for Order completed page.")
        self.wait_for_order_completed(test)

        log.info("Order Placed.")
        self.driver.save_screenshot("screenshot.png")
        self.notification_handler.send_notification("Order Placed", True)
        return True
