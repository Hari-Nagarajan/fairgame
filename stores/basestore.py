import time


class BaseStoreHandler:
    def login(self):
        pass

    def parse_config(self):
        pass

    def run(self):
        pass

    def check_stock(self, item):
        pass

    @staticmethod
    def get_elapsed_time(start_time):
        return int(time.time()) - start_time
