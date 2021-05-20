#      FairGame - Automated Purchasing Program
#      Copyright (C) 2021  Hari Nagarajan
#
#      This program is free software: you can redistribute it and/or modify
#      it under the terms of the GNU General Public License as published by
#      the Free Software Foundation, either version 3 of the License, or
#      (at your option) any later version.
#
#      This program is distributed in the hope that it will be useful,
#      but WITHOUT ANY WARRANTY; without even the implied warranty of
#      MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#      GNU General Public License for more details.
#
#      You should have received a copy of the GNU General Public License
#      along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#      The author may be contacted through the project's GitHub, at:
#      https://github.com/Hari-Nagarajan/fairgame

import base64
import os
import platform
import shutil
import time
import urllib
from datetime import datetime
from functools import wraps
from pathlib import Path
from signal import SIGINT, signal
import asyncio
from typing import Optional, List

import click
import uvloop

from common.globalconfig import AMAZON_CREDENTIAL_FILE, GlobalConfig
from notifications.notifications import NotificationHandler, TIME_FORMAT

from stores.amazon_handler import AmazonStoreHandler as AIO_AmazonStoreHandler
from utils.logger import log
from utils.version import is_latest, version, get_latest_version

LICENSE_PATH = os.path.join(
    "cli",
    "license",
)

tasks: List[asyncio.Task] = []


def get_folder_size(folder):
    return sizeof_fmt(sum(file.stat().st_size for file in Path(folder).rglob("*")))


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, "Yi", suffix)


# see https://docs.python.org/3/library/signal.html
def interrupt_handler(signal_num, frame):
    log.info(f"Caught the interrupt signal.  Exiting.")
    global tasks
    if tasks:
        log.debug(f"Canceling {len(tasks)} tasks")
        for task in tasks:
            task.cancel()
    exit(0)


