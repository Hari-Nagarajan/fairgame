import click
import questionary


class QuestionaryOption(click.Option):
    def __init__(self, param_decls=None, **attrs):
        click.Option.__init__(self, param_decls, **attrs)

    def prompt_for_value(self, ctx):
        return questionary.select(self.prompt, choices=self.type.choices).unsafe_ask()
