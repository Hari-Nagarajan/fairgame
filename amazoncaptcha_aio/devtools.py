# -*- coding: utf-8 -*-

"""
amazoncaptcha.devtools
~~~~~~~~~~~~~~~~~~~~~~

This module contains the set of amazoncaptcha's devtools.
"""

from .solver import AmazonCaptcha
from .exceptions import NotFolderError
from .__version__ import __version__

from io import BytesIO
import multiprocessing
import requests
import os

#--------------------------------------------------------------------------------------------------------------

class AmazonCaptchaCollector(object):

    def __init__(self, output_folder_path, keep_logs=True, accuracy_test=False):
        """
        Initializes the AmazonCaptchaCollector instance.

        Args:
            output_folder (str): Folder where images or logs should be stored.
            keep_logs (bool, optional): Is set to True, unsolved captcha links
                will be stored separately.
            accuracy_test (bool, optional): If set to True, AmazonCaptchaCollector
                will not download images, but just solve them and log the results.

        """

        self.output_folder = output_folder_path
        self.keep_logs = keep_logs
        self.accuracy_test = accuracy_test

        if not os.path.exists(self.output_folder):
            os.mkdir(self.output_folder)

        elif not os.path.isdir(self.output_folder):
            raise NotFolderError(self.output_folder)

        self.collector_logs = os.path.join(self.output_folder, f'collector-logs-{__version__.replace(".", "")}.log')
        self.test_results = os.path.join(self.output_folder, 'test-results.log')
        self.not_solved_logs = os.path.join(self.output_folder, 'not-solved-captcha.log')

    def _extract_captcha_link(self, captcha_page):
        """Extracts a captcha link from an html page.

        Args:
            captcha_page (str): A page's html in string format.

        Returns:
            str: Captcha link.

        """

        return captcha_page.text.split('<img src="')[1].split('">')[0]

    def _extract_captcha_id(self, captcha_link):
        """
        Extracts a captcha id from a captcha link.

        Args:
            captcha_link (str): A link to the captcha image.

        Returns:
            str: Captcha ID.

        """

        return ''.join(captcha_link.split('/captcha/')[1].replace('.jpg', '').split('/Captcha_'))

    def get_captcha_image(self):
        """
        Requests the page with Amazon's captcha, gets random captcha.
        Creates AmazonCaptcha instance, stores an original image before solving.

        If it is not an accuracy test, the image will be stored in a specified
        folder with the solution within its name. Otherwise, only the logs
        will be stored, mentioning the captcha link being processes and the result.

        """

        captcha_page = requests.get('https://www.amazon.com/errors/validateCaptcha')
        captcha_link = self._extract_captcha_link(captcha_page)

        response = requests.get(captcha_link)
        captcha = AmazonCaptcha(BytesIO(response.content))
        captcha._image_link = captcha_link
        original_image = captcha.img

        solution = captcha.solve(keep_logs=self.keep_logs, logs_path=self.not_solved_logs)
        log_message = f'{captcha.image_link}::{solution}'

        if solution != 'Not solved' and not self.accuracy_test:
            print(log_message)
            captcha_name = 'dl_' + self._extract_captcha_id(captcha.image_link) + '_' + solution + '.png'
            original_image.save(os.path.join(self.output_folder, captcha_name))

        else:
            print(log_message)
            with open(self.collector_logs, 'a', encoding='utf-8') as f:
                f.write(log_message + '\n')

    def _distribute_collecting(self, milestone):
        """Distribution function for multiprocessing."""

        for step in milestone:
            self.get_captcha_image()

    def start(self, target, processes):
        """
        Starts the process of collecting captchas of conducting a test.

        Args:
            target (int): Number of captchas to be processed.
            processes (int): Number of simultaneous processes.

        """

        goal = list(range(target))
        milestones = [goal[x: x + target // processes] for x in range(0, len(goal), target // processes)]

        jobs = list()
        for j in range(processes):
            p = multiprocessing.Process(target=self._distribute_collecting, args=(milestones[j], ))
            jobs.append(p)
            p.start()

        for proc in jobs:
            proc.join()

        if self.accuracy_test:
            with open(self.collector_logs, 'r', encoding='utf-8') as f:
                output = f.readlines()

            all_captchas = len(output)
            solved_captchas = len([i for i in output if 'Not solved' not in i])
            success_percentage = round((solved_captchas / all_captchas) * 100, 5)
            result = f'::Test::Ver{__version__}::Cap{all_captchas}::Per{success_percentage}::'

            with open(self.test_results, 'w', encoding='utf-8') as f:
                print(result)
                f.write(result)

#--------------------------------------------------------------------------------------------------------------
