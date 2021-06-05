# -*- coding: utf-8 -*-

"""Solver for Amazon's image captcha.

The motivation behind the creation of this library is taking its start from
the genuinely simple idea: "I don't want to use pytesseract or some other
non-amazon-specific OCR services, nor do I want to install some executables to
just solve a captcha. I desire to get a solution within 1-2 lines of code
without any heavy add-ons. Using a pure Python."

Examples:
    Browsing Amazon using selenium and stuck on captcha? The class method
    below will do all the "dirty" work of extracting an image from the webpage
    for you. Practically, it takes a screenshot from your webdriver, crops the
    captcha, and stores it into bytes array, which is then used to create an
    AmazonCaptcha instance. This also means avoiding any local savings.

        from amazoncaptcha import AmazonCaptcha
        from selenium import webdriver

        driver = webdriver.Chrome() # This is a simplified example
        driver.get('https://www.amazon.com/errors/validateCaptcha')

        captcha = AmazonCaptcha.fromdriver(driver)
        solution = captcha.solve()


    If you are not using selenium or the previous method is not just the case for
    you, it is possible to use a captcha link directly. This class method will
    request the url, check the content type and store the response content into bytes
    array to create an instance of AmazonCaptcha.

        from amazoncaptcha import AmazonCaptcha

        link = 'https://images-na.ssl-images-amazon.com/captcha/usvmgloq/Captcha_kwrrnqwkph.jpg'

        captcha = AmazonCaptcha.fromlink(link)
        solution = captcha.solve()

"""

from .solver import AmazonCaptcha
from .devtools import AmazonCaptchaCollector
from .exceptions import ContentTypeError, NotFolderError

#--------------------------------------------------------------------------------------------------------------
