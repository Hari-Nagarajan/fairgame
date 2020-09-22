import requests
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait

options = Options()
options.page_load_strategy = "eager"
chrome_options = ChromeOptions()
chrome_options.add_argument("--disable-application-cache")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

# prefs = {"profile.managed_default_content_settings.images": 2}
# chrome_options.add_experimental_option("prefs", prefs)


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


def wait_for_page(d, title, time=30):
    """
    Uses webdriver(d) to wait for page title(title) to become visible
    """
    WebDriverWait(d, time).until(ec.title_is(title))


def button_click_using_xpath(d, xpath):
    """
    Uses webdriver(d) to click a button using an XPath(xpath)
    """
    button_menu = wait_for_element_by_xpath(d, xpath)
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
