# README.md

Tool to help us buy a GPU in 2020

[Installation](#Installation) | [Usage](#Usage) | [Discord](https://discord.gg/hQeUbRv)  | [Troubleshooting](#Troubleshooting)
## Installation

This project uses [Pipenv](https://pypi.org/project/pipenv/) to manage dependencies. Hop in my [Discord](https://discord.gg/hQeUbRv) if you have ideas, need help or just want to tell me about how you got your new 3080.

```
pip install pipenv
pipenv shell 
pipenv install
```

Run it
```
python app.py

Usage: app.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  amazon
  nvidia
```

## Usage

Ok now we have a basic GUI. GUIs aren't my strong suit, but pretty much the top box is the settings for amazon and
the bottom box is the settings for Nvidia. 

### Amazon 
- Open a chrome browser
- Log into Amazon
- Go to a product page
- Refresh the page until the 'Buy Now' option exists
- If the price is under the "Price Limit", it will buy the item.

Example usage:
```
python app.py amazon
Amazon Email []: hari@email.com
Amazon Password []: mypassword
Amazon Item URL []: https://www.amazon.com/dp/B08HHDP9DW
Maximum Price to Pay [1000]: 1000
...
INFO: "2020-09-19 00:07:02,199 - Logged in as hari@email.com
INFO: "2020-09-19 00:07:05,200 - Loading page: https://www.amazon.com/dp/B08HHDP9DW
INFO: "2020-09-19 00:07:06,452 - Loaded page for ASUS TUF Gaming NVIDIA GeForce RTX 3080 Graphics Card (PCIe 4.0, 10GB GDDR6X, HDMI 2.1, DisplayPort 1.4a, Dual Ball Fan Bearings, Military-Grade Certification, GPU Tweak II)
INFO: "2020-09-19 00:07:06,474 - Initial availability message is: Currently unavailable. We don't know when or if this item will be back in stock.
INFO: "2020-09-19 00:07:06,494 - Refreshing page.
INFO: "2020-09-19 00:07:07,695 - Current availability message is: Currently unavailable. We don't know when or if this item will be back in stock.
```

### Nvidia 
- Call Digitalriver API to get product number for the GPU selected (2060S, 3080, 3090)
- Call Digitalriver API to check if the GPU is in stock until it is in stock
- Will open a window in your default browser with the GPU in your cart when it is stock.

Example usage:
```
python app.py nvidia
What GPU are you after?: 3080
What locale shall we use? [en_us]:
...
19092020 12:05:46 AM : Calling https://api.digitalriver.com/v1/shoppers/me/products/5438481700/inventory-status? : DEBUG -stores.nvidia
19092020 12:05:46 AM : Returned 200 : DEBUG -stores.nvidia
19092020 12:05:46 AM : Stock status is PRODUCT_INVENTORY_OUT_OF_STOCK : INFO -stores.nvidia

```


## Troubleshooting

I suggest joining the #Support channel in [Discord](https://discord.gg/hQeUbRv) for personal assistance if these common fixes don't help.

** Error: ```selenium.common.exceptions.WebDriverException: Message: unknown error: cannot find Chrome binary``` ** 
The issue is that chrome is not installed in the expected location. See [Selenium Wiki](https://github.com/SeleniumHQ/selenium/wiki/ChromeDriver#requirements) and the section on [overriding the Chrome binary location .](https://sites.google.com/a/chromium.org/chromedriver/capabilities#TOC-Using-a-Chrome-executable-in-a-non-standard-location)

The easy fix for this is to add an option where selenium is used (amazon.py)
```
chrome_options.binary_location="C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe"
```

** Error: ```selenium.common.exceptions.SessionNotCreatedException: Message: session not created: This version of ChromeDriver only supports Chrome version 85```

You are not running the proper version of Chrome this requires. As of this update, the current version is Chrome 85. Check your version by going to ```chrome://version/``` in your browser. We are going to be targeting the current stable build of chrome. If you are behind, please update, if you are on a beta or canary branch, you'll have to build your own version of chromedriver-py.