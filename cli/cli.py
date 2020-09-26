import click

from cli.utils import QuestionaryOption
from notifications.notifications import NotificationHandler
from stores.amazon import Amazon
from stores.bestbuy import BestBuyHandler
from stores.evga import Evga
from stores.nvidia import NvidiaBuyer, GPU_DISPLAY_NAMES, CURRENCY_LOCALE_MAP
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
    type=click.Choice(CURRENCY_LOCALE_MAP.keys(), case_sensitive=False),
    prompt="What locale shall we use?",
    cls=QuestionaryOption,
)
@click.option("--test", is_flag=True)
@click.option("--interval", type=int, default=5)
def nvidia(gpu, locale, test, interval):
    try:
        nv = NvidiaBuyer(gpu, locale, test, interval)
        nv.run_items()
    except KeyboardInterrupt:
        raise
    except:
        send_crash_notification("nvidia")
        raise


@click.command()
@click.option("--no-image", is_flag=True)
@click.option("--headless", is_flag=True)
@click.option("--test", is_flag=True)
def amazon(no_image, headless, test):
    try:
        if no_image:
            selenium_utils.no_amazon_image()
        amzn_obj = Amazon(headless=headless)
        amzn_obj.run_item(test=test)
    except KeyboardInterrupt:
        raise
    except:
        send_crash_notification("amazon")
        raise


@click.command()
@click.option("--sku", type=str, required=True)
@click.option("--headless", is_flag=True)
def bestbuy(sku, headless):
    try:
        bb = BestBuyHandler(sku, headless)
        bb.run_item()
    except KeyboardInterrupt:
        raise
    except:
        send_crash_notification("bestbuy")
        raise


@click.command()
@click.option("--test", is_flag=True)
@click.option("--headless", is_flag=True)
def evga(test, headless):
    try:
        ev = Evga(headless)
        ev.buy(test=test)
    except KeyboardInterrupt:
        raise
    except:
        send_crash_notification("evga")
        raise


notification_handler = NotificationHandler()


def send_crash_notification(store):
    notification_handler.send_notification(f"nvidia-bot for {store} has crashed.")


main.add_command(nvidia)
main.add_command(amazon)
main.add_command(bestbuy)
main.add_command(evga)
