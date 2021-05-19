from decimal import Decimal
from enum import Enum

import attr
from amazoncaptcha import AmazonCaptcha
from furl import furl
from lxml import html
from price_parser import Price, parse_price

from utils.logger import log

FREE_SHIPPING_PRICE = parse_price("0.00")

MERCHANT_IDS = [
    "A2Q3Y263D00KWC",
    "A2EUQ1WTGCTBG2",
    "A1AM78C64UM0Y8",
    "ATVPDKIKX0DER",
    "A2VIGQ35RCS4UG",
    "A1PA6795UKMFR9",
    "ARBP9OOSHTCHU",
    "A1RKKUPIHCS9HS",
    "A13V1IB3VIYZZH",
    "A1F83G8C2ARO7P",
    "A21TJRUUN4KGV",
    "APJ6JRA9NG5V4",
    "A1805IZSGTT6HS",
    "A1C3SOZRARQ6R3",
    "A17E79C6D8DWNP",
    "A2NODRKZP88ZB9",
    "A33AVAJ2PDY3EV",
    "A19VAU5U5O7RUS",
    "A39IBJ37TRP1C6",
    "A1VC38T7YXB528",
    "A3P5ROKL5A1OLE",
    "A2OAJ7377F756P",
    "A2KVF7QXNCLV8H",
    "A1X6FK5RDHNB96",
    "A2CVHYRTWLQO9T",
    "A3JWKAKR8XB7XF",
    "AN1VRQENFRJN5",
    "A3DWYIK6Y9EEQB",
    "A1AT7YVPFBWXBL",
    "A11IL2PNWYJU7H",
    "A3OJWAJQNSBARP",
    "A301WKE65PGVT5",
]


class AmazonItemCondition(Enum):
    # See https://sellercentral.amazon.com/gp/help/external/200386310?language=en_US&ref=efph_200386310_cont_G1831
    Neu = 10
    Neuf = 10
    New = 10
    Nieuw = 10
    Nuevo = 10
    Nuovo = 10
    Refurbished = 20
    Renewed = 20
    Rental = 30
    CollectibleLikeNew = 40
    GebrauchtWieneu = 40
    LikeNew = 40
    Open_box = 40
    OpenBoxLikeNew = 40
    UsedLikeNew = 40
    CollectibleVeryGood = 50
    GebrauchtSehrgut = 50
    OpenBoxVeryGood = 50
    UsatoComenuovo = 50
    UsedVeryGood = 50
    VeryGood = 50
    CollectibleGood = 60
    GebrauchtGut = 60
    Good = 60
    OpenBoxGood = 60
    UsedGood = 60
    Acceptable = 70
    CollectibleAcceptable = 70
    OpenBoxAcceptable = 70
    UsedAcceptable = 70
    Used = 80
    Unknown = 1000
    Any = 1001

    @classmethod
    def from_str(cls, label):
        # Straight lookup
        try:
            if label.strip() == "":
                return AmazonItemCondition.Unknown

            condition = AmazonItemCondition[label]
            return condition
        except KeyError:
            # Key doesn't exist as a Member, so try cleaning up the string
            cleaned_label = "".join(label.split())
            cleaned_label = cleaned_label.replace("-", "")
            try:
                condition = AmazonItemCondition[cleaned_label]
                return condition
            except KeyError:
                log.error(f"Found invalid Item Condition Key: '{label}'")
                return AmazonItemCondition.Unknown
                # raise NotImplementedError


@attr.s(auto_attribs=True)
class SellerDetail:
    merchant_id: str
    price: Price
    shipping_cost: Price
    condition: int = AmazonItemCondition.New
    offering_id: str = None
    atc_form: list = []

    @property
    def selling_price(self) -> Decimal:
        return self.price.amount + self.shipping_cost.amount


@attr.s(auto_attribs=True)
class FGItem:
    id: str
    min_price: Price
    max_price: Price
    purchase_delay: int = 0
    name: str = None
    short_name: str = None
    furl: furl = None
    pdp_url = None
    condition: AmazonItemCondition = AmazonItemCondition.New
    status_code: int = 200
    merchant_id: str = "any"


