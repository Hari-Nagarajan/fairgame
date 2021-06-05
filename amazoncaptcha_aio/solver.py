# -*- coding: utf-8 -*-

"""
amazoncaptcha.solver
~~~~~~~~~~~~~~~~~~~~

This module contains AmazonCaptcha instance and all the requiries for it.

Attributes:
    MONOWEIGHT (int): The bigger this number - the thicker a monochromed picture
    MAXIMUM_LETTER_LENGTH (int): Maximum letter length by X axis
    MINIMUM_LETTER_LENGTH (int): Minimum letter length by X axis
    SUPPORTED_CONTENT_TYPES (list of str): Used when requesting a captcha url
        to check if Content-Type in the headers is valid

"""

from .utils import cut_the_white, merge_horizontally, find_letter_boxes
from .exceptions import ContentTypeError
from aiohttp import ClientSession

from PIL import Image, ImageChops
from io import BytesIO
import warnings
import requests
import json
import zlib
import os

#--------------------------------------------------------------------------------------------------------------

MONOWEIGHT = 1
MAXIMUM_LETTER_LENGTH = 33
MINIMUM_LETTER_LENGTH = 14
SUPPORTED_CONTENT_TYPES = ['image/jpeg']

#--------------------------------------------------------------------------------------------------------------

