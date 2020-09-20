from os import path
import json
import time

# Pasted from stores/amazon.py
from chromedriver_py import binary_path  # this will get you the path variable
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

options = Options()
options.page_load_strategy = "eager"
chrome_options = ChromeOptions()
chrome_options.add_argument("--disable-application-cache")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
chrome_options.add_experimental_option("detach", True)
prefs = {"profile.managed_default_content_settings.images": 2}
chrome_options.add_experimental_option("prefs", prefs)

from utils.logger import log



AUTOBUY_CONFIG_PATH = "autobuy_config.json"
AUTOBUY_CONFIG_KEYS = ['NVIDIA_LOGIN', 'NVIDIA_PASSWORD', 'FULL_AUTOBUY','CREDITCARD_NUMBER','CREDITCARD_EXP','CREDITCARD_SECURITY_CODE']

AUTOBUY_CONTINUE_VAL = ["continuer","envoyer"]

class AutoBuy:
    enabled = False

    def __init__(self):
        log.info("Initializing Autobuy...")
        if path.exists(AUTOBUY_CONFIG_PATH):
            with open(AUTOBUY_CONFIG_PATH) as json_file:
                self.config = json.load(json_file)
                if self.has_valid_creds():
                    self.nvidia_login = self.config['NVIDIA_LOGIN']
                    self.nvidia_password = self.config['NVIDIA_PASSWORD']
                    self.full_autobuy = self.config['FULL_AUTOBUY']
                    self.ccNum = self.config['CREDITCARD_NUMBER'].replace(' ','')
                    self.ccExpDate = self.config['CREDITCARD_EXP'].split('/')
                    self.ccSecCode = self.config['CREDITCARD_SECURITY_CODE']
                    self.enabled = True
        else:
            log.info("No Autobuy creds found.")

    def has_valid_creds(self):
        if all(item in self.config.keys() for item in AUTOBUY_CONFIG_KEYS):
            return True
        else:
            return False

    def auto_buy(self,url):
        log.debug("Initialize autobuy")
        # Create firefox instance
        self.driver = webdriver.Chrome(
            executable_path=binary_path, options=options, chrome_options=chrome_options
        )
        self.driver.get(url)
        self.wait = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "dr_cc_login")))
        self.driver.find_element_by_xpath('//*[@id="loginID"]').send_keys(
            self.nvidia_login
        )
        self.driver.find_element_by_xpath('//*[@id="loginPass"]').send_keys(
            self.nvidia_password
        )
        self.driver.find_element_by_xpath('//*[@id="dr_cc_login"]').click()

        self.wait = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "cCardNew")))

        log.info(f"Logged in as {self.nvidia_login}")

        # Card info
        self.driver.find_element_by_xpath('//*[@id="cCardNew"]').click()
        self.driver.find_element_by_xpath('//*[@id="ccNum"]').send_keys(
            self.ccNum
        )
        Select(self.driver.find_element_by_id('expirationDateMonth')).select_by_value(self.ccExpDate[0].lstrip('0'))
        Select(self.driver.find_element_by_id('expirationDateYear')).select_by_value(self.ccExpDate[1])

        self.driver.find_element_by_xpath('//*[@id="cardSecurityCode"]').send_keys(
            self.ccSecCode
        )
        self.driver.find_element_by_xpath(f'//*[@value="{AUTOBUY_CONTINUE_VAL[0]}"]').click()
        if self.full_autobuy:
            self.wait = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "dr_confirmProducts")))
            self.driver.find_element_by_xpath(f'//*[@value="{AUTOBUY_CONTINUE_VAL[1]}"]').click()
        
        