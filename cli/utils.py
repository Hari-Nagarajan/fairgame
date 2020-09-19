import click

from stores.nvidia import GPU_DISPLAY_NAMES, ACCEPTED_LOCALES


class GPU(click.ParamType):

    def convert(self, value, param, ctx):
        if value.upper() not in GPU_DISPLAY_NAMES.keys():
            self.fail(
                f"{value} is not a valid GPU, valid GPUs are {list(GPU_DISPLAY_NAMES.keys())}",
                param,
                ctx,
            )

        return value.upper()


class Locale(click.ParamType):

    def convert(self, value, param, ctx):
        if value.lower() not in ACCEPTED_LOCALES:
            self.fail(
                f"{value} is not a valid Locale, valid Locales are {ACCEPTED_LOCALES}",
                param,
                ctx,
            )

        return value.lower()
