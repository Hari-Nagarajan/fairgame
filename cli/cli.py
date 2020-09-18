import click

from cli.gpu import GPU
from stores.nvidia import NvidiaBuyer


@click.group()
def main():
    pass


@click.command()
@click.argument("gpu", type=GPU())
def buy(gpu):
    nv = NvidiaBuyer()
    nv.buy(gpu)


main.add_command(buy)
