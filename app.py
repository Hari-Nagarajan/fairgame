import json
from concurrent.futures import ThreadPoolExecutor

from guizero import App, PushButton, Box, TextBox, Text, Combo

from stores.amazon import Amazon
from stores.nvidia import GPU_DISPLAY_NAMES
from stores.nvidia import NvidiaBuyer
from utils.logger import log


class MainUI:
    def __init__(self):
        self.app = App(layout="grid", width=550, title="3080 Bot")
        self.amzn_input_data = self.load_amzn_options()

        self.amazon_executor = ThreadPoolExecutor(max_workers=3)
        self.nvidia_executor = ThreadPoolExecutor(max_workers=3)

        self.amazon_box = Box(self.app, grid=[0, 0], height="fill", width="550", layout="grid", align="left")
        self.amazon_status = Text(self.amazon_box, grid=[0, 1], align="left", bg="black", color="white", height="fill", text="")
        self.amazon_status.text_size = 10

        self.amazon_inputs_box = Box(self.amazon_box, grid=[0, 0], border=1, height="fill",  width="fill", layout="grid", align="left")

        self.start_button = PushButton(self.amazon_inputs_box, command=self.start_amzn, text="start", grid=[4, 0], align="right")
        self.stop_button = PushButton(self.amazon_inputs_box, command=self.stop_amzn, text="stop", enabled=False,
                                      grid=[4, 1], align="right")

        Text(self.amazon_inputs_box, text="Amazon Email", grid=[0, 0], align="left", )
        self.amazon_email = TextBox(self.amazon_inputs_box, align="left", grid=[1, 0], width=20, text=self.amzn_input_data['amazon_email'])

        Text(self.amazon_inputs_box, text="Amazon Password", grid=[0, 1], align="left")
        self.amazon_password = TextBox(
            self.amazon_inputs_box, align="left", grid=[1, 1], hide_text=True, width=20, text=self.amzn_input_data['amazon_password']
        )

        Text(self.amazon_inputs_box, text="Item URL", grid=[2, 0], align="left")
        self.amazon_item_url = TextBox(self.amazon_inputs_box, align="left", grid=[3, 0], text=self.amzn_input_data['amazon_item_url'],width=20)

        Text(self.amazon_inputs_box, text="Price Limit", grid=[2, 1], align="left")
        self.amazon_price_limit = TextBox(self.amazon_inputs_box, align="left", grid=[3, 1],  text=self.amzn_input_data['amazon_price_limit'], width=20)

        self.nvidia_box = Box(self.app, grid=[0, 1], border=1, height="fill", width=200, layout="grid", align="left")
        self.nvidia_inputs_box = Box(self.nvidia_box, grid=[0, 0], border=1, height="fill", width=200, layout="grid")
        self.start_button_nv = PushButton(self.nvidia_inputs_box, command=self.start_nv, text="start", grid=[1, 0])
        self.stop_button_nv = PushButton(self.nvidia_inputs_box, command=self.stop_nv, text="stop", enabled=False,
                                      grid=[2, 0])
        self.nv_status = Text(self.nvidia_box, grid=[0, 1], align="left", bg="black", color="white", height="fill", text="")
        self.nv_status.text_size = 10

        self.nv_gpu = Combo(self.nvidia_inputs_box, options=list(GPU_DISPLAY_NAMES.keys()), grid=[0,0])

    def save_amzn_options(self):
        data = {
            'amazon_email': self.amazon_email.value,
            'amazon_password': self.amazon_password.value,
            'amazon_item_url': self.amazon_item_url.value,
            'amazon_price_limit': self.amazon_price_limit.value
        }
        with open('amazon.json', 'w') as outfile:
            json.dump(data, outfile)

    def load_amzn_options(self):
        try:
            with open('amazon.json') as json_file:
                return json.load(json_file)
        except:
            return {
            'amazon_email': None,
            'amazon_password': None,
            'amazon_item_url': None,
            'amazon_price_limit': None
        }

    def amazon_run_item(self):
        amzn_obj = Amazon(username=self.amazon_email.value, password=self.amazon_password.value, debug=True)
        amzn_obj.run_item(item_url=self.amazon_item_url.value, price_limit=self.amazon_price_limit.value)

    def start_amzn(self):
        if self.amazon_email.value and self.amazon_password.value and self.amazon_price_limit.value and self.amazon_item_url.value:
            log.info("Starting amazon bot.")
            self.save_amzn_options()
            self.start_button.disable()
            self.stop_button.enable()
            self.amazon_status.value = "Running."
            self.amazon_executor.submit(self.amazon_run_item)

    def stop_amzn(self):
        self.amazon_executor.shutdown()
        self.amazon_status.value = "Stopped."
        self.start_button.enable()
        self.stop_button.disable()

    def nv_run(self):
        nv = NvidiaBuyer()
        nv.buy(self.nv_gpu.value)

    def start_nv(self):
        if self.nv_gpu.value:
            log.info("Starting NV bot.")
            self.nv_status.value = "Running."
            self.start_button_nv.disable()
            self.stop_button_nv.enable()
            self.amazon_executor.submit(self.nv_run)

    def stop_nv(self):
        self.nvidia_executor.shutdown()
        self.nv_status.value = "Stopped."
        self.start_button_nv.enable()
        self.stop_button_nv.disable()


if __name__ == "__main__":
    main_ui = MainUI()
    main_ui.app.display()