def notify_on_crash(func):
    @wraps(func)
    def decorator(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            log.debug(e)
            notification_handler.send_notification(f"FairGame has crashed.")
            global tasks
            if tasks:
                for task in tasks:
                    task.cancel()
            raise

    return decorator


@click.group()
def main():
    pass


@click.command()
@click.option(
    "--p",
    type=str,
    default=None,
    help="Pass in encryption file password as argument",
)
@click.option(
    "--delay", type=float, default=5.0, help="Time to wait between checks for item[s]"
)
@click.option(
    "--uv",
    is_flag=True,
    default=False,
    help="Use uvloop to speed up asyncio. Not supported on Windows.",
)
@notify_on_crash
def amazon_aio(p, delay, uv):
    if uv:
        uvloop.install()
    log.debug("Creating AIO Amazon Store Handler")
    aio_amazon_obj = AIO_AmazonStoreHandler(
        notification_handler=notification_handler, encryption_pass=p, delay=delay
    )
    global tasks
    log.debug("Creating AIO Amazon Store Tasks")
    tasks = asyncio.run(aio_amazon_obj.run_async())
    if tasks:
        for task in tasks:
            task.cancel()
    log.info("All tasks complete, exiting program")


# async def task_handler(tasks: List[asyncio.Task]):
#     while tasks:
#         for task in tasks:
#             if task.done():
#                 task.cancel()
#     await asyncio.sleep(5)
#     return


@click.option(
    "--disable-sound",
    is_flag=True,
    default=False,
    help="Disable local sounds.  Does not affect Apprise notification " "sounds.",
)
@click.command()
def test_notifications(disable_sound):
    enabled_handlers = ", ".join(notification_handler.enabled_handlers)
    message_time = datetime.now().strftime(TIME_FORMAT)
    notification_handler.send_notification(
        f"Beep boop. This is a test notification from FairGame. Sent {message_time}."
    )
    log.info(f"A notification was sent to the following handlers: {enabled_handlers}")
    if not disable_sound:
        log.info("Testing notification sound...")
        notification_handler.play_notify_sound()
        time.sleep(2)  # Prevent audio overlap
        log.info("Testing alert sound...")
        notification_handler.play_alarm_sound()
        time.sleep(2)  # Prevent audio overlap
        log.info("Testing purchase sound...")
        notification_handler.play_purchase_sound()
    else:
        log.info("Local sounds disabled for this test.")

    # Give the notifications a chance to get out before we quit
    time.sleep(5)


@click.command()
@click.option("--w", is_flag=True)
@click.option("--c", is_flag=True)
def show(w, c):
    show_file = "show_c.txt"
    if w and c:
        print("Choose one option. Program Quitting")
        exit(0)
    elif w:
        show_file = "show_w.txt"
    elif c:
        show_file = "show_c.txt"
    else:
        print(
            "Option missing, you must include w or c with show argument. Program Quitting"
        )
        exit(0)

    if os.path.exists(LICENSE_PATH):

        with open(os.path.join(LICENSE_PATH, show_file)) as file:
            try:
                print(file.read())
            except FileNotFoundError:
                log.error("License File Missing. Quitting Program")
                return
    else:
        log.error("License File Missing. Quitting Program.")
        return


@click.command()
@click.option(
    "--domain",
    help="Specify the domain you want to find endpoints for (e.g. www.amazon.de, www.amazon.com, smile.amazon.com.",
)
def find_endpoints(domain):
    import dns.resolver

    if not domain:
        log.error("You must specify a domain to resolve for endpoints with --domain.")
        exit(0)
    log.info(f"Attempting to resolve '{domain}'")
    # Default
    my_resolver = dns.resolver.Resolver()
    try:
        resolved = my_resolver.resolve(domain)
        for rdata in resolved:
            log.info(f"Your computer resolves {domain} to {rdata.address}")
    except Exception as e:
        log.error(f"Failed to use local resolver due to: {e}")
        exit(1)

    # Find endpoints from various DNS servers
    endpoints, resolutions = resolve_domain(domain)
    log.info(
        f"{domain} resolves to at least {len(endpoints)} distinct IP addresses across {resolutions} lookups:"
    )
    endpoints = sorted(endpoints)
    for endpoint in endpoints:
        log.info(f" {endpoint}")

    return endpoints


def resolve_domain(domain):
    import dns.resolver

    public_dns_servers = global_config.get_fairgame_config().get("public_dns_servers")
    resolutions = 0
    endpoints = set()

    # Resolve the domain for each DNS server to find out how many end points we have
    for provider in public_dns_servers:
        # Provider is Google, Verisign, etc.
        log.info(f"Testing {provider}")
        for server in public_dns_servers[provider]:
            # Server is 8.8.8.8 or 1.1.1.1
            my_resolver = dns.resolver.Resolver()
            my_resolver.nameservers = [server]

            try:
                resolved = my_resolver.resolve(domain)
            except Exception as e:
                log.warning(
                    f"Unable to resolve using {provider} server {server} due to: {e}"
                )
                continue
            for rdata in resolved:
                ipv4_address = rdata.address
                endpoints.add(ipv4_address)
                resolutions += 1
                log.debug(f"{domain} resolves to {ipv4_address} via {server}")
    return endpoints, resolutions


@click.command()
@click.option(
    "--domain", help="Specify the domain you want to generate traceroute commands for."
)
def show_traceroutes(domain):
    if not domain:
        log.error("You must specify a domain to test routes using --domain.")
        exit(0)

    # Get the endpoints to test
    endpoints, resolutions = resolve_domain(domain=domain)

    if platform.system() == "Windows":
        trace_command = "tracert -d "
    else:
        trace_command = "traceroute -n "

    # Spitball test routes via Python's traceroute
    for endpoint in endpoints:
        log.info(f" {trace_command}{endpoint}")


@click.command()
def test_logging():
    log.dev("This is a test of the dev log level")


# Register Signal Handler for Interrupt
signal(SIGINT, interrupt_handler)

main.add_command(test_notifications)
main.add_command(show)
main.add_command(find_endpoints)
main.add_command(show_traceroutes)
main.add_command(test_logging)
main.add_command(amazon_aio)

# Global scope stuff here
if is_latest():
    log.info(f"FairGame v{version}")
elif version.is_prerelease:
    log.warning(f"FairGame PRE-RELEASE v{version}")
else:
    log.warning(
        f"You are running FairGame v{version}, but the most recent version is v{get_latest_version()}. "
        f"Consider upgrading "
    )

global_config = GlobalConfig()
notification_handler = NotificationHandler()
