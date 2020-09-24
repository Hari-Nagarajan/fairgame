import os

import click

from cli.utils import QuestionaryOption
from stores.amazon import Amazon
from stores.bestbuy import BestBuyHandler
from stores.evga import Evga
from stores.nvidia import NvidiaBuyer, GPU_DISPLAY_NAMES, ACCEPTED_LOCALES
from utils import selenium_utils


@click.group()
def main():
    pass


@click.command()
@click.option(
    "--gpu",
    type=click.Choice(GPU_DISPLAY_NAMES, case_sensitive=False),
    prompt="What GPU are you after?",
    cls=QuestionaryOption,
)
@click.option(
    "--locale",
    type=click.Choice(ACCEPTED_LOCALES, case_sensitive=False),
    prompt="What locale shall we use?",
    cls=QuestionaryOption,
)
@click.option("--test", is_flag=True)
@click.option("--interval", type=int, default=5)
def nvidia(gpu, locale, test, interval):
    nv = NvidiaBuyer(gpu, locale, test, headless, interval)
    nv.run_items()


@click.command()
@click.option(
    "--amazon_email",
    type=str,
    prompt="Amazon Email",
    default=lambda: os.environ.get("amazon_email", ""),
    show_default="current user",
)
@click.option(
    "--amazon_password",
    type=str,
    prompt="Amazon Password",
    default=lambda: os.environ.get("amazon_password", ""),
    show_default="current user",
)
@click.option(
    "--amazon_item_url",
    type=str,
    prompt="Amazon Item URL",
    default=lambda: os.environ.get("amazon_item_url", ""),
    show_default="current user",
)
@click.option(
    "--amazon_price_limit",
    type=int,
    prompt="Maximum Price to Pay",
    default=lambda: int(os.environ.get("amazon_price_limit", 10000)),
    show_default="current user",
)
@click.option("--no-image", is_flag=True)
@click.option("--headless", is_flag=True)
def amazon(
    amazon_email,
    amazon_password,
    amazon_item_url,
    amazon_price_limit,
    no_image,
    headless,
):
    os.environ.setdefault("amazon_email", amazon_email)
    os.environ.setdefault("amazon_password", amazon_password)
    os.environ.setdefault("amazon_item_url", amazon_item_url)
    os.environ.setdefault("amazon_price_limit", str(amazon_price_limit))

    if no_image:
        selenium_utils.no_amazon_image()

    amzn_obj = Amazon(
        username=amazon_email, password=amazon_password, headless=headless
    )
    amzn_obj.run_item(item_url=amazon_item_url, price_limit=amazon_price_limit)

    if no_image:
        selenium_utils.no_amazon_image()


@click.command()
@click.option("--sku", type=str, required=True)
@click.option("--headless", is_flag=True)
def bestbuy(sku, headless):
    bb = BestBuyHandler(sku, headless)
    bb.run_item()


@click.command()
@click.option("--test", is_flag=True)
@click.option("--model", type=str)
@click.option("--headless", is_flag=True)
def evga(test, model, headless):
    ev = Evga(headless)
    ev.buy(test=test, model=model)


main.add_command(nvidia)
main.add_command(amazon)
main.add_command(bestbuy)
main.add_command(evga)
