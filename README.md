# Fairgame

[Installation](#Installation) | [Usage](#Usage) | [Discord](https://discord.gg/4rfbNKrmnC) | [Troubleshooting](#Troubleshooting)

## Why???

We built this in response to the severe tech scalping situation that's happening right now. Almost every tech product
that's coming out right now is being instantly brought out by scalping groups and then resold at at insane prices. $699
GPUs are being listed for $1700 on eBay, and these scalpers are buying 40 cards while normal consumers can't get a
single one. Preorders for the PS5 are being resold for nearly $1000. Our take on this is that if we release a bot that
anyone can use, for free, then the number of items that scalpers can buy goes down and normal consumers can buy items
for MSRP.

**If everyone is botting, then no one is botting.**

## Requirements

This project requires a recent 3.8 version of a python branch, 3.8.5 and more recent have been tested, 3.8.8 is preferred. 3.7, 3.9, 3.10 branches will not work. It also requires a working Chrome installation. Running it off a potato is not suggested. 

## Quick Start

Here are the very simple steps for running the bot (on Windows):
1. Turn on your computer
2. Install Python 3.8.5, 3.8.6, 3.8.7 or 3.8.8. Install to some location that does not include spaces in the path (I suggest C:\Python38). Click the checkbox that says Add Python 3.8 to PATH (or something similar) during the installation
3. Download GitHub Desktop and Open the FairGame Repository with GitHub Desktop (or download the zip file). Again, make sure this installs to a location without spaces in the path. If you need help with this, look at Wiki.
4. Open the FairGame folder in File Explorer. Double click __INSTALL (RUN FIRST).bat Don't use admin
5. After this finishes (it could take a few minutes or longer), make a copy of the amazon_config.template_json file, and rename it to amazon_config.json. If you don't know how to rename file extensions, look it up on Google
6. Edit the amazon_config.json, this assumes US using smile.amazon.com. Find a product, like a USB stick that is in stock, and put the ASIN for that product in place of the B07JH53M4T listed below (or use that if it is in stock). Change the reserve_min_1 and reserve_max_1 to be below and above the price of the item, respectively: 
```
{
  "asin_groups": 1,
  "asin_list_1": ["B07JH53M4T"],
  "reserve_min_1": 5,
  "reserve_max_1": 15,
  "amazon_website": "smile.amazon.com"
}
```
7. In File Explorer, double click the `_Amazon.bat` file in the FairGame folder. Type in your amazon email address when asked for your amazon login ID. Type in your amazon account password when asked for your amazon password. Type in a password for your credentials (this can be whatever you want, it just encrypts your account email/password file)
8. Verify that the bot successfully makes it to the place your order page with the item you put in the config file. If it does not, then you messed something up above. Fix it
9. Edit the config file with what you want
10. Remove `--test` from `_Amazon.bat`
11. Run `_Amazon.bat` and wait


## Current Functionality

Only Amazon auto-checkout.

## Got a question?

Read through this document and the cheat sheet linked in the next sections. See the [FAQs](#frequently-asked-questions)
if that does not answer your questions.

## Known Issues

--no-image can cause the flyout from Amazon not to work, which causes time out issues. Something to do with the javascript that loads, if you have solutions for a fix, all ears.

Pipenv does not like spaces in file paths, so you will either need to run from a place where you do not have spaces in the file path, or set the option for pipenv to run locally in relation to the current file directory with:
```shell
set PIPENV_VENV_IN_PROJECT=1 (Windows) 
export PIPENV_VENV_IN_PROJECT=1 (Linux/Other)
```

Running the bot minimized can cause time out errors due to how Selenium acts with various versions of Chrome. 

OTP doesn't work in headless. Turn it off when starting up a headless instance, then turn it back on afterwords. 

## Installation

Community user Easy_XII has created a great cheat sheet for getting started. It includes specific and additional steps
for Windows users as well as useful product and configuration information. Please start
with [this guide](https://docs.google.com/document/d/14kZ0SNC97DFVRStnrdsJ8xbQO1m42v7svy93kUdtX48) to get you started
and to answer any initial questions you may have about setup.

**Note:** The above document is community maintained and managed. The authors of Fairgame do not control the contents,
so use some common sense when configuring the bot as both the bot and the sites we interact with change over time. For
example, do not ask us why the bot does not purchase an item whose price has changed to $8.49 when the _minimum_
purchase price is set to $10 in the configuration file that YOU are supposed to update

### General
FairGame should be able to (theoretically) run on any device that has an internet connection and can run Python 3.8.5 or newer and the required dependencies, so these are generic instructions for installation. As indicated above, there are Windows specific instructions provided in the "cheat sheet". In addition, we have some specific platform instructions found in the Platform Specific section below. If you aren't running Windows, or one of the platforms mentioned below, just install Python 3.8.5 or newer, and try the instructions below.

This project uses [Pipenv](https://pypi.org/project/pipenv/) to manage dependencies. Hop in
my [Discord](https://discord.gg/4rfbNKrmnC) if you have ideas, need help or just want to tell us about how you got your
new toys.

To get started, there are two options:

#### Releases

To get the latest release as a convenient package, download it directly from
the [Releases](https://github.com/Hari-Nagarajan/fairgame/releases)
page on GitHub. The "Source code" zip or tar file are what you'll want. This can be downloaded and extracted into a
directory of your choice (e.g. C:\fairgame).

#### Git

If you want to manage the code via Git, you'll first need to clone this repository. If you are unfamiliar with Git,
follow the [guide](https://github.com/Hari-Nagarajan/fairgame/wiki/How-to-use-GitHub-Desktop-App) on how to do that on
our Wiki . You *can* use the "Download Zip" button on the GitHub repository's homepage but this makes receiving updates
more difficult. If you can get setup with the GitHub Desktop app, updating to the latest version of the bot takes 1
click.

!!! YOU WILL NEED TO USE THE 3.8 BRANCH OF PYTHON, 3.9.x BREAKS DEPENDENCIES !!!

It is best if you use the newest version (3.8.8) but 3.8.5, 3.8.6, and 3.8.7 should also work. 3.8.0 does not.

```shell
pip install pipenv
pipenv shell 
pipenv install
```

NOTE: YOU SHOULD RUN `pipenv shell` and `pipenv install` ANY TIME YOU UPDATE, IN CASE THE DEPENDENCIES HAVE CHANGED!

Run it

```shell
python app.py

Usage: app.py [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  amazon
```

### Platform Specific

These instructions are supplied by community members and any adjustments, corrections, improvements or clarifications
are welcome. These are typically created during installation in a single environment, so there may be caveats or changes
necessary for your environment. This isn't intended to be a definitive guide, but a starting point as validation that a
platform can/does work. Please report back any suggestions to our [Discord](https://discord.gg/qDY2QBtAW6) feedback
channel.

### Installation MacOS 

Usage on Mojave (10.14) and above. Previous versions of macOS may not be compatible.

Ensure you have Python 3.8.5+ (3.8.8 recommended) installed on your system. If not, you can download it from 
https://www.python.org/downloads/release/python-388/ in the Files section near the bottom of the page. Make sure 
to choose macOS 64-bit installer. Once downloaded, you can go through the installer's setup steps.

Download the ZIP of Fairgame from GitHub, or clone it with `git clone https://github.com/Hari-Nagarajan/fairgame`. 

Open up the terminal on macOS (can be found in /Utilities in /Applications in Finder) and type `cd folderLocationHere/Fairgame`. 
If you do not know where the folder is located, type `cd ` and then drag the Fairgame folder ontop of the terminal window 
and let go. It then should autofill the folder path.

Type `pip3 install pipenv` and hit enter.

Type `pipenv shell` and hit enter. 

Type `pipenv install` and hit enter. 

Type `python app.py amazon` and go through setup. You will also need to set up the config file, seen below in the Configuration section

### Installation Ubuntu 20.10 (and probably other distros)

Based off Ubuntu 20.10 with a fresh installation.

Open terminal. Either right click desktop and go to Open In Terminal, or search for Terminal under Show Applications

Install Google Chrome:
`wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo dpkg -i google-chrome-stable_current_amd64.deb`

Install Pip:
`sudo apt install python3-pip`

Install pipenv:
`pip3 install pipenv`

Add /home/$USER/.local/bin to PATH:
`export PATH="/home/$USER/.local/bin:$PATH"`

Install git:
`sudo apt install git`

Clone git repository:
`git clone https://github.com/Hari-Nagarajan/fairgame`

Change into the fairgame folder:
`cd ./fairgame/`

Prepare your config files within ./config/

```shell
cp ./config/amazon_config.template_json ./config/amazon_config.json
cp ./config/apprise.conf_template ./config/apprise.conf
```

Make a pipshell environment:
`pipenv shell`

Install dependencies:
`pipenv install`

Edit the newly created files with your settings based on your [configuration](#configuration)

### Installation Raspberry Pi 4 (2 GB+)

This is an abridged version of the community created document by UnidentifiedWarlock and Judarius.  It can be 
found [here](https://docs.google.com/document/d/1VUxXhATZ8sZOJxdh3AIY6OGqwLRmrAcPikKZAwphIE8/edit). If the steps here
don't work on your Pi 4, look there for additional options. This hasn't been tested on a Pi 3, but given enough RAM to
run Chrome, it may very well work. Let us know. 

```shell
sudo apt update
sudo apt upgrade
sudo apt-get install -y build-essential tk-dev libncurses5-dev libncursesw5-dev libreadline6-dev libdb5.3-dev libgdbm-dev libsqlite3-dev libssl-dev libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev libzbar-dev clang libxslt1-dev rustc

version=3.8.8

wget https://www.python.org/ftp/python/$version/Python-$version.tgz

tar zxf Python-$version.tgz
cd Python-$version
./configure --enable-optimizations
make -j4
sudo make altinstall

sudo python3 -m pip install --upgrade pip

sudo apt install chromium-chromedriver
git clone https://github.com/Hari-Nagarajan/fairgame
cd fairgame/
pip3 install pipenv
export PATH=$PATH:/home/$USER/.local/bin
pipenv shell 
pipenv install
cp /usr/bin/chromedriver /home/fairgame/.local/share/virtualenvs/fairgame-<RANDOMCHARS>/lib/python3.8/site-packages/chromedriver_py/chromedriver_linux64
```

Leave this Terminal window open.

Open the following file in a text editor:

`/home/$USER/.local/share/virtualenvs/fairgame-<RANDOMCHARS>/lib/python3.8/site-packages/selenium/webdriver/common/service.py`

Edit line 38 from

`self.path = executable`

to

`self.path = "chromedriver"`

Then save and close the file.

## Usage

### Amazon

TL;DR Notes:
* By default, bot will only purchase new items with free shipping.
* Running the FairGame with the `_Amazon.bat` is easiest. You should change the name of the `_Amazon.bat` file though, so it does not overwrite any changes you made (adding flags, removing `--test`, etc.)
* Make a copy of the `amazon_config.template_json` file, and rename it to `amazon_config.json`. Modify it as _you_ see fit, with ASINs and min/max reserve prices as you think they should be set.
* **DO NOT ADD STUFF TO YOUR CART WHILE THE BOT IS RUNNING - IF IT ATTEMPTS TO CHECKOUT, AND THERE ARE ITEMS IN THE CART, BUT YOUR TARGET ITEM DOES NOT ADD TO CART CORRECTLY, IT WILL PURCHASE WHATEVER WAS IN THE CART AND THINK THAT IT PURCHASED YOUR TARGET ITEM.**
* **EVEN THOUGH THIS IS "TL;DR" YOU STILL NEED TO READ THE WHOLE THING!**

The following flags are specific to the Amazon scripts. They the `[OPTIONS]` to be passed on the command-line to control
the behavior of Amazon scanning and purchasing. These can be added at the command line or added to a batch file/shell
script (see `_Amazon.bat` in the root folder of the project). **NOTE:** `--test` flag has been added to `_Amazon.bat`
file by default. This should be deleted after you've verified that the bot works correctly for you. If you don't want
your `_Amazon.bat`
to be deleted when you update, you should rename it to something else.

#### Amazon flags ####

```shell
python app.py amazon --help

Usage: app.py amazon option

Options:
  --no-image          Do not load images
  --headless          Runs Chrome in headless mode.
  --test              Run the checkout flow but do not actually purchase the
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

  --disable-presence  Disable Discord Rich Presence functionallity, this stops discord from seeing what you are doing.
  --disable-sound     Disable local sounds.  Does not affect Apprise
                      notification sounds.

  --slow-mode         Uses normal page load strategy for selenium. Default is
                      none

  --p TEXT            Pass in encryption file password as argument
  --log-stock-check   Will log each stock check to terminal and log file
  --shipping-bypass   Bot will attempt to click "Ship to this Address" button,
                      if it pops up during checkout. 
                      USE THIS OPTION AT YOUR OWN RISK!!!
                      NOTE: There is no functionality to choose payment
                      option, so bot may still fail during checkout
                      
  --help              Show this message and exit.
```

#### Configuration

Make a copy of `amazon_config.template_json` and rename to `amazon_config.json`. Edit it according to the ASINs you are
interested in purchasing.  [*What's an
ASIN?*](https://www.datafeedwatch.com/blog/amazon-asin-number-what-is-it-and-how-do-you-get-it#how-to-find-asin)

* `asin_groups` indicates the number of ASIN groups you want to use.
* `asin_list_x` list of ASINs for products you want to purchase. You must locate these (see Discord or lookup the ASIN
  on product pages).
    * The first time an item from list "x" is in stock and under its associated reserve, it will purchase it.
    * If the purchase is successful, the bot will not buy anything else from list "x".
    * Use sequential numbers for x, starting from 1. x can be any integer from 1 to 18,446,744,073,709,551,616
* `reserve_min_x` set a minimum limit to consider for purchasing an item. If a seller has a listing for a 700 dollar
  item a 1 dollar, it's likely fake.
* `reserve_max_x` is the most amount you want to spend for a single item (i.e., ASIN) in `asin_list_x`. Does not include
  tax. If --checkshipping flag is active, this includes shipping listed on offer page.
* `amazon_website` amazon domain you want to use. smile subdomain appears to work better, if available in your
  country. [*What is Smile?*](https://org.amazon.com/)

##### Examples

One unique product with one ASIN (e.g., Segway Ninebot S and GoKart Drift Kit Bundle) :

```json
{
  "asin_groups": 1,
  "asin_list_1": [
    "B07K7NLDGT"
  ],
  "reserve_min_1": 450,
  "reserve_max_1": 500,
  "amazon_website": "smile.amazon.com"
}
```

One general product with multiple ASINS (e.g 16 GB USB drive 2 pack)

```json
{
  "asin_groups": 1,
  "asin_list_1": [
    "B07JH53M4T",
    "B085M1SQ9S",
    "B00E9W1ULS"
  ],
  "reserve_min_1": 15,
  "reserve_max_1": 20,
  "amazon_website": "smile.amazon.com"
}
```

Two general products with multiple ASINS and different price points (e.g. 16 GB USB drive 2 pack and a statue of The
Thinker)

```json
{
  "asin_groups": 2,
  "asin_list_1": [
    "B07JH53M4T",
    "B085M1SQ9S",
    "B00E9W1ULS"
  ],
  "reserve_min_1": 15,
  "reserve_max_1": 20,
  "asin_list_2": [
    "B006HPI2A2",
    "B00N54S1WW"
  ],
  "reserve_min_2": 50,
  "reserve_max_2": 75,
  "amazon_website": "smile.amazon.com"
}
```

If you wanted to watch another product, you'd add a third list (e.g. `asin_list_3`) and associated min/max pricing and
increase the `asin_groups` to 3. Add as many lists as are needed, keeping in mind that the main distinction between
lists is the min/max price boundaries. Once any ASIN is purchased from an ASIN list, that list is remove from the hunt
until FairGame is restarted.

To verify that your JSON is well formatted, paste and validate it at https://jsonlint.com/

#### Start Up

On first launch the bot will prompt you for your Amazon credentials. You will then be asked for a password to encrypt them. Once done, your
encrypted credentials will be stored in
`amazon_credentials.json`. If you ever forget your encryption password, just delete this file and the next launch of the
bot will recreate it. An example of this will look like the following:

```shell
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

```shell
python app.py amazon --test
INFO Initializing Apprise handler
INFO Initializing other notification handlers
INFO Enabled Handlers: ['Audio']
Reading credentials from: amazon_credentials.json
Credential file password: <enter the previously created password>
```

Example usage:

```commandline
python app.py amazon --test
...
2021-03-04 08:49:47|0.6.1.dev5|WARNING|FairGame PRE-RELEASE v0.6.1.dev5
2021-03-04 08:49:47|0.6.1.dev5|INFO|Initializing Global configuration...
2021-03-04 08:49:47|0.6.1.dev5|INFO|Initializing Apprise handler using: config/apprise.conf
2021-03-04 08:49:47|0.6.1.dev5|INFO|Found Telegram configuration
2021-03-04 08:49:47|0.6.1.dev5|INFO|Found Discord configuration
2021-03-04 08:49:47|0.6.1.dev5|INFO|Initializing Amazon configuration...
2021-03-04 08:49:47|0.6.1.dev5|INFO|Reading credentials from: config/amazon_credentials.json
Credential file password: *********
2021-03-04 08:49:53|0.6.1.dev5|INFO|==================================================
2021-03-04 08:49:53|0.6.1.dev5|INFO|Starting Amazon ASIN Hunt on https://smile.amazon.com/ for 2 Products with:
2021-03-04 08:49:53|0.6.1.dev5|INFO|--Offer URL of: https://smile.amazon.com/dp/
2021-03-04 08:49:53|0.6.1.dev5|INFO|--Delay of 3.0 seconds
2021-03-04 08:49:53|0.6.1.dev5|INFO|--Free Shipping items only
2021-03-04 08:49:53|0.6.1.dev5|INFO|--Looking for 1 ASINs between 5.00 and 30.00
2021-03-04 08:49:53|0.6.1.dev5|INFO|--Looking for 1 ASINs between 650.00 and 850.00
2021-03-04 08:49:53|0.6.1.dev5|WARNING|--Testing Mode.  NO Purchases will be made.
2021-03-04 08:49:53|0.6.1.dev5|INFO|==================================================
2021-03-04 08:49:53|0.6.1.dev5|INFO|Waiting for home page.
2021-03-04 08:49:57|0.6.1.dev5|INFO|Lets log in.
2021-03-04 08:49:57|0.6.1.dev5|INFO|Already logged in
2021-03-04 08:50:18|0.6.1.dev5|INFO|Checking stock for items.
2021-03-04 08:50:20|0.6.1.dev5|INFO|Item in stock and in reserve range!
2021-03-04 08:50:25|0.6.1.dev5|INFO|clicking add to cart
2021-03-04 08:50:26|0.6.1.dev5|INFO|clicking checkout.
2021-03-04 08:50:27|0.6.1.dev5|INFO|Email
2021-03-04 08:50:28|0.6.1.dev5|INFO|Email not needed.
2021-03-04 08:50:29|0.6.1.dev5|INFO|Remember me checkbox
2021-03-04 08:50:30|0.6.1.dev5|INFO|Password
2021-03-04 08:50:33|0.6.1.dev5|INFO|enter in your two-step verification code in browser
2021-03-04 08:50:35|0.6.1.dev5|INFO|Logged in as me@gmail.com
2021-03-04 08:50:37|0.6.1.dev5|INFO|Found button , but this is a test
2021-03-04 08:50:39|0.6.1.dev5|INFO|will not try to complete order
2021-03-04 08:50:39|0.6.1.dev5|INFO|test time took 19.061731576919556 to check out

```

## Notifications

### Sounds

Local sounds are provided as a means to give you audible cues to what is happening. The notification sound plays for
notable events (e.g., start up, product found for purchase) during the scans. An alarm notification will play when user
interaction is necessary. This is typically when all automated options have been exhausted. Lastly, a purchase
notification sound will play if the bot if successful. These local sounds can be disabled via the command-line
and [tested](#testing-notifications) along with other notification methods

### Apprise

Notifications are now handled by Apprise. Apprise lets you send notifications to a large number of supported
notification services. Check https://github.com/caronc/apprise/wiki for a detailed list.

To enable Apprise notifications, make a copy of `apprise.conf_template` in the `config` directory and name it
`apprise.conf`. Then add apprise formatted urls for your desired notification services as simple text entries in the
config file. Any recognized notification services will be reported on app start.

##### Apprise Example Config:

```
# Hash Tags denote comment lines and blank lines are allowed
# Discord (https://github.com/caronc/apprise/wiki/Notify_discord)

https://discordapp.com/api/webhooks/{WebhookID}/{WebhookToken}

# Telegram
tgram://{bot_token}/{chat_id}/


# Slack (https://github.com/caronc/apprise/wiki/Notify_slack)
https://hooks.slack.com/services/{tokenA}/{tokenB}/{tokenC}

```

### Pavlok

To enable shock notifications to
your [Pavlok Shockwatch](https://www.amazon.com/Pavlok-PAV2-PERIMETER-BLACK-2/dp/B01N8VJX8P?), store the url from the
pavlok app in the ```pavlok_config.json``` file, you can copy the template from ```pavlok_config.template_json```.

**WARNING:** This feature does not currently support adjusting the intensity, it will always be max (255).

```json
{
  "base_url": "url goes here"
}
```

### Testing notifications

Once you have setup your `apprise_config.json ` you can test it by running `python app.py test-notifications` from
within your pipenv shell. This will send a test notification to all configured notification services.

## Troubleshooting

+ Re-read this documentation.

+ Verify your JSON.

+ Consider joining the #tech-support channel in [Discord](https://discord.gg/5tw6UY7g44) for help from the community if
  these common fixes don't help.

+ **Error: ```selenium.common.exceptions.WebDriverException: Message: unknown error: cannot find Chrome binary```**
  The issue is that chrome is not installed in the expected location.
  See [Selenium Wiki](https://github.com/SeleniumHQ/selenium/wiki/ChromeDriver#requirements) and the section
  on [overriding the Chrome binary location .](https://sites.google.com/a/chromium.org/chromedriver/capabilities#TOC-Using-a-Chrome-executable-in-a-non-standard-location)

  The easy fix for this is to add an option where selenium is used (`selenium_utils.py`)

  ```
  python chrome_options.binary_location = "C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe"
  ```

+ **Error: ```selenium.common.exceptions.SessionNotCreatedException: Message: session not created: This version of ChromeDriver only supports Chrome version 87```**

  You are not running the proper version of Chrome this requires. As of this update, the current version is Chrome 87.
  Check your version by going to ```chrome://version/``` in your browser. We are going to be targeting the current stable
  build of chrome. If you are behind, please update, if you are on a beta or canary branch, you'll have to build your own
  version of chromedriver-py.

## Frequently Asked Questions

To keep up with questions, the Discord channel [#FAQ](https://discord.gg/GEsarYKMAw) is where you'll find the latest
answers. If you don't find it there, ask in #tech-support.

1. **Can I run multiple instances of the bot?**

   While possible, running multiple instances are not a supported usage case. You are on your own to figure this one out.

2. **Does Fairgame automatically bypass CAPTCHA's on the store sites?**
   For Amazon, yes. The bot will try and auto-solve CAPTCHA's during the checkout process.

3. **Does Fairgame run on a Raspberry Pi?**
   Yes, with caveats. Most people seem to have success with Raspberry Pi 4. The 2 GB model may need to run the headless
   option due to the smaller memory footprint. Still awaiting community feedback on running on a Pi 3. CPU and memory
   capacity seem to be the limiting factor for older Pi models.

## Attribution

Notification sound from https://notificationsounds.com.
