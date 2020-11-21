from cli import cli
from signal import signal, SIGINT
from utils.logger import log

from selenium import webdriver
from stores.amazon import Amazon


def handler(signal, frame):
    log.info("Caught a ctrl-c, exiting...")
    try:
        webdriver.quit(Amazon(driver))
    except Exception as e:
        log.info(e)
        log.info("Failed to close driver")
    exit(0)


if __name__ == "__main__":
    signal(SIGINT, handler)
    cli.main()
