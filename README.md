# README.md

Tool to help us buy a GPU in 2020

[Installation](#Installation) | [Usage](#Usage) 
## Installation

This project uses [Pipenv](https://pypi.org/project/pipenv/) to manage dependencies. 

```
pip install pipenv
pipenv shell 
pipenv install
```

Run it
```
python app.py
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

### Nvidia 
- Call Digitalriver API to get product number for the GPU selected (2060S, 3080, 3090)
- Call Digitalriver API to check if the GPU is in stock until it is in stock
- Will open a window in your default browser with the GPU in your cart when it is stock.

