import click

from stores.nvidia import GPU_DISPLAY_NAMES


class GPU(click.ParamType):
    name = "api-key"

    def convert(self, value, param, ctx):
        if value.upper() not in GPU_DISPLAY_NAMES.keys():
            self.fail(
                f"{value} is not a valid GPU, valid GPUs are {list(GPU_DISPLAY_NAMES.keys())}",
                param,
                ctx,
            )

        return value.upper()
