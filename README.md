# FairGame README

# Table of Contents:
* [About FairGame](#About-FairGame)
    * [Current Functionality](#Current-Functionality)
    * [Disclaimer](#Disclaimer) 
* [Installation](#Installation)
    * [Requirements](#Requirements)
    * [Quick Start](#Quick-Start)
    * [Detailed Directions](#Detailed-Directions)
        * [Python](#Python)
        * [Downloading FairGame](#Downloading-FairGame)
        * [Installing Dependencies](#Installing-Dependencies)
        * [Configuration](#Configuration)
        * [Proxies](#Proxies)
        * [Running the program](#Running-the-program)
        * [Optional settings](#Optional-settings)
        * [Start Up](#Start-Up)
    * [Other Installation Help](#Other-Installation-Help)
        * [ASINs](#ASINs)
        * [Platform Specific](#Platform-Specific)
* [Advanced Configuration](#Advanced-Configuration)
    * [Notifications](#Notifications)
        * [Sounds](#Sounds)
        * [Apprise](#Apprise)
        * [Testing notifications](#Testing-notifications)
    * [CLI Tools](#CLI-Tools)
        * [CDN Endpoints](#CDN-Endpoints)
        * [Routes](#Routes)
* [Issues Running FairGame](#Issues-Running-FairGame)
    * [Known Issues](#Known-Issues)
    * [Troubleshooting](#Troubleshooting)
    * [Frequently Asked Questions](#Frequently-Asked-Questions)
    

# Quick Links
 * [Discord](https://discord.gg/4rfbNKrmnC) **DO NOT ASK QUESTIONS IN DISCORD BEFORE READING THIS DOCUMENT**
 * [Python Download (3.8.9)](https://www.python.org/downloads/release/python-389/)

# About FairGame

We built this in response to the severe tech scalping situation that's happening right now. Almost every tech product
that's coming out right now is being instantly brought out by scalping groups and then resold at at insane prices. $699
GPUs are being listed for $1700 on eBay, and these scalpers are buying 40 cards while normal consumers can't get a
single one. Preorders for the PS5 are being resold for nearly $1000. Our take on this is that if we release a bot that
anyone can use, for free, then the number of items that scalpers can buy goes down and normal consumers can buy items
for MSRP.

**If everyone is botting, then no one is botting.**

## Current Functionality

**ALPHA BRANCH IS A WORK IN PROGRESS, ANY OF THE FOLLOWING STEPS IN THIS README ARE SUBJECT TO CHANGE**

FairGame Alpha only works on Amazon using smile.amazon.com as the domain and can automatically place an order.
### Other Notes on Functionality
* By default, FairGame Alpha will only purchase items with free shipping. Please see [Configuration](#Configuration) 
  if you would like to change this.
* FairGame Alpha is designed to check if each product is in stock simultaneously. It does this by creating a monitoring session for each ASIN in your `amazon_aio_config.json` file. If   you're checking 5 ASIN's with your configuration, all 5 ASIN's will be checked every 5 seconds by default with their own monitoring session that is not logged in to your Amazon account. If you're using proxies each monitoring session will be running through one proxy in your `proxies.json` file. If you're not using proxies each monitoring      session will run on your home IP. *DO NOT* expect support if you are running several ASIN's without proxies and get softbanned. See [Disclaimer](#Disclaimer).
* More than one instance of the program can be run concurrently, we do not encourage nor support this and will not 
  provide help in doing so.
* There is no functionality to stop and confirm information with your bank during checkout (sorry EU). If someone from
  EU wants to figure this out and submit a pull request, that would be great.
* FairGame organizes the products being checked into lists, and each list is subject to a minimum and maximum 
  purchase price range. Once an item is purchased from any list the checkout worker will close and the bot will need to be restarted in order to make more purchase.
* If Fairgame catches a drop and you see several `turbo-initiate` pages with a 200 status code this **VERY LIKELY** means that the drop is already gone and Amazon is serving you   a garbage page!

### Disclaimer 

WARNING: The use of this software can result in a Amazon restricting access to your account and make it difficult 
for you to purchase products, with or without the bot. By using this software, you acknowledge these risks. These restrictions
cannot and will not be resolved by the developer(s), nor can they be detected/resolved by the standard Amazon Customer Support,
as far as we are aware. If this happens, the only resolution is to stop all Amazon monitors (e.g., FairGame, Distill.io,
or other bots, etc.), wait, and hope the limits are lifted within a few days. If this is a major issue you should
consider avoiding use of this software. 

Account restrictions may be triggered by any of the following: 1) running multiple instances on one device, 2) running multiple instances on different devices, using the same account, regardless of their IP, proxy, or location, 3) configuring an instance to check stock too frequently/aggressively (default settings not guaranteed to be safe). 

Symptoms of account restrictions include: 1) Fly-out (offers) window is missing/completely blank, even if there are listings for the ASIN, 2) frequent CAPTCHA checks, 3) inability to access the My Account page, add items to your cart, or complete purchases; usually displayed as a 503 error (Amazon Dogs & “SORRY we couldn’t find that page” message). You’ll likely have to sit-out a few days of drops to resolve the throttle.

# Installation

## Requirements

***!!! YOU WILL NEED TO USE THE 3.8 BRANCH OF PYTHON, ANY OTHER BRANCH/VERSION (Anaconda, 2.7, 3.9.x, 3.10, 4.0,
toaster, etc.) BREAKS DEPENDENCIES !!!***

It is best if you use the newest version of **3.8** (at this time, 3.8.9) but 3.8.5, 3.8.6, 3.8.7, and 3.8.8 should also work. 

It also requires a working Chrome installation. 
Running it on a potato (<2GB of RAM) is not suggested. 

## Quick Start

Here are the very simple steps for running the bot on Windows, however most of these instructions should be followed
regardless of your OS (obviously you aren't running .bat files if you aren't on Windows, or using GitHub Desktop if not 
available on your OS). See [Platform Specific](#Platform-Specific) instructions for help installing Python and
dependencies in other operating systems:
1. [Turn on your computer](https://www.google.com/search?q=how+do+I+turn+on+my+computer)
2. [Install Python 3.8.9](https://www.python.org/downloads/release/python-389/). Install to some location that does not include spaces in the path 
   (we suggest C:\Python38). Click the checkbox that says Add Python 3.8 to PATH (or something similar) 
   during the installation.
   
   ![Add Python 3.8 to PATH](https://github.com/Hari-Nagarajan/fairgame/blob/master/docs/images/PythonInstalltoPath.png)
   
3. Download GitHub Desktop and Open the FairGame Repository for the [alpha branch](https://github.com/Hari-Nagarajan/fairgame/tree/alpha) with GitHub Desktop (or download the      zip file). 
   Again, make sure this installs to a location without spaces in the path, but it is *STRONGLY* suggested that you install
   to the root of the drive (e.g., C:\fairgame). If you need help with GitHub Desktop, look at the
   [Wiki](https://github.com/Hari-Nagarajan/fairgame/wiki/How-to-use-GitHub-Desktop-App).
   ![Step3](https://user-images.githubusercontent.com/20719891/117584052-6aae9300-b0bf-11eb-99a9-2734a3e594bc.jpg)
   
4. Open the FairGame folder in File Explorer. Double click __INSTALL (RUN FIRST).bat ***DON'T USE ADMINISTRATIVE MODE***.
   
   ![Run Install Batch file](https://user-images.githubusercontent.com/20719891/117584073-8c0f7f00-b0bf-11eb-9ddc-992ed0ca3436.jpg)
   
5. After this finishes (it could take a few minutes or longer), open the `config` folder in the FairGame folder, make 
   a copy of the amazon_aio_config.template_json file and rename it to amazon_config.json. If you don't know how to rename
   file extensions, look it up on [Google](https://www.google.com/search?q=how+do+I+rename+file+extensions+in+Windows).
   
   ![Config Folder](https://user-images.githubusercontent.com/20719891/117584140-004a2280-b0c0-11eb-8bdd-aa3ec2cf4c9f.jpg)
   
   ![Copy Template](https://user-images.githubusercontent.com/20719891/117584198-6cc52180-b0c0-11eb-8956-76e51f69c785.png)

6. Edit the amazon_aio_config.json, this assumes US using smile.amazon.com. Using Amazon Smile requires that you select
   a charity. If you do not know how to do this, use 
   [Google](https://www.google.com/search?q=how+do+i+select+a+charity+on+amazon+smile). 
   Find a product, like a USB stick that is in stock, and put the 
   [ASIN](https://www.google.com/search?q=what+is+an+ASIN) for that product in place of the B001XURP8G listed below 
   (or use that if it is in stock). Change the min-price and max-price to be below and above the price of the
   item, respectively. More about condition and merchant ID explained in [Configuration](#Configuration)
   ```json
   {
     "items": [
       {
         "asins": ["B001XURP8G"],
         "min-price": 9,
         "max-price": 11,
         "condition": "New",
         "merchant_id": "amazon"
       }
     ],
     "amazon_domain": "smile.amazon.com"
   }
   ```
   
   ![Edit Config file](https://user-images.githubusercontent.com/20719891/117584427-c5e18500-b0c1-11eb-9e0a-d17700b82742.jpg)

   
7. In File Explorer, double click the `_Amazon_aio.bat` file in the FairGame folder. ***DON'T USE ADMINISTRATIVE MODE***. 
   Type in your amazon email address when asked for your amazon login ID. Type in your amazon account password when 
   asked for your amazon password. Type in a password for your credentials (this can be whatever you want, it just 
   encrypts your account email/password file)
   
   ![AIO Bat file](https://user-images.githubusercontent.com/20719891/117584570-8cf5e000-b0c2-11eb-84c3-1de203014f58.jpg)
   
8. Verify that the bot successfully places an order with the item you put in the config file. **NOTE: WITH ALPHA, TEST MODE NO LONGER FUNCTIONS THE SAME WAY. YOU SHOULD TRY AND BUY SOMETHING TO VERIFY THE BOT WORKS FOR YOU!**
   If it does not, then:
   * You messed something up above, and need to fix it; or,
   * If the bot will not make a purchase on an in stock item and you are not softbanned, you need to do all of the following in a separate
     tab within the bots browser. Start the bot, wait for the homepage to load, then close out of the command prompt. This should allow you to perform the following steps in the      bots browser:
     * Make sure one-click purchasing is set up for your account, 
     * Verify there is a default payment method and default address associated with that payment method,
     * And then make a purchase manually in that separate tab of the bot's browser and verify that it 
       correctly sets your defaults for the browser. 
     * See [#faq on our Discord](https://discord.gg/GEsarYKMAw) for additional information.
     * ALSO see notes regarding EU and [current functionality](#Other-Notes-on-Functionality)
9. Edit the `amazon_aio_config.json` file with the item(s) you want to look for. See [Configuration](#Configuration) 
   and [Configuration Examples](#Configuration-Examples) for additional information
   
10. Run `_Amazon_aio.bat` and wait


Every request Fairgame performs is saved in the `html_saves` folder. Whenever something comes in stock you will see a file called `turbo-initiate_...` (assuming the bot saw the stock). Iff turbo-initiate is succesful the bot will try to call turbo_checkout which will save a file called `turbo_checkout_...`, and if it thinks it placed an order it will save a file called `order-confirm_...`

![html_saves_success](https://user-images.githubusercontent.com/20719891/117584813-db57ae80-b0c3-11eb-991c-034b689c4e24.jpg)

For regular stock checks on an out of stock item you will most commonly see:
   * `stock-check_200...`
   * `stock-check_503...`
 
The bot will not be able to purchase items if it is getting served a 503 page. Check [Disclaimer](#Disclaimer) for more info about 503 pages. The `html_saves` folder is an excellent tool to help diagnose issues.


Additional information about running FairGame can be found in the rest of the documentation.

## Detailed Directions
### Python
This project uses Python 3.8.X and uses [Pipenv](https://pypi.org/project/pipenv/) to manage dependencies. 

### Downloading FairGame
To get started, there are two options:
#### Releases

To get the latest release as a convenient package, download it directly from
the [Releases](https://github.com/Hari-Nagarajan/fairgame/releases)
page on GitHub. The "Source code" zip or tar file are what you'll want. This can be downloaded and extracted into a
directory of your choice, it is *STRONGLY* suggested that you install to the root of the drive (e.g., C:\fairgame).

#### Git

If you want to manage the code via Git, you'll first need to clone this repository. If you are unfamiliar with Git,
follow the [guide](https://github.com/Hari-Nagarajan/fairgame/wiki/How-to-use-GitHub-Desktop-App) on how to do that on
our [Wiki](https://github.com/Hari-Nagarajan/fairgame/wiki/How-to-use-GitHub-Desktop-App). 
You *can* use the "Download Zip" button on the GitHub repository's homepage but this makes receiving updates
more difficult. If you can get setup with the GitHub Desktop app, updating to the latest version of the bot takes 1
click. Regardless, it is *STRONGLY* suggested that you install to the root of the drive (e.g., C:\fairgame)

### Installing Dependencies
If you are on Windows, use `INSTALL (RUN FIRST).bat`. ***Do NOT use administrative mode***

If you are not on Windows, do the following:

```shell
pip install pipenv
pipenv install
```
`pipenv install` must be run in the project's folder.

**NOTE: YOU SHOULD RUN `pipenv install` ANY TIME YOU UPDATE, IN CASE THE DEPENDENCIES HAVE CHANGED!**

### Configuration

In the `config` folder, make a copy of `amazon_aio_config.template_json` and 
[rename](https://www.google.com/search?q=how+to+change+file+extensions+on+windows+10) it to `amazon_aio_config.json`. Edit it 
according to the 
[ASINs](https://www.datafeedwatch.com/blog/amazon-asin-number-what-is-it-and-how-do-you-get-it#how-to-find-asin) you are
interested in purchasing. You can find a list of ASINs for some common products people are looking for on our 
Discord [#asins](https://discord.gg/DuVXAN5FnN). If it's not in there, you have to look it up yourself.

* `items`: items is a list that contains [Python dictionaries](https://www.w3schools.com/python/python_dictionaries.asp) with the following keys: (asins, min-price, max-price,     condition, and merchant_id). You can create multiple dictionaries using these keys if you want to check multiple ASINs with a different min/max price or                         condition/merchant_id.
    * The first time an item from any `asins` list is in stock and under its associated reserve, it will attempt to purchase it. Currently, FairGame 
      will continue to loop through the other ASIN's, but the checkout worker will only make one purchase so the bot must be started again to make further purchases.
* `min-price`: set a minimum limit to consider for purchasing an item. If a seller has a listing for a 700 dollar
  item a 1 dollar, it's likely fake.
* `max-price`: is the most amount you want to spend for a single item (i.e., ASIN) in `asins`. Does not include
  tax.
* `condition`: Please see the image below to determine the different values that can be used. As an example, if you put `Used` in your config it will attempt to purchase anything that is Used or above it (Good, Refurbished, New, etc)
![alpha_conditions](https://user-images.githubusercontent.com/20719891/117585270-59b55000-b0c6-11eb-8fed-72c468022f96.jpg)

* `merchant_id`: Use `amazon` if you want to only consider offers that are sold by Amazon. Use `any` if you want to consider offers from Amazon and Third Parties (potential scalpers or scammers)

* `amazon_domain`: **(CURRENTLY ONLY SUPPORTING smile.amazon.com SO AS OF RIGHT NOW DOES NOTHING)**
   Amazon domain you want to use. smile subdomain appears to work better, if available in your
   country. [*What is Smile?*](https://org.amazon.com/) Note that using Amazon Smile requires you to pick a charity.
   If you do not do so, you will not be able to purchase anything, and you will likely have problems running FairGame.

#### Adjusting Delay

The default delay is 5 seconds. Check [optional settings](#Optional-settings) for details on how to change the delay.

#### Check ASIN's with a Shipping Price

In order to adjust the `check_shipping` option you must edit the `amazon_monitoring.py` file the same as above.

Use `CTRL+F` to search for `check_shipping` and find the line: 

`def get_qualified_seller(item, sellers, check_shipping=False) -> SellerDetail or None:`

Replace 'False' with 'True' and save. Your bot will now consider offers that have a shipping price.

#### Configuration Examples

One unique product with one ASIN (e.g., Segway Ninebot S and GoKart Drift Kit Bundle), seraching for New offers from Amazon only:

```json
{
  "items": [
    {
      "asins": ["B07K7NLDGT"],
      "min-price": 400,
      "max-price": 500,
      "condition": "New",
      "merchant_id": "amazon"
    }
  ],
  "amazon_domain": "smile.amazon.com"
}
```

One general product with multiple ASINS (e.g 16 GB USB drive 2 pack),  searching for New offers from any seller:

```json
{
  "items": [
    {
      "asins": ["B07K7NLDGT", "B085M1SQ9S", "B00E9W1ULS"],
      "min-price": 15,
      "max-price": 20,
      "condition": "New",
      "merchant_id": "any"
    }
  ],
  "amazon_domain": "smile.amazon.com"
}
```

Two general products with multiple ASINS and different price points (e.g. 16 GB USB drive 2 pack and a statue of The
Thinker). Both are checking for Used (or above) condition, and only considering offers from Amazon.

```json
{
  "items": [
    {
      "asins": ["B07JH53M4T", "B085M1SQ9S", "B00E9W1ULS"],
      "min-price": 15,
      "max-price": 20,
      "condition": "Used",
      "merchant_id": "amazon"
    },
    {
      "asins": ["B006HPI2A2", "B00N54S1WW"],
      "min-price": 50,
      "max-price": 75,
      "condition": "Used",
      "merchant_id": "amazon"
    }
  ],
  "amazon_domain": "smile.amazon.com"
}
```
If you wanted to watch another product, you'd add a third dictionary to the `items` list (copy and paste) and  adjust the associated asins, min/max pricing, condition, and
merchant_id. Add as many dictionaries as are needed, keeping in mind that the main distinction between
dictionaries is the min/max price boundaries. Once any ASIN is purchased from an `asins` list the checkout worker will stop and the program must be restarted in order to purchase again.

To verify that your JSON is well formatted, paste and validate it at https://jsonlint.com/

### Proxies

In the `config` folder, make a copy of `proxies.template_json` and 
[rename](https://www.google.com/search?q=how+to+change+file+extensions+on+windows+10) it to `proxies.json`. Edit it 
according to your proxy list, the process for editing the proxies json is the same as editing the aio_config json.

We do not have any recommendations for which proxies are better or worse, try asking [Google](https://www.google.com/search?q=where+to+buy+proxies).

#### Examples

Http User/Pass Authentication:
```json
{
    "proxies": [
        {
            "http": "http://user:password@ipaddress:port",
            "https": "http://user:password@ipaddress:port"
        },
        {
            "http": "http://joe:my_pass!2@192.111.222.333:1234",
            "https": "http://joe:my_pass!2@192.111.222.333:1234"
        }
    ]
}
```

Socks5 User/Pass Authentication:
```json
{
    "proxies": [
        {
            "http": "socks5://user:password@ipaddress:port",
            "https": "socks5://user:password@ipaddress:port"
        },
        {
            "http": "socks5://joe:my_pass!2@192.111.222.333:1234",
            "https": "socks5://joe:my_pass!2@192.111.222.333:1234"
        }
    ]
}
```

Http IP Authentication: **You must authenticate your IP with your proxy provider in order to use this format**
```json
{
    "proxies": [
        {
            "http": "http://ipaddress:port",
            "https": "http://ipaddress:port"
        },
        {
            "http": "http://192.111.222.333:1234",
            "https": "http://192.111.222.333:1234"
        }
    ]
}
```

Socks5 IP Authentication: **You must authenticate your IP with your proxy provider in order to use this format**
```json
{
    "proxies": [
        {
            "http": "socks5://ipaddress:port",
            "https": "socks5://ipaddress:port"
        },
        {
            "http": "socks5://192.111.222.333:1234",
            "https": "socks5://192.111.222.333:1234"
        }
    ]
}
```
[What is a Python dictionary?](https://www.w3schools.com/python/python_dictionaries.asp)

The second dictionary in each example contains values so you can see what it should look like with actual values. Each proxy gets assigned to one dictionary and each dictionary has a value for the http and https keys. Putting the same proxy for both keys ensures the proxy is used for both http and https requests.

Make a dictionary for each proxy you want to add. If you have 10 ASIN's in your aio_config file and 10 dictionaries in your proxies config file then each monitoring session will get assigned an ASIN. The first dictionary will get assigned to the first ASIN, second dictionary gets assigned to the second ASIN, etc.

#### Troubleshooting Proxies

You can easily diagnose which proxies are giving you issues by utilizing the `html_saves` folder. Each check will store a save of the HTML page it received and sometimes you may see 503 errors only appearing for certain ASINs. 

![proxy_503](https://user-images.githubusercontent.com/20719891/117586652-5a51e480-b0ce-11eb-95c5-7cdc0285b0b7.jpg)

You can see in the above image how I am only receiving 503 errors for ASIN's: B08L8HPKR6 & B08L8L71SM. This tells me that I likely need to replace those proxies (or at the very least give them a break).

![proxies_troubleshoot](https://user-images.githubusercontent.com/20719891/117586748-f0860a80-b0ce-11eb-9ddb-294630bfea67.jpg)

By looking at your config you will be able to determine which proxies need to be replaced. In the above example I can see that the proxies in the 2nd and 7th dictionaries need to be replaced in the `proxies.json` file.

If you want to add the ASIN to your html_saves files, open `amazon_monitoring.py` with a text editor. The file is located in the `stores` folder. If you do not know how to open files with a text editor do not attempt this step.

   1. `CTRL+F` and search for `save_html`
   2. Find the line `save_html_response("stock-check", status, response_text)` and replace it with: 
      
      `save_html_response(f"{self.item.id}_stock-check", status, response_text)`
   4. There are 2 lines that need to be changed.
   
### Running the program
Run the program by double clicking on the _Amazon_aio.bat file (or whatever you renamed it to). 
***DO NOT RUN THE BATCH FILE WITH ADMINISTRATIVE MODE***

If you are not on Windows, you can run the bot with the following command:

```shell
pipenv run python app.py amazon-aio
```

#### Optional settings

```options
pipenv run python app.py amazon-aio [Options]

Options:
   --delay FLOAT       Time to wait between the end of one stock check and the beginning of the next stock check.
```

**!*!*Currently thes options below are not available with the Alpha branch, but some may be added again in the future!*!***

```old_options
pipenv run python app.py amazon-aio [Options]

Options:
  --headless          Runs Chrome in headless mode.
  
  --test              Run the checkout flow but do not actually purchase the item[s]. Only functional with `--alt-checkout` mode.
  
  --alt-checkout      Utilize the old add to cart method of checkout.
  
  --checkshipping     Also include items with a shipping price in the search.
                      Shipping costs are factored into reserve price check calculation.

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

  --slow-mode         Uses normal page load strategy for selenium. Default is none

  --p TEXT            Pass in encryption file password as argument
  
  --log-stock-check   Will log each stock check to terminal and log file
  
  --shipping-bypass   Bot will attempt to click "Ship to this Address" button,
                      if it pops up during checkout. 
                      USE THIS OPTION AT YOUR OWN RISK!!!
                      NOTE: There is no functionality to choose payment
                      option, so bot may still fail during checkout
                      
  --help              Show this message and exit.
```

#### Examples

Running FairGame with default functionality (Only currently supported option with alpha):
```shell
pipenv run python app.py amazon-aio
```

### Start Up

When you first launch FairGame, it will prompt you for your amazon credentials.  You will then be asked for a password 
to encrypt them. Once done, your encrypted credentials will be stored in `amazon_credentials.json`. 
If you ever forget your encryption password, just delete this file and the next launch of the bot will recreate it.
An example of this will look like the following:

```shell
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
INFO Initializing Apprise handler
INFO Initializing other notification handlers
INFO Enabled Handlers: ['Audio']
Reading credentials from: amazon_credentials.json
Credential file password: <enter the previously created password>
```


## Other Installation Help

### ASINs
See [#asins](https://discord.gg/DuVXAN5FnN) channel on our Discord server, or look them up on Amazon.

### Platform Specific

These instructions are supplied by community members and any adjustments, corrections, improvements or clarifications
are welcome. These are typically created during installation in a single environment, so there may be caveats or changes
necessary for your environment. This isn't intended to be a definitive guide, but a starting point as validation that a
platform can/does work. Please report back any suggestions to our [Discord](https://discord.gg/wgCYBx9URn) feedback
channel.

#### Installation MacOS 

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

Type `pipenv run python app.py amazon` and go through setup. You will also need to set up the config file, seen below in the Configuration section

#### Installation Ubuntu 20.10 (and probably other distros)

Based off Ubuntu 20.10 with a fresh installation.

Open terminal. Either right click desktop and go to Open In Terminal, or search for Terminal under Show Applications

Install Google Chrome:
`wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && sudo dpkg -i google-chrome-stable_current_amd64.deb`

Add Universe repo (this might be optional depending on your distro):
`sudo add-apt-repository universe && sudo apt update`

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

#### Installation Raspberry Pi 4 (2 GB+)

This is an abridged version of the community created document by UnidentifiedWarlock and Judarius (link to this
document can be found at end of this section, however you should **follow the README directions first!**). If the 
README steps don't work on your Pi 4, look at that document for additional options. This hasn't been tested
on a Pi 3, but given enough RAM to run Chrome, it may very well work. Let us know. 

```shell
sudo apt update
sudo apt upgrade
sudo apt-get install -y build-essential tk-dev libreadline-dev libdb5.3-dev libgdbm-dev libsqlite3-dev libssl-dev libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev libxslt1-dev rustc libjpeg-dev zlib1g-dev libfreetype6-dev liblcms1-dev libopenjp2-7 libtiff5 libncurses5-dev libncursesw5-dev chromium-chromedriver

version=3.8.8

wget https://www.python.org/ftp/python/$version/Python-$version.tgz

tar zxf Python-$version.tgz
cd Python-$version
./configure --enable-optimizations
make -j4
sudo make altinstall

cd ..

sudo python3.8 -m pip install --upgrade pip

git clone https://github.com/Hari-Nagarajan/fairgame
cd fairgame/
pip3 install pipenv
export PATH=$PATH:/home/$USER/.local/bin
pipenv shell 
pipenv install
cp /usr/bin/chromedriver /home/$USER/.local/share/virtualenvs/fairgame-<RANDOMCHARS>/lib/python3.8/site-packages/chromedriver_py/chromedriver_linux64
```

Leave this Terminal window open.

Open the following file in a text editor:

`/home/$USER/.local/share/virtualenvs/fairgame-<RANDOMCHARS>/lib/python3.8/site-packages/selenium/webdriver/common/service.py`

Edit line 38 from

`self.path = executable`

to

`self.path = "chromedriver"`

Then save and close the file.

Back in the terminal you kept open, under the fairgame folder you can now type `pipenv run python app.py amazon` and run the bot, or add any flags after you wish to use like `--headless` or `--delay x` to make `pipenv run python app.py amazon --headless --delay 4`

Basis for the above directions can be found [here](https://docs.google.com/document/d/1VUxXhATZ8sZOJxdh3AIY6OGqwLRmrAcPikKZAwphIE8/edit)

# Advanced Configuration 
## Notifications

### Sounds

Local sounds are provided as a means to give you audible cues to what is happening. The notification sound plays for
notable events (e.g., start up, product found for purchase) during the scans. An alarm notification will play when user
interaction is necessary. This is typically when all automated options have been exhausted. Lastly, a purchase
notification sound will play if the bot if successful. These local sounds can be disabled via the command-line
and [tested](#testing-notifications) along with other notification methods
#### Attribution
Notification sound from https://notificationsounds.com.

### Apprise

Notifications are now handled by Apprise. Apprise lets you send notifications to a large number of supported
notification services. Check https://github.com/caronc/apprise/wiki for a detailed list.

To enable Apprise notifications, make a copy of `apprise.conf_template` in the `config` directory and name it
`apprise.conf`. Then add apprise formatted urls for your desired notification services as simple text entries in the
config file. Any recognized notification services will be reported on app start.

#### Apprise Example Config:

```
# Hash Tags denote comment lines and blank lines are allowed
# Discord (https://github.com/caronc/apprise/wiki/Notify_discord)

https://discordapp.com/api/webhooks/{WebhookID}/{WebhookToken}

# Telegram
tgram://{bot_token}/{chat_id}/


# Slack (https://github.com/caronc/apprise/wiki/Notify_slack)
https://hooks.slack.com/services/{tokenA}/{tokenB}/{tokenC}

```

### Testing notifications

Once you have setup your `apprise_config.json ` you can test it by running `python app.py test-notifications` from
within your pipenv shell. This will send a test notification to all configured notification services.

## CLI Tools

### CDN Endpoints

The `find-endpoints` tool is designed to help you understand how many website domain endpoints exist for your geography
based on global Content Delivery Networks (CDNs) and your specific network provider. Its purpose is nothing more than to
educate you about variability of the network depending on how your computer resolves a domain. Doing something useful
with this knowledge is beyond the scope of this feature.

```shell
Usage: app.py find-endpoints [OPTIONS]

Options:
  --domain TEXT  Specify the domain you want to find endpoints for (e.g.
                 www.amazon.de, www.amazon.com, smile.amazon.com.

  --help         Show this message and exit.
```

Specifying a domain (e.g. www.amazon.com, www.amazon.es, www.google.com, etc.) will generate a list of IP addresses that
various public name servers resolve the name to. Hopefully this is helpful in understanding the variable nature of the
content that different people see.

### Routes

The `show_traceroutes` tool is simply a tool that attempts to generate the commands necessary to determine the various
paths that the Fairgame could take to get to a domain, based on who is resolving the domain to an IP.
It uses the [end points](#cdn-endpoints) tool to convert a domain name to the various IPs and generates a list of
commands you can copy and paste into the console to compare routes.

```shell
Usage: app.py show-traceroutes [OPTIONS]

Options:
  --domain TEXT  Specify the domain you want to generate traceroute commands for.

  --help         Show this message and exit.
```

This is intended for people who feel that they can modify their network situation such that the fastest route is used.
Explaining the Internet and how routing works is beyond the scope of this command, this tool, this project, and the
developers.

# Issues Running FairGame 
## Known Issues
* DO NOT change the zoom setting of the browser (it must be at 100%). Selenium doesn't work with the zoom at any other setting.
* 
* Pipenv does not like spaces in file paths, so you will either need to run from a place where you do not have spaces 
  in the file path, or set the option for pipenv to run locally in relation to the current file directory with:
```shell
set PIPENV_VENV_IN_PROJECT=1 (Windows) 
export PIPENV_VENV_IN_PROJECT=1 (Linux/Other)
```

* Running the bot's Chrome browser minimized can cause time out errors due to how Selenium acts with various versions of Chrome. 

* One time passcode (OTP) doesn't work in headless. Turn it off when starting up a headless instance, then turn 
  it back on afterwords.
  
* Avoid installing FairGame on OneDrive or similar cloud storage - some people have issues with this.

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

+ **Error: ```selenium.common.exceptions.SessionNotCreatedException: Message: session not created: 
  This version of ChromeDriver only supports Chrome version 90```**

  You are not running the proper version of Chrome this requires. As of this update, the current version is Chrome 90.
  Check your version by going to ```chrome://version/``` in your browser. We are going to be targeting the current stable
  build of chrome. If you are behind, please update, if you are on a beta or canary branch, you'll have to build your own
  version of chromedriver-py.

## Frequently Asked Questions

To keep up with questions, the Discord channel [#FAQ](https://discord.gg/GEsarYKMAw) is where you'll find the latest
answers. If you don't find it there, ask in #tech-support.

1. **Why didn't Fairgame buy this GPU that I can see in my browser?**
   
   If Fairgame didn't attempt to buy it, then Fairgame didn't ever see it as in stock. Many stock alert services are
   sending out affiliate URLs that appear to cache offers for some period of time, regardless of whether or not the item
   is still in-stock and purchaseable. Many people have reported that they can see an item as in stock in their browser
   but Fairgame either didn't see it, failed to check out, or logged some weird error condition.
   
   If you are trying to purchase an Nvidia 30-series or an AMD 6000-series GPU in 2021 then this may happen frequently for you.
   These items appear to sell out within fractions of a second and a large a mount of luck will be involved. Please do not
   create issues or ask for help when Fairgame "misses" a drop or tries to checkout but can't find the item in your cart.
   We know that it's hard to buy these things right now - that's why we're all here. Good luck!
   
1. **Can I run multiple instances of the bot?**
   
   It is possible, however we do not support running multiple instances nor any issues that may be encountered while doing so.
   
1. **Does Fairgame automatically bypass CAPTCHA's on the store sites?**
   
   The bot will try and auto-solve CAPTCHA's during the checkout process.
   
1. **Does `--headless` work?**
   
   Yes!  A community user identified the issue with the headless option while running on a Raspberry Pi. This allowed
   the developers to update the codebase to consistently work correctly on headless server environments. Give it a try
   and let us know if you have any issues.
   
1. **Does Fairgame run on a Raspberry Pi?**
   
   Yes, with caveats. Most people seem to have success with Raspberry Pi 4. The 2 GB model may need to run the headless
   option due to the smaller memory footprint. Still awaiting community feedback on running on a Pi 3. CPU and memory
   capacity seem to be the limiting factor for older Pi models. The Pi is also much slower then even a semi-recent
   (5 years or less) laptop. 
