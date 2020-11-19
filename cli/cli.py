from datetime import datetime
from functools import wraps
from signal import signal, SIGINT

import click

from cli.utils import QuestionaryOption
from notifications.notifications import NotificationHandler, TIME_FORMAT
from stores.amazon import Amazon, DEFAULT_AUTOBUY_CONFIG_PATH as DEFAULT_AMAZON_CONFIG_PATH
from stores.bestbuy import BestBuyHandler
from stores.nvidia import NvidiaBuyer, GPU_DISPLAY_NAMES, CURRENCY_LOCALE_MAP
from utils import selenium_utils
from utils.logger import log

notification_handler = NotificationHandler()


def handler(signal, frame):
    log.info("Caught the stop, exiting.")
    exit(0)


def notify_on_crash(func):
    @wraps(func)
    def decorator(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except KeyboardInterrupt:
            pass
        except:
            notification_handler.send_notification(f"nvidia-bot has crashed.")
            raise

    return decorator


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
@notify_on_crash
def nvidia(gpu, locale, test, interval):
    nv = NvidiaBuyer(
        gpu,
        notification_handler=notification_handler,
        locale=locale,
        test=test,
        interval=interval,
    )
    nv.run_items()


@click.command()
@click.option("--no-image", is_flag=True)
@click.option("--headless", is_flag=True)
@click.option("--test", is_flag=True)
@click.option("--config-file", default=DEFAULT_AMAZON_CONFIG_PATH, type=str, show_default=True)
@notify_on_crash
def amazon(no_image, headless, test, config_file):
    if no_image:
        selenium_utils.no_amazon_image()
    else:
        selenium_utils.yes_amazon_image()

    amzn_obj = Amazon(headless=headless, notification_handler=notification_handler, config_file=config_file)
    amzn_obj.run_item(test=test)


@click.command()
@click.option("--sku", type=str, required=True)
@click.option("--headless", is_flag=True)
@notify_on_crash
def bestbuy(sku, headless):
    bb = BestBuyHandler(
        sku, notification_handler=notification_handler, headless=headless
    )
    bb.run_item()


@click.command()
def test_notifications():
    enabled_handlers = ", ".join(notification_handler.get_enabled_handlers())
    time = datetime.now().strftime(TIME_FORMAT)
    notification_handler.send_notification(
        f"Beep boop. This is a test notification from Nvidia bot. Sent {time}."
    )
    log.info(f"A notification was sent to the following handlers: {enabled_handlers}")


signal(SIGINT, handler)

main.add_command(nvidia)
main.add_command(amazon)
main.add_command(bestbuy)
main.add_command(test_notifications)
