import os

import click

from cli.utils import GPU, Locale
from stores.amazon import Amazon
from stores.nvidia import NvidiaBuyer


@click.group()
def main():
    pass


@click.command()
@click.option("--gpu", type=GPU(), prompt="What GPU are you after?")
@click.option("--locale", type=Locale(), prompt="What locale shall we use?", default="en_us")
def nvidia(gpu, locale):
    nv = NvidiaBuyer(locale)
    nv.buy(gpu)


@click.command()
@click.option("--amazon_email", type=str, prompt="Amazon Email", default=lambda: os.environ.get('amazon_email', ''),
              show_default='current user')
@click.option("--amazon_password", type=str, prompt="Amazon Password", default=lambda: os.environ.get('amazon_password', ''),
              show_default='current user')
@click.option("--amazon_item_url", type=str, prompt="Amazon Item URL", default=lambda: os.environ.get('amazon_item_url', ''),
              show_default='current user')
@click.option("--amazon_price_limit", type=int, prompt="Maximum Price to Pay", default=lambda: int(os.environ.get('amazon_price_limit', 1000)),
              show_default='current user')
def amazon(amazon_email, amazon_password, amazon_item_url, amazon_price_limit):
    os.environ.setdefault('amazon_email', amazon_email)
    os.environ.setdefault('amazon_password', amazon_password)
    os.environ.setdefault('amazon_item_url', amazon_item_url)
    os.environ.setdefault('amazon_price_limit', str(amazon_price_limit))

    amzn_obj = Amazon(username=amazon_email, password=amazon_password, debug=True)
    amzn_obj.run_item(item_url=amazon_item_url, price_limit=amazon_price_limit)


main.add_command(nvidia)
main.add_command(amazon)
