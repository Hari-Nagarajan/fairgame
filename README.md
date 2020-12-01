# nvidia-bot

[Installation](#Installation) | [Usage](#Usage) | [Discord](https://discord.gg/qDY2QBtAW6)  | [Troubleshooting](#Troubleshooting)

## Why???

I built this in response to the severe tech scalping situation that's happening right now. Almost every tech product that's coming
out right now is being instantly brought out by scalping groups and then resold at at insane prices. $699 GPUs are being listed
for $1700 on eBay, and these scalpers are buying 40 carts while normal consumers can't get a single one. Preorders for the PS5 are
being resold for nearly $1000. My take on this is that if I release a bot that anyone can use, for free, then the number of items 
that scalpers can buy goes down and normal consumers can buy items for MSRP. If everyone is botting, then no one is botting. 

## Got a question?

See the [FAQs](#frequently-asked-questions) first.

## Installation

Easy_XII has created a great cheat sheet for getting started, [please follow this guide](https://docs.google.com/document/d/1grN282tPodM9N57bPq4bbNyKZC01t_4A-sLpzzu_7lM/).

This project uses [Pipenv](https://pypi.org/project/pipenv/) to manage dependencies. Hop in my [Discord](https://discord.gg/qDY2QBtAW6) if you have ideas, need help or just want to tell me about how you got your new 3080. 

To get started you'll first need to clone this repository. If you are unfamiliar with Git, follow the [guide on how to do that on our Wiki](https://github.com/Hari-Nagarajan/nvidia-bot/wiki/How-to-use-GitHub-Desktop-App). You *can* use the "Download Zip" button on the GitHub repository's homepage but this makes receieving updates more difficult. If you can get setup with the GitHub Desktop app, updating to the latest version of the bot takes 1 click.

!!! YOU WILL NEED TO USE THE 3.8 BRANCH OF PYTHON, 3.9.0 BREAKS DEPENDENCIES !!!
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
  bestbuy
```

## Current Functionality

| **Website** | **Auto Checkout** | **Open Cart Link** | **Test flag** |
|:---:|:---:|:---:|:---:|
| amazon.com |`✔`| | |
| bestbuy.com | |`✔`| |


## Usage

### Amazon 

**Amazon flags**
```
--no-image : prevents images from loading on amazon webdriver
--test : This will not finish the checkout
--delay : modify default delay between page refreshes (3 seconds), use --delay=x, where is is time in seconds (accepts decimals)
--checkshipping : Bot will consider shipping + sales price in reserve check. Without this flag, only free shipping items will be considered
--detailed : Take more screenshots. !!!!!! This could cause you to miss checkouts !!!!!!
--used : Show used items in search listings
```

Make a copy of `amazon_config.template_json` and rename to `amazon_config.json`:
```json
{
  "username": "",
  "password": "",
  "asin_groups": 2,
  "asin_list_1": ["B07JH53M4T","B08HR7SV3M"],
  "reserve_1": 1000,
  "asin_list_2": ["B07JH53M4T","B08HR7SV3M"],
  "reserve_2": 750,
  "amazon_website": "smile.amazon.com"
}
```
* `username` is your Amazon account email address
* `password` is your Amazon account password
* `asin_groups` indicates the number of ASIN groups you want to use.
* `asin_list_x` list of ASINs for products you want to purchase. You must locate these (see Discord or lookup the ASIN on product pages). 
    * The first time an item from list "x" is in stock and under its associated reserve, it will purchase it. 
    * If the purchase is successful, the bot will not buy anything else from list "x".
* `reserve_x` is the most amount you want to spend for a single item (i.e., ASIN) in `asin_list_x`. Does not include tax. If --checkshipping flag is active, this includes shipping listed on offer page.
* `amazon_website` amazon domain you want to use. smile subdomain appears to work better, if available in your country.

Example usage:

```
python app.py amazon --test
...
INFO: "2020-09-25 14:40:49,987 - Initializing notification handlers
INFO: "2020-09-25 14:40:49,988 - Enabled Handlers: ['Audio', 'Twilio', 'Pavlok']
INFO: "2020-09-25 14:40:54,141 - Already logged in
INFO: "2020-09-25 14:40:54,141 - Checking stock for items.
INFO: "2020-09-25 14:40:54,614 - One or more items in stock!
INFO: "2020-09-25 14:40:54,718 - Pavlok zaped
INFO: "2020-09-25 14:40:54,848 - SMS Sent: SM68afc07b580f45d1b2527ec4b668f2d8
INFO: "2020-09-25 14:40:58,771 - Clicking continue.
INFO: "2020-09-25 14:41:03,816 - Waiting for Cart Page
INFO: "2020-09-25 14:41:03,826 - On cart page.
INFO: "2020-09-25 14:41:03,826 - clicking checkout.
INFO: "2020-09-25 14:41:04,287 - Waiting for Place Your Order Page
INFO: "2020-09-25 14:41:04,332 - Finishing checkout
INFO: "2020-09-25 14:41:04,616 - Clicking Button: <selenium.webdriver.remote.webelement.WebElement (session="89f5bfa2d22cf963433ed241494d68c1", element="b3fb2797-383c-413d-8d79-1ddd63013394")>
INFO: "2020-09-25 14:41:04,617 - Waiting for Order completed page.
INFO: "2020-09-25 14:41:04,617 - This is a test, so we don't need to wait for the order completed page.
INFO: "2020-09-25 14:41:04,617 - Order Placed.
```


## Best Buy
This is fairly basic right now.  The bot will monitor for the SKUs provided and if one shows as buyable, it will 
attempt to open your default browser and add it to cart.  Just login to the best buy website in your default browser 
and then run the command as follows:

```
python app.py bestbuy --sku [SKU] --skus [SKU1,SKU2,SKU3]
```

Example:
```python
python app.py bestbuy --sku 6429440
python app.py bestbuy --skus 6429440,6430175,6432400,6436223
```


### Notifications
Notifications are now handled by apprise. Apprise lets you send notifications to a large number of supported notification services.
Check https://github.com/caronc/apprise/wiki for a detailed list. 

To enable Apprise notifications, make a copy of `apprise_config.template_json` in the `config` directory and name it `apprise_config.json`.
Then add apprise formatted urls for your desired notification services as json blobs. 

Apprise Example blobs:
```json
[
  {
  "url": "tgram://{bot_token}/{chat_id}"
  },
  {
  "url": "twilio://{AccountSID}:{AuthToken}@{FromPhoneNo}/{PhoneNo}"
  },
  {
  "url": "slack://{OAuthToken}/#{channel}"
  },
  {
  "url": "{COPY AND PASTE DISCORD WEBHOOK HERE}"
  }
]
```

#### Pavlok
To enable shock notifications to your [Pavlok Shockwatch](https://www.amazon.com/Pavlok-PAV2-PERIMETER-BLACK-2/dp/B01N8VJX8P?),
store the url from the pavlok app in the ```pavlok_config.json``` file, you can copy the template from ```pavlok_config.template_json```.

**WARNING:** This feature does not currently support adjusting the intensity, it will always be max (255).
```json
{
  "base_url": "url goes here"
}
```


#### Testing notifications

Once you have setup your `apprise_config.json ` you can test it by running `python app.py test-notifications` from within your pipenv shell. This will send a test notification to all configured notification services.

## Troubleshooting

I suggest joining the #tech-support channel in [Discord](https://discord.gg/qDY2QBtAW6) for personal assistance if these common fixes don't help.

**Error: ```selenium.common.exceptions.WebDriverException: Message: unknown error: cannot find Chrome binary```** 
The issue is that chrome is not installed in the expected location. See [Selenium Wiki](https://github.com/SeleniumHQ/selenium/wiki/ChromeDriver#requirements) and the section on [overriding the Chrome binary location .](https://sites.google.com/a/chromium.org/chromedriver/capabilities#TOC-Using-a-Chrome-executable-in-a-non-standard-location)

The easy fix for this is to add an option where selenium is used (`selenium_utils.py``)
```python
chrome_options.binary_location="C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe"
```

**Error: ```selenium.common.exceptions.SessionNotCreatedException: Message: session not created: This version of ChromeDriver only supports Chrome version 87```**

You are not running the proper version of Chrome this requires. As of this update, the current version is Chrome 87. Check your version by going to ```chrome://version/``` in your browser. We are going to be targeting the current stable build of chrome. If you are behind, please update, if you are on a beta or canary branch, you'll have to build your own version of chromedriver-py.

## Raspberry-Pi-Setup
Maybe this works?

1. Prereqs and Setup
```shell
sudo apt update
sudo apt upgrade
sudo apt install chromium-chromedriver
git clone https://github.com/Hari-Nagarajan/nvidia-bot
cd nvidia-bot/
pip3 install pipenv
export PATH=$PATH:/home/<YOURUSERNAME>/.local/bin
pipenv shell 
pipenv install
```
2. Leave this Terminal window open.

3. Open the following file in a text editor: 
```
/home/<YOURUSERNAME>/.local/share/virtualenvs/nvidia-bot-<RANDOMCHARS>/lib/python3.7/site-packages/selenium/webdriver/common/service.py
```
4. Edit line 38 from `self.path = executable` to `self.path = "chromedriver"`, then save and close the file.


5. Back in Terminal...
```shell
python app.py
```

6. Follow [Usage](#Usage) to configure the bot as needed.

## Frequently Asked Questions

### 1. Can I run multiple instances of the bot? 
Yes. For example you can run one instance to check stock on the Nvidia store and a separate instance to check stock on Amazon. Bear in mind that if you do this you may end up with multiple purchases going through at the same time.

### 2. Does Nvidia Bot automatically bypass CAPTCHA's on the store sites?
* For Amazon, yes. The bot will try and auto-solve CAPTCHA's during the checkout process.

## Attribution

Notification sound from https://notificationsounds.com.
