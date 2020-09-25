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
    nv = NvidiaBuyer(gpu, locale, test, interval)
    nv.run_items()


@click.command()
@click.option("--no-image", is_flag=True)
@click.option("--headless", is_flag=True)
@click.option("--test", is_flag=True)
def amazon(no_image, headless, test):
    if no_image:
        selenium_utils.no_amazon_image()
    amzn_obj = Amazon(headless=headless)
    amzn_obj.run_item(test=test)

@click.command()
@click.option("--sku", type=str, required=True)
@click.option("--headless", is_flag=True)
def bestbuy(sku, headless):
    bb = BestBuyHandler(sku, headless)
    bb.run_item()


@click.command()
@click.option("--test", is_flag=True)
@click.option("--headless", is_flag=True)
def evga(test, headless):
    ev = Evga(headless)
    ev.buy(test=test)


main.add_command(nvidia)
main.add_command(amazon)
main.add_command(bestbuy)
main.add_command(evga)
