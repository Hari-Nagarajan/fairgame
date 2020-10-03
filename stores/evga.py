import getpass
import json
import pickle
from os import path
from time import sleep
from utils import encryption as encrypt

from chromedriver_py import binary_path  # this will get you the path variable
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

from notifications.notifications import NotificationHandler
from utils import selenium_utils
from utils.logger import log
from utils.selenium_utils import options, enable_headless

LOGIN_URL = "https://secure.evga.com/us/login.asp"
CONFIG_PATH = "evga_config.json"


class Evga:
    def __init__(self, headless=False):
        if headless:
            enable_headless()
        self.notification_handler = NotificationHandler()
        if path.exists(CONFIG_PATH):
            self.load_encrypted_credentials(CONFIG_PATH)
        else:
            log.fatal("No config file found, creating")
            config_dict = self.await_credential_input()
            self.create_encrypted_credentials(config_dict, CONFIG_PATH)
        
        self.driver = webdriver.Chrome(executable_path=binary_path, options=options)
        self.login(self.username, self.password)

    @staticmethod
    def await_credential_input():
        username = input("EVGA login ID: ")
        password = getpass.getpass(prompt="EVGA Password: ")
        card_pn = input("Part number to purchase: ")
        card_series = input("Card series (3070, 3080, 3090): ")
        credit_card = {}
        credit_card["name"] = input("Name on your CC: ")
        credit_card["number"] = input("Credit card number: ")
        credit_card["cvv"] = input("3 digit number on the back (4 for AMEX): ")
        credit_card["expiration_month"] = input("Expiration month (2 digit format): ")
        credit_card["expiration_year"] = input("Expiration year (4 digit format): ")
        return {
            "username": username,
            "password": password,
            "card_pn": card_pn,
            "card_series": card_series,
            "credit_card": credit_card,
        }

    @staticmethod
    def create_encrypted_credentials(config_dict, config_path):
        config = bytes(json.dumps(config_dict), "utf-8")
        log.info("Create a password for the credential file")
        cpass = getpass.getpass(prompt="Credential file password: ")
        vpass = getpass.getpass(prompt="Verify credential file password: ")
        if cpass == vpass:
            result = encrypt.encrypt(config, cpass)
            final_config = open(config_path, "w")
            final_config.write(result)
            final_config.close()
            log.info("Credentials safely stored.")
        else:
            print("Password and verify password do not match.")
            exit(0)

    def load_encrypted_credentials(self, config_path):
        with open(config_path, "r") as json_file:
            try:
                data = json_file.read()
                if "nonce" in data:
                    password = getpass.getpass(prompt="Password: ")
                    decrypted = encrypt.decrypt(data, password)
                    config = json.loads(decrypted)
                    self.username = config["username"]
                    self.password = config["password"]
                    self.card_pn = config["card_pn"]
                    self.card_series = config["card_series"]
                    self.credit_card = config["credit_card"]
                else:
                    config = bytes(json.dumps(data), "utf-8")
                    log.info("Your configuration file is unencrypted, it will now be encrypted.")
                    cpass = getpass.getpass(prompt="Credential file password: ")
                    vpass = getpass.getpass(prompt="Verify credential file password: ")
                    if cpass == vpass:
                        result = encrypt.encrypt(config, cpass)
                        final_config = open(AUTOBUY_CONFIG_PATH, "w")
                        final_config.write(result)
                        final_config.close()
                        log.info("Credentials safely stored.")
                    else:
                        print("Password and verify password do not match.")
                        exit(0)
            except Exception as e:
                log.error(e)
                log.error("Failed to decrypt the credential file.")

    def login(self, username, password):
        """
        We're just going to attempt to load cookies, else enter the user info and let the user handle the captcha
        :param username:
        :param password:
        :return:
        """
        self.driver.execute_cdp_cmd(
            "Network.setUserAgentOverride",
            {
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.53 Safari/537.36"
            },
        )
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        if path.isfile("evga-cookies.pkl"):  # check for cookies file
            self.driver.get("https://www.evga.com")
            selenium_utils.wait_for_page(
                self.driver, "EVGA - Intelligent Innovation - Official Website", 300
            )
            cookies = pickle.load(open("evga-cookies.pkl", "rb"))
            for cookie in cookies:
                self.driver.add_cookie(cookie)

        self.driver.get("https://www.evga.com")
        selenium_utils.wait_for_page(
            self.driver, "EVGA - Intelligent Innovation - Official Website", 300
        )
        if (
            len(self.driver.find_elements_by_id("svg-login")) > 0
        ):  # cookies did not provide logged in state
            self.driver.get(LOGIN_URL)
            selenium_utils.wait_for_page(self.driver, "EVGA - Intelligent Innovation")

            selenium_utils.field_send_keys(self.driver, "evga_login", username)
            selenium_utils.field_send_keys(self.driver, "password", password)

            log.info("Go do the captcha and log in")

            selenium_utils.wait_for_page(
                self.driver, "EVGA - Intelligent Innovation - Official Website", 300
            )
            pickle.dump(
                self.driver.get_cookies(), open("evga-cookies.pkl", "wb")
            )  # save cookies

        log.info("Logged in!")

    def buy(self, delay=5, test=False):
        if test:
            log.info("Refreshing Page Until Title Matches ...")
            selenium_utils.wait_for_title(
                self.driver,
                "EVGA - Products - Graphics - GeForce 16 Series Family - GTX 1660",
                "https://www.evga.com/products/ProductList.aspx?type=0&family=GeForce+16+Series+Family&chipset=GTX+1660",
            )
        else:
            log.info("Refreshing Page Until Title Matches ...")
            selenium_utils.wait_for_title(
                self.driver,
                "EVGA - Products - Graphics - GeForce 30 Series Family - RTX "
                + self.card_series,
                "https://www.evga.com/products/productlist.aspx?type=0&family=GeForce+30+Series+Family&chipset=RTX+"
                + self.card_series,
            )

        log.info("matched chipset=RTX+" + self.card_series + "!")

        if self.card_pn and not test:
            # check for card
            log.info("On GPU list Page")
            card_btn = self.driver.find_elements_by_xpath(
                "//a[@href='/products/product.aspx?pn=" + self.card_pn + "']"
            )
            while not card_btn:
                log.debug("Refreshing page for GPU")
                self.driver.refresh()
                card_btn = self.driver.find_elements_by_xpath(
                    "//a[@href='/products/product.aspx?pn=" + self.card_pn + "']"
                )
                sleep(delay)

            card_btn[0].click()

        #  Check for stock
        log.info("On GPU Page")
        atc_buttons = self.driver.find_elements_by_xpath(
            '//input[@class="btnBigAddCart"]'
        )
        while not atc_buttons:
            log.debug("Refreshing page for GPU")
            self.driver.refresh()
            atc_buttons = self.driver.find_elements_by_xpath(
                '//input[@class="btnBigAddCart"]'
            )
            sleep(delay)

        #  Add to cart
        atc_buttons[0].click()

        # Send notification that product is available
        self.notification_handler.send_notification(
            f"📦 Card found in stock at EVGA (P/N {self.card_pn})…"
        )

        #  Go to checkout
        selenium_utils.wait_for_page(self.driver, "EVGA - Checkout")
        selenium_utils.button_click_using_xpath(
            self.driver, '//*[@id="LFrame_CheckoutButton"]'
        )

        # Shipping Address screen
        selenium_utils.wait_for_page(self.driver, "Shopping")

        log.info("Skip that page.")
        self.driver.get("https://secure.evga.com/Cart/Checkout_Payment.aspx")

        selenium_utils.wait_for_page(self.driver, "EVGA - Checkout - Billing Options")

        log.info("Ensure that we are paying with credit card")
        sleep(3)
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, './/input[@value="rdoCreditCard"]'))
        ).click()
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="ctl00_LFrame_btncontinue"]')
            )
        ).click()

        selenium_utils.wait_for_element(self.driver, "ctl00_LFrame_txtNameOnCard")

        log.info("Populate credit card fields")

        selenium_utils.field_send_keys(
            self.driver, "ctl00$LFrame$txtNameOnCard", self.credit_card["name"]
        )
        selenium_utils.field_send_keys(
            self.driver, "ctl00$LFrame$txtCardNumber", self.credit_card["number"]
        )
        selenium_utils.field_send_keys(
            self.driver, "ctl00$LFrame$txtCvv", self.credit_card["cvv"]
        )
        Select(self.driver.find_element_by_id("ctl00_LFrame_ddlMonth")).select_by_value(
            self.credit_card["expiration_month"]
        )
        Select(self.driver.find_element_by_id("ctl00_LFrame_ddlYear")).select_by_value(
            self.credit_card["expiration_year"]
        )
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "/html/body/form/div[3]/div[3]/div/div[1]/div[5]/div[3]/div/div[1]/div/div[@id='checkoutButtons']/input[2]",
                )
            )
        ).click()

        try:
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "/html/body/form/div[3]/div[3]/div/div[1]/div[5]/div[3]/div/div[1]/div/div[@id='checkoutButtons']/input[2]",
                    )
                )
            ).click()
        except:
            pass

        log.info("Finalize Order Page")
        selenium_utils.wait_for_page(self.driver, "EVGA - Checkout - Finalize Order")

        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "ctl00_LFrame_cbAgree"))
        ).click()

        if not test:
            WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.ID, "ctl00_LFrame_btncontinue"))
            ).click()

        log.info("Finalized Order!")

        # Send extra notification alerting user that we've successfully ordered.
        self.notification_handler.send_notification(
            f"🎉 Order submitted at EVGA for {self.card_pn}",
            audio_file="purchase.mp3",
        )