class AmazonCaptcha(object):

    def __init__(self, img, image_link=None, devmode=False):
        """
        Initializes the AmazonCaptcha instance.

        Args:
            img (str or io.BytesIO): Path to an input image OR an instance
                of BytesIO representing this image.
            image_link (str, optional): Used if `AmazonCaptcha` was created
                using `from_webdriver` class method. Defaults to None.
            devmode (bool, optional): If set to True, instead of 'Not solved',
                unrecognised letters will be replaced with dashes.

        """

        self.img = Image.open(img, 'r')
        self._image_link = image_link
        self.devmode = devmode

        self.letters = dict()
        self.result = dict()

        package_directory_path = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
        self.training_data_folder = os.path.join(package_directory_path, 'training_data')
        self.alphabet = [filename.split('.')[0] for filename in os.listdir(self.training_data_folder)]

    @property
    def image_link(self):
        """
        Image link property is being assigned only if the instance was
        created using `fromdriver` or `fromlink` class methods.

        If you have created an AmazonCaptcha instance using the constructor,
        the property will be equal to None, which triggers the warning.

        """

        if not self._image_link:
            warnings.warn("Seems like you are trying to pull out the image link, while not having it.", Warning, stacklevel=2)

        return self._image_link

    def _monochrome(self):
        """
        Makes a captcha pure monochrome.

        Literally says: "for each pixel of an image turn codes 0, 1 to a 0,
        while everything in range from 2 to 255 should be replaced with 255".
        *All the numbers stay for color codes.
        """

        self.img = self.img.convert('L')
        self.img = Image.eval(self.img, lambda a: 0 if a <= MONOWEIGHT else 255)

    def _find_letters(self):
        """
        Extracts letters from an image using found letter boxes.

        Populates 'self.letters' with extracted letters being PIL.Image instances.
        """

        letter_boxes = find_letter_boxes(self.img, MAXIMUM_LETTER_LENGTH)
        letters = [self.img.crop((letter_box[0], 0, letter_box[1], self.img.height)) for letter_box in letter_boxes]

        if (len(letters) == 6 and letters[0].width < MINIMUM_LETTER_LENGTH) or (len(letters) != 6 and len(letters) != 7):
            letters = [Image.new('L', (200, 70)) for i in range(6)]

        if len(letters) == 7:
            letters[6] = merge_horizontally(letters[6], letters[0])
            del letters[0]

        letters = [cut_the_white(letter) for letter in letters]
        self.letters = {str(k): v for k, v in zip(range(1, 7), letters)}

    def _save_letters(self):
        """
        Transforms separated letters into pseudo binary.

        Populates 'self.letters' with pseudo binaries.
        """

        for place, letter in self.letters.items():
            letter_data = list(letter.getdata())
            letter_data_string = ''.join(['1' if pix == 0 else '0' for pix in letter_data])

            pseudo_binary = str(zlib.compress(letter_data_string.encode('utf-8')))
            self.letters[place] = pseudo_binary

    def _translate(self):
        """
        Finds patterns to extracted pseudo binary strings from data folder.

        Literally says: "for each pseudo binary scan every stored letter
        pattern and find a match".

        Returns:
            str: a solution if there is one OR 'Not solved' if devmode set to False

        """

        for place, pseudo_binary in self.letters.items():
            for letter in self.alphabet:

                with open(os.path.join(self.training_data_folder, letter + '.json'), 'r', encoding = 'utf-8') as js:
                    data = json.loads(js.read())

                if pseudo_binary in data:
                    self.result[place] = letter
                    break

            else:
                self.result[place] = '-'

                if not self.devmode:
                    return 'Not solved'

        return ''.join(self.result.values())

    def solve(self, keep_logs=False, logs_path='not-solved-captcha.log'):
        """
        Runs the sequence of solving a captcha.

        Args:
            keep_logs (bool): Not solved captchas will be logged if True.
                Defaults to False.
            logs_path (str): Path to the file, where not solved captcha
                links will be stored. Defaults to "not-solved-captcha.log".

        Returns:
            str: Result of the sequence.

        """

        self._monochrome()
        self._find_letters()
        self._save_letters()

        solution = self._translate()

        if solution == 'Not solved' and keep_logs and self.image_link:

            with open(logs_path, 'a', encoding='utf-8') as f:
                f.write(self.image_link + '\n')

        return solution

    @classmethod
    def fromdriver(cls, driver, devmode=False):
        """
        Takes a screenshot from your webdriver, crops the captcha, and stores
        it into bytes array, which is then used to create an AmazonCaptcha instance.

        This also means avoiding any local savings.

        Args:
            driver (selenium.webdriver.*): Webdriver with opened captcha page.
            devmode (bool, optional): If set to True, instead of 'Not solved',
                unrecognised letters will be replaced with dashes.

        Returns:
            AmazonCaptcha: Instance created based on webdriver.

        """

        png = driver.get_screenshot_as_png()
        element = driver.find_element_by_tag_name('img')
        image_link = element.get_attribute('src')

        location = element.location
        size = element.size
        left = location['x']
        top = location['y']
        right = location['x'] + size['width']
        bottom = location['y'] + size['height']

        img = Image.open(BytesIO(png))
        img = img.crop((left, top, right, bottom))

        bytes_array = BytesIO()
        img.save(bytes_array, format='PNG')
        image_bytes_array = BytesIO(bytes_array.getvalue())

        return cls(image_bytes_array, image_link, devmode)

    @classmethod
    def from_webdriver(cls, driver, devmode=False):
        warnings.warn("from_webdriver() is deprecated; use fromdriver() instead.", DeprecationWarning, stacklevel=2)
        return cls.fromdriver(driver, devmode)

    @classmethod
    async def fromlink(cls, image_link, devmode=False):
        """
        Requests the given link and stores the content of the response
        as `io.BytesIO`, which is then used to create AmazonCaptcha instance.

        This also means avoiding any local savings.

        Args:
            link (str): Link to Amazon's captcha image.
            devmode (bool, optional): If set to True, instead of 'Not solved',
                unrecognised letters will be replaced with dashes.

        Returns:
            AmazonCaptcha: Instance created based on the image link.

        Raises:
            ContentTypeError: If response headers contain unsupported
                content type.

        """

        s = ClientSession()
        async with s.get(image_link) as response:
            if response.headers['Content-Type'] not in SUPPORTED_CONTENT_TYPES:
                raise ContentTypeError(response.headers['Content-Type'])
            content = await response.content.read()

            image_bytes_array = BytesIO(content)

        return cls(image_bytes_array, image_link, devmode)

#--------------------------------------------------------------------------------------------------------------