def get_merchant_names(tree):
    # Merchant Link XPath:
    # //a[@target='_blank' and contains(@href, "merch_name")]
    merchant_nodes = tree.xpath(
        "//a[@target='_blank' and contains(@href, 'merch_name')]"
    )
    # log.debug(f"found {len(merchant_nodes)} merchant nodes.")
    merchants = []
    for idx, merchant_node in enumerate(merchant_nodes):
        # log.debug(f"Found merchant {idx + 1}: {merchant_node.text.strip()}")
        merchants.append(merchant_node.text.strip())
    return merchants


def get_prices(tree):
    # Price collection xpath:
    # //div[@id='aod-offer']//div[contains(@id, "aod-price-")]//span[contains(@class,'a-offscreen')]
    price_nodes = tree.xpath(
        "//div[@id='aod-offer']//div[contains(@id, 'aod-price-')]//span[contains(@class,'a-offscreen')]"
    )
    # log.debug(f"Found {len(price_nodes)} price nodes.")
    prices = []
    for idx, price_node in enumerate(price_nodes):
        log.debug(f"Found price {idx + 1}: {price_node.text}")
        prices.append(parse_price(price_node.text))
    return prices


def get_shipping_costs(tree, free_shipping_string):
    # Assume Free Shipping and change otherwise

    # Shipping collection xpath:
    # .//div[starts-with(@id, 'aod-bottlingDepositFee-')]/following-sibling::span
    shipping_nodes = tree.xpath(
        ".//div[starts-with(@id, 'aod-bottlingDepositFee-')]/following-sibling::*[1]"
    )
    count = len(shipping_nodes)
    # log.debug(f"Found {count} shipping nodes.")
    if count == 0:
        log.warning("No shipping nodes found.  Assuming zero.")
        return FREE_SHIPPING_PRICE
    elif count > 1:
        log.warning("Found multiple shipping nodes.  Using the first.")

    shipping_node = shipping_nodes[0]
    # Shipping information is found within either a DIV or a SPAN following the bottleDepositFee DIV
    # What follows is logic to parse out the various pricing formats within the HTML.  Not ideal, but
    # it's what we have to work with.
    shipping_span_text = shipping_node.text.strip()
    if shipping_node.tag == "div":
        if shipping_span_text == "":
            # Assume zero shipping for an empty div
            log.debug(
                "Empty div found after bottleDepositFee.  Assuming zero shipping."
            )
            return FREE_SHIPPING_PRICE
        else:
            # Assume zero shipping for unknown values in
            log.warning(
                f"Non-Empty div found after bottleDepositFee.  Assuming zero. Stripped Value: '{shipping_span_text}'"
            )
            return FREE_SHIPPING_PRICE
    elif shipping_node.tag == "span":
        # Shipping values in the span are contained in:
        # - another SPAN
        # - hanging out alone in a B tag
        # - Hanging out alone in an I tag
        # - Nested in two I tags <i><i></i></i>
        # - "Prime FREE Delivery" in this node

        shipping_spans = shipping_node.findall("span")
        shipping_bs = shipping_node.findall("b")
        # shipping_is = shipping_node.findall("i")
        shipping_is = shipping_node.xpath("//i[@aria-label]")
        if len(shipping_spans) > 0:
            # If the span starts with a "& " it's free shipping (right?)
            if shipping_spans[0].text.strip() == "&":
                # & Free Shipping message
                # log.debug("Found '& Free', assuming zero.")
                return FREE_SHIPPING_PRICE
            elif shipping_spans[0].text.startswith("+"):
                return parse_price(shipping_spans[0].text.strip())
        elif len(shipping_bs) > 0:
            for message_node in shipping_bs:

                if message_node.text.upper() in free_shipping_string:
                    # log.debug("Found free shipping string.")
                    return FREE_SHIPPING_PRICE
                else:
                    log.error(
                        f"Couldn't parse price from <B>. Assuming 0. Do we need to add: '{message_node.text.upper()}'"
                    )
                    return FREE_SHIPPING_PRICE
        elif len(shipping_is) > 0:
            # If it has prime icon class, assume free Prime shipping
            if "FREE" in shipping_is[0].attrib["aria-label"].upper():
                # log.debug("Found Free shipping with Prime")
                return FREE_SHIPPING_PRICE
        elif any(
            shipping_span_text.upper() in free_message
            for free_message in free_shipping_string
        ):
            # We found some version of "free" inside the span.. but this relies on a match
            log.warning(
                f"Assuming free shipping based on this message: '{shipping_span_text}'"
            )
        else:
            log.error(
                f"Unable to locate price.  Assuming 0.  Found this: '{shipping_span_text}' "
                f"Consider reporting to #tech-support Discord."
            )
    return FREE_SHIPPING_PRICE


