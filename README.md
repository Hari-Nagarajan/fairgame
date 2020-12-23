# Fairgame

[Installation](#Installation) | [Usage](#Usage) | [Discord](https://discord.gg/qDY2QBtAW6)  | [Troubleshooting](#Troubleshooting)

## Why???

We built this in response to the severe tech scalping situation that's happening right now. Almost every tech product that's coming
out right now is being instantly brought out by scalping groups and then resold at at insane prices. $699 GPUs are being listed
for $1700 on eBay, and these scalpers are buying 40 carts while normal consumers can't get a single one. Preorders for the PS5 are
being resold for nearly $1000. Our take on this is that if we release a bot that anyone can use, for free, then the number of items 
that scalpers can buy goes down and normal consumers can buy items for MSRP. 

**If everyone is botting, then no one is botting.**

## Got a question?

Read through this document and the cheat sheet linked in the next sections. See the [FAQs](#frequently-asked-questions) if that does not answer your questions.

## Installation

Easy_XII has created a great cheat sheet for getting started, [please follow this guide](https://docs.google.com/document/d/1grN282tPodM9N57bPq4bbNyKZC01t_4A-sLpzzu_7lM/).

This project uses [Pipenv](https://pypi.org/project/pipenv/) to manage dependencies. Hop in my [Discord](https://discord.gg/qDY2QBtAW6) if you have ideas, need help or just want to tell us about how you got your new toys. 

To get started you'll first need to clone this repository. If you are unfamiliar with Git, follow the [guide on how to do that on our Wiki](https://github.com/Hari-Nagarajan/fairgame/wiki/How-to-use-GitHub-Desktop-App). You *can* use the "Download Zip" button on the GitHub repository's homepage but this makes receieving updates more difficult. If you can get setup with the GitHub Desktop app, updating to the latest version of the bot takes 1 click.

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
The following flags are specific to the Amazon scripts.  They the `[OPTIONS]` to be passed on the command-line to control
the behavior of Amazon scanning and purchasing.  These can be added at the command line or added to a batch file/shell
 script (see `_Amazon.bat` in the root folder of the project).

**Amazon flags**

```
python app.py amazon --help

Usage: app.py amazon [OPTIONS]

Options:
  --no-image          Do not load images
  --headless          Unsupported headless mode. GLHF
  --test              Run the checkout flow, but do not actually purchase the
                      item[s]

  --delay FLOAT       Time to wait between checks for item[s]
  --checkshipping     Factor shipping costs into reserve price and look for
                      items with a shipping price

  --detailed          Take more screenshots. !!!!!! This could cause you to
                      miss checkouts !!!!!!

  --used              Show used items in search listings.
  --single-shot       Quit after 1 successful purchase
  --no-screenshots    Take NO screenshots, do not bother asking for help if
                      you use this... Screenshots are the best tool we have
                      for troubleshooting

  --disable-presence  Disable Discord Rich Presence functionallity
  --disable-sound     Disable local sounds.  Does not affect Apprise
                      notification sounds.

  --slow-mode         Uses normal page load strategy for selenium. Default is
                      none

  --p TEXT            Pass in encryption file password as argument
  --help              Show this message and exit.
```

**Configuration**

Make a copy of `amazon_config.template_json` and rename to `amazon_config.json`.  Edit it according to the ASINs  you 
are interested in purchasing.  [*What's an ASIN?*](https://www.datafeedwatch.com/blog/amazon-asin-number-what-is-it-and-how-do-you-get-it#how-to-find-asin)  

* `asin_groups` indicates the number of ASIN groups you want to use.
* `asin_list_x` list of ASINs for products you want to purchase. You must locate these (see Discord or lookup the ASIN on product pages). 
    * The first time an item from list "x" is in stock and under its associated reserve, it will purchase it. 
    * If the purchase is successful, the bot will not buy anything else from list "x".
    * Use sequential numbers for x, starting from 1. x can be any integer from 1 to 18,446,744,073,709,551,616
* `reserve_min_x` set a minimum limit to consider for purchasing an item. If a seller has a listing for a 700 dollar item a 1 dollar, it's likely fake.
* `reserve_max_x` is the most amount you want to spend for a single item (i.e., ASIN) in `asin_list_x`. Does not include tax. If --checkshipping flag is active, this includes shipping listed on offer page.
* `amazon_website` amazon domain you want to use. smile subdomain appears to work better, if available in your country.

**Examples**

One unique product with one ASIN (e.g., Segway Ninebot S and GoKart Drift Kit Bundle) :

```json
{
	"asin_groups": 1,
	"asin_list_1": ["B07K7NLDGT"],
	"reserve_min_1": 450,
	"reserve_max_1": 500,
	"amazon_website": "smile.amazon.com"
}
```

One general product with multiple ASINS (e.g 16 GB USB drive 2 pack)

```json
{
	"asin_groups": 1,
	"asin_list_1": ["B07JH53M4T", "B085M1SQ9S", "B00E9W1ULS"],
	"reserve_min_1": 15,
	"reserve_max_1": 20,
	"amazon_website": "smile.amazon.com"
}
```

Two general products with multiple ASINS and different price points (e.g. 16 GB USB drive 2 pack and a statue of The Thinker)

```json
{
	"asin_groups": 2,
	"asin_list_1": ["B07JH53M4T", "B085M1SQ9S", "B00E9W1ULS"],
	"reserve_min_1": 15,
	"reserve_max_1": 20,
	"asin_list_2": ["B006HPI2A2", "B00N54S1WW"],
	"reserve_min_2": 50,
	"reserve_max_2": 75,
	"amazon_website": "smile.amazon.com"
}
```

If you wanted to watch another product, you'd add a third list (e.g. `asin_list_3`) and associated min/max pricing and
increase the `asin_groups` to 3.  Add as many lists as are needed, keeping in mind that the main distinction between lists
is the min/max price boundaries.  Once any ASIN is purchased from an ASIN list, that list is remove from the hunt
until FairGame is restarted.

To verify that your JSON is well formatted, paste and validate it at https://jsonlint.com/

**Start Up**

Previously your username and password were entered into the config file, this is no longer the case. On first launch the bot will prompt
you for your credentials. You will then be asked for a password to encrypt them. Once done, your encrypted credentials will be stored in
`amazon_credentials.json`. If you ever forget your encryption password, just delete this file and the next launch of the bot will recreate
it. An example of this will look like the following:

```
python app.py amazon
INFO Initializing Apprise handler
INFO Initializing other notification handlers
INFO Enabled Handlers: ['Audio']
INFO No credential file found, let's make one
Amazon login ID: <your email address>
Amazon Password: <your amazon password>
INFO Create a password for the credential file
Credential file password: <a password used to encrypt your amazon credentials>
Verify credential file password: <the same password that was entered above>
INFO Credentials safely stored.
```

Starting the bot when you have created an encrypted file:

```
python app.py amazon --test
INFO Initializing Apprise handler
INFO Initializing other notification handlers
INFO Enabled Handlers: ['Audio']
Reading credentials from: amazon_credentials.json
Credential file password: <enter the previously created password>
```
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


## ~~Best Buy~~

Best Buy is currently deprecated because we don't yet have an effective way to determine item availability 
without scraping and processing the product pages individually.  Future updates may see this functionality 
return, but the current code isn't reliable for high demand items and checkout automation has become 
increasingly hard due to anti-bot measures taken by Best Buy.

Original code still exists, but provides very little utility.  A 3rd party stock notification service would 
probably serve as a better solution at Best Buy.

~~This is fairly basic right now. Just login to the best buy website in your default browser and then run the command as follows:~~

```
python app.py bestbuy --sku [SKU]
```

~~Example:~~
```python
python app.py bestbuy --sku 6429440
```


## Notifications

### Sounds
Local sounds are provided as a means to give you audible cues to what is happening.  The notification sound
plays for notable events (e.g., start up, product found for purchase) during the scans.  An alarm notification
will play when user interaction is necessary.  This is typically when all automated options have been exhausted.
Lastly, a purchase notification sound will play if the bot if successful.  These local sounds can be disabled
via the command-line and [tested](#testing-notifications) along with other notification methods

### Apprise
Notifications are now handled by Apprise. Apprise lets you send notifications to a large number of supported notification services.
Check https://github.com/caronc/apprise/wiki for a detailed list. 

To enable Apprise notifications, make a copy of `apprise.conf_template` in the `config` directory and name it 
`apprise.conf`. Then add apprise formatted urls for your desired notification services as simple text entries 
in the config file.  Any recognized notification services will be reported on app start.   

**Apprise Example Config:**
```
# Hash Tags denote comment lines and blank lines are allowed
# Discord (https://github.com/caronc/apprise/wiki/Notify_discord)

https://discordapp.com/api/webhooks/{WebhookID}/{WebhookToken}

# Telegram
tgram://{bot_token}/{chat_id}/


# Slack (https://github.com/caronc/apprise/wiki/Notify_slack)
https://hooks.slack.com/services/{tokenA}/{tokenB}/{tokenC}

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

Re-read this documentation.  Verify your JSON.

I suggest joining the #tech-support channel in [Discord](https://discord.gg/qDY2QBtAW6) for help from the community if these common fixes don't help.

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
git clone https://github.com/Hari-Nagarajan/fairgame
cd fairgame/
pip3 install pipenv
export PATH=$PATH:/home/<YOURUSERNAME>/.local/bin
pipenv shell 
pipenv install
```
2. Leave this Terminal window open.

3. Open the following file in a text editor: 
```
/home/<YOURUSERNAME>/.local/share/virtualenvs/fairgame-<RANDOMCHARS>/lib/python3.7/site-packages/selenium/webdriver/common/service.py
```
4. Edit line 38 from `self.path = executable` to `self.path = "chromedriver"`, then save and close the file.


5. Back in Terminal...
```shell
python app.py
```

6. Follow [Usage](#Usage) to configure the bot as needed.

## Frequently Asked Questions

### 1. Can I run multiple instances of the bot? 
Yes. For example you can run one instance to check stock on Best Buy and a separate instance to check stock on Amazon. Bear in mind that if you do this you may end up with multiple purchases going through at the same time.

### 2. Does Fairgame automatically bypass CAPTCHA's on the store sites?
* For Amazon, yes. The bot will try and auto-solve CAPTCHA's during the checkout process.

## Attribution

Notification sound from https://notificationsounds.com.
