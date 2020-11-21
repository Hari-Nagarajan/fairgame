from cli import cli
from signal import signal, SIGINT
from utils.logger import log
from selenium import webdriver

def handler(signal, frame):
    log.info("Caught a ctrl-c, exiting...")
    try:
        webdriver.Chrome.quit()
    except Exception:
        pass
    exit(0)

if __name__ == "__main__":
    signal(SIGINT, handler)
    cli.main()
