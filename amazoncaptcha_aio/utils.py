# -*- coding: utf-8 -*-

"""
amazoncaptcha.utils
~~~~~~~~~~~~~~~~~~~

This module contains the set of amazoncaptcha's utilities.
"""

from PIL import Image, ImageChops

#--------------------------------------------------------------------------------------------------------------

def cut_the_white(letter):
    """
    Cuts white spaces/borders to get a clear letter.

    We do not trim the whole image at the beginning, because all the letters
    have different position by Y, which means that cutting white won't do
    any good, until letters are separated by X.

    Args:
        letter (PIL.Image): Letter to be processed.

    Returns:
        PIL.Image: The letter without white spaces.

    """

    background = Image.new(letter.mode, letter.size, 255)
    diff = ImageChops.difference(letter, background)
    bbox = diff.getbbox()

    return letter.crop(bbox)

def merge_horizontally(img1, img2):
    """
    Merges two letters horizontally.

    Created in case an image is corrupted and the last letter ends at the
    beginning of the image, causing letter to be unreadable.

    Args:
        img1 (PIL.Image): First letter.
        img2 (PIL.Image): Second letter.

    Returns:
        PIL.Image: Two merged letters.

    """

    merged = Image.new('L', (img1.width + img2.width, img1.height))
    merged.paste(img1, (0, 0))
    merged.paste(img2, (img1.width, 0))

    return merged

def find_letter_boxes(img, maxlength):
    """
    Finds and separates letters from a captcha image.

    Args:
        img (PIL.Image): Monochromed captcha.
        maxlength (int): Maximum letter length by X axis.

    Returns:
        letter_boxes (:obj:`list` of :obj:`tuple`): List with X coords of each letter.

    """

    image_columns = [[img.getpixel((x, y)) for y in range(img.height)] for x in range(img.width)]
    image_code = [1 if 0 in column else 0 for column in image_columns]
    xpoints = [d for d, s in zip(range(len(image_code)), image_code) if s]
    xcoords = [x for x in xpoints if x - 1 not in xpoints or x + 1 not in xpoints]

    if len(xcoords) % 2:
        xcoords.insert(1, xcoords[0])

    letter_boxes = list()
    for s, e in zip(xcoords[0::2], xcoords[1::2]):
        start, end = s, min(e + 1, img.width - 1)

        if end - start <= maxlength:
            letter_boxes.append((start, end))

        else:
            two_letters = {k: v.count(0) for k, v in enumerate(image_columns[start + 5:end - 5])}
            divider = min(two_letters, key=two_letters.get) + 5
            letter_boxes.extend([(start, start + divider), (start + divider + 1, end)])

    return letter_boxes

#--------------------------------------------------------------------------------------------------------------
