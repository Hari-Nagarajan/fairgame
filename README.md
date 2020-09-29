# nvidia-bot

[Installation](#Installation) | [Usage](#Usage) | [Discord](https://discord.gg/hQeUbRv)  | [Troubleshooting](#Troubleshooting)

## Why???

I built this in response to the severe tech scalping situation that's happening right now. Almost every tech product that's coming
out right now is being instantly brought out by scalping groups and then resold at at insane prices. $699 GPUs are being listed
for $1700 on eBay, and these scalpers are buying 40 carts while normal consumers can't get a single one. Preorders for the PS5 are
being resold for nearly $1000. My take on this is that if I release a bot that anyone can use, for free, then the number of items 
that scalpers can buy goes down and normal consumers can buy items for MSRP. If everyone is botting, then no one is botting. 

## Installation

For Raspberry Pi installation and setup, go [here](#Raspberry-Pi-Setup).

This project uses [Pipenv](https://pypi.org/project/pipenv/) to manage dependencies. Hop in my [Discord](https://discord.gg/hQeUbRv) if you have ideas, need help or just want to tell me about how you got your new 3080. [TerryFrench](https://github.com/TerryFrench) has also created a youtube video detailing how to get this project running on Windows 10 as well. Huge thanks to him. 

[![Alt text](https://img.youtube.com/vi/TvOQubunx6o/0.jpg)](https://www.youtube.com/watch?v=TvOQubunx6o)


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

## Current Functionality

| **Website** | **Auto Checkout** | **Open Cart Link** | **Test flag** |
|:---:|:---:|:---:|:---:|
| nvidia.com | |`✔`| |
| amazon.com |`✔`| | |
| bestbuy.com | |`✔`| |
| evga.com |`✔` | |`✔`|


## Usage

### Amazon 

***Warning***: This will buy every ASIN that is in stock the first time anything is in stock. So there is a possibility you can end up with multiple items.
Thankfully Amazon.com has 1 click order canceling so its not a huge issue. We are working on a solution for this and price limits soon.

**Amazon flags**
```
--no-image : prevents images from loading on amazon webdriver
--test : This will not finish the checkout
```

Make a copy of `amazon_config.template_json` to `amazon_config.json`:
```json
{
  "username": "",
  "password": "",
  "asin_list": ["B07JH53M4T","B08HR7SV3M"],
  "amazon_website": "amazon.com"
}
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

### Nvidia 
Will check stock and open an add to cart link in your browser and send notifications.

**Nvidia flags**
```
--test : runs a test of the checkout process, without actually making the purchase
--interval: How many seconds between each stock check (default: 5)
```

Example usage:
```python
python app.py nvidia
What GPU are you after?: 3080
What locale shall we use? [en_us]:
...
INFO: "2020-09-23 21:43:56,152 - We have 1 product IDs for NVIDIA GEFORCE RTX 3080
INFO: "2020-09-23 21:43:56,153 - Product IDs: ['5438481700']
INFO: "2020-09-23 21:43:56,153 - Checking stock for 5438481700 at 5 second intervals.
```

Quick run:
```python
python app.py nvidia --gpu 3080 --locale en_us
```

## Best Buy
This is fairly basic right now. Just login to the best buy website in your default browser and then run the command as follows:

```
python app.py bestbuy --sku [SKU]
```

Example:
```python
python app.py bestbuy --sku 6429440
```

## EVGA
Make a copy of `evga_config.template_json` to `evga_config.json`:
```json
{
  "username": "hari@",
  "password": "password!",
  "card_pn": "10G-P5-3895-KR",
  "card_series": "3080",
  "credit_card" : {
            "name": "Hari ",
            "number": "234234",
            "cvv": "123",
            "expiration_month": "12",
            "expiration_year": "2023"
        }
}
```

Test run command (Uses old gpu list and then stops before finishing the order)
`python app.py evga --test`

Autobuy command:
`python app.py evga`

These are the series: "3090" or "3080" (any should work, untested)

P/N numbers can be found in URLs or on product pages such as newegg. They look like this:
* 10G-P5-3895-KR
* 10G-P5-3881-KR
* 10G-P5-3885-KR 

![EVGA PN Screenshot](evga_pn.png)

if it doesn't load the correct page title (since the 3090 isn't listed yet), it will refresh every second until the correct page is loaded.


### Notifications
This uses a notifications handler that will support multiple notification channels. 

Once you've set up the notification handlers you want to use, be sure to test them using the [test-notifications command].(#testing-notifications).

#### Twilio
To enable Twilio notifications, first go to https://www.twilio.com/ and create a free account and get a Twilio number.
Then make a copy of `twilio_config.template_json` and name it `twilio_config.json`. If this file exists and the credentials are
valid, the notification handler will send you an sms when it carts or purchases an item.
```json
{
  "account_sid": "ACCOUNT_SID",
  "auth_token": "AUTH_TOKEN",
  "from": "YOUR TWILIO NUMBER",
  "to": "THE NUMBER YOU WANT TO SEND SMS TO"
}
```

#### Discord
To enable Discord notifications, first get your wehbook url. Use the directions [here](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks) to get the webhook url.
Make a copy of the `discord_config.template_json` file and name it `discord_config.json` and place the webhook url here. 
Optionally a [user id](https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID-) can be added to ping someone (like yourself).
```json
{
  "webhook_url": "Discord webhook url here",
  "user_id": "Optional user id to ping here"
}
```

#### Telegram
To enable Telegram notifications, you have to create a new bot and get your chat id. Use the directions [here](https://medium.com/@ManHay_Hong/how-to-create-a-telegram-bot-and-send-messages-with-python-4cf314d9fa3e) (Creating your bot and Getting your Chat id sections).

Make a copy of the `telegram_config.template_json` file and name it `telegram_config.json` and place your `BOT_TOKEN` and `BOT_CHAT_ID` values here. 
```json
{
    "BOT_TOKEN" : "1234567890:abcdefghijklmnopqrstuvwxyz",
    "BOT_CHAT_ID" : "111222333"
}
```

It is possible to notify multiple users at once. Just add a list as the `BOT_CHAT_ID` value:

```json
{
    "BOT_TOKEN" : "1234567890:abcdefghijklmnopqrstuvwxyz",
    "BOT_CHAT_ID" : ["111222333", "444555666"]
}
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

#### Join
To enable Join notifications, make a copy of the `join_config.template_json` file and name it `join_config.json`  
Go [here](https://joinjoaomgcd.appspot.com/) and select the device you want to notify.  
Click the `JOIN API` tab and paste the value next to `Device Id` into your `join_config.json` `deviceId` section.  
Next click the `SHOW` button next to `API Key` and copy that value into your `join_config.json` `apikey` section.
```json
{
  "apikey": "paste api key here",
  "deviceId": "paste device id here"
}
```

#### Testing notifications

Once you have setup your desired notification handlers you can test them by running `python app.py test-notifications` from within your pipenv shell. This will send a test notification to all configured notificaiton handlers.

## Troubleshooting

I suggest joining the #tech-support channel in [Discord](https://discord.gg/hQeUbRv) for personal assistance if these common fixes don't help.

**Error: ```selenium.common.exceptions.WebDriverException: Message: unknown error: cannot find Chrome binary```** 
The issue is that chrome is not installed in the expected location. See [Selenium Wiki](https://github.com/SeleniumHQ/selenium/wiki/ChromeDriver#requirements) and the section on [overriding the Chrome binary location .](https://sites.google.com/a/chromium.org/chromedriver/capabilities#TOC-Using-a-Chrome-executable-in-a-non-standard-location)

The easy fix for this is to add an option where selenium is used (amazon.py)
```python
chrome_options.binary_location="C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe"
```

**Error: ```selenium.common.exceptions.SessionNotCreatedException: Message: session not created: This version of ChromeDriver only supports Chrome version 85```**

You are not running the proper version of Chrome this requires. As of this update, the current version is Chrome 85. Check your version by going to ```chrome://version/``` in your browser. We are going to be targeting the current stable build of chrome. If you are behind, please update, if you are on a beta or canary branch, you'll have to build your own version of chromedriver-py.

## Raspberry-Pi-Setup

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

### 1. Can I run multiple instances of the bot?**  
Yes. For example you can run one instance to check stock on the Nvidia store and a separate instance to check stock on Amazon.

### 2. Does Nvidia Bot automatically bypass CAPTCHA's on the store sites?
No. If a CAPTCHA is shown the bot will inform you and you will be given 15 seconds to complete the CAPTCHA.

### 3. Can I add multiple P/N numbers to the EVGA bot 
Not currently. If you want to check for multiple card models you will need to run a separate instance of the bot for each model you want to check for.

## Attribution

Notification sound from https://notificationsounds.com.