def get_form_actions(tree):
    """Extract the add to cart form actions from an HTML tree using XPath"""
    # ATC form actions
    # //div[@id='aod-offer']//form[contains(@action,'add-to-cart')]
    form_action_nodes = tree.xpath(
        "//div[@id='aod-offer']//form[contains(@action,'add-to-cart')]"
    )
    # log.debug(f"Found {len(form_action_nodes)} form action nodes.")
    form_actions = []
    for idx, form_action in enumerate(form_action_nodes):
        form_actions.append(form_action.action)
    return form_actions


def get_item_condition(form_action) -> AmazonItemCondition:
    """Attempts to determine the Item Condition from the Add To Cart form action"""
    if "_new_" in form_action:
        # log.debug(f"Item condition is new")
        return AmazonItemCondition.New
    elif "_used_" in form_action:
        # log.debug(f"Item condition is used")
        return AmazonItemCondition.UsedGood
    elif "_col_" in form_action:
        # og.debug(f"Item condition is collectible")
        return AmazonItemCondition.CollectibleGood
    else:
        # log.debug(f"Item condition is unknown: {form_action}")
        return AmazonItemCondition.Unknown


def solve_captcha(session, form_element, domain: str):
    log.warning("Encountered CAPTCHA. Attempting to solve.")
    # Starting from the form, get the inputs and image
    captcha_images = form_element.xpath('//img[contains(@src, "amazon.com/captcha/")]')
    if captcha_images:
        link = captcha_images[0].attrib["src"]
        # link = 'https://images-na.ssl-images-amazon.com/captcha/usvmgloq/Captcha_kwrrnqwkph.jpg'
        captcha = AmazonCaptcha.fromlink(link)
        solution = captcha.solve()

        if solution:
            log.info(f"solution is:{solution} ")
            form_inputs = form_element.xpath(".//input")
            input_dict = {}
            for form_input in form_inputs:
                if form_input.type == "text":
                    input_dict[form_input.name] = solution
                else:
                    input_dict[form_input.name] = form_input.value
            f = furl(domain)  # Use the original URL to get the schema and host
            f = f.set(path=form_element.attrib["action"])
            f.add(args=input_dict)
            response = session.get(f.url)
            log.debug(f"Captcha response was {response.status_code}")
            return response.text, response.status_code

    return html.fromstring(""), 404


def price_check(item, seller):
    if item.max_price.amount >= seller.selling_price >= item.min_price.amount:
        return True
    else:
        return False


def condition_check(item, seller):
    if item.condition.value >= seller.condition.value:
        return True
    else:
        return False


def merchant_check(item, seller):
    if (
        item.merchant_id.lower() == "any"
        or (item.merchant_id.lower() == "amazon" and seller.merchant_id in MERCHANT_IDS)
        or item.merchant_id == seller.merchant_id
    ):
        return True
    else:
        return False


def parse_condition(condition: str) -> AmazonItemCondition:
    return AmazonItemCondition[condition]


def min_total_price(seller: SellerDetail):
    return seller.selling_price


def new_first(seller: SellerDetail):
    return seller.condition


def has_captcha(tree):
    return tree.xpath("//form[contains(@action,'validateCaptcha')]")


def free_shipping_check(seller):
    if seller.shipping_cost.amount > 0:
        return False
    else:
        return True
