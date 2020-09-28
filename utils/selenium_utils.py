import requests
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait


options = Options()
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)


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


def no_amazon_image():
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)


def yes_amazon_image():
    prefs = {"profile.managed_default_content_settings.images": 0}
    options.add_experimental_option("prefs", prefs)


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
