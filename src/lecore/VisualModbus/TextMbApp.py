from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Button, Header, Label, Static, Input
from textual.containers import Horizontal, Vertical


class LogApp(App):
    CSS_PATH = "TextMbAppCss.tcss"
    TITLE = "A Question App"
    SUB_TITLE = "The most important question"

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            for i in range(2):
                with Horizontal(classes='column'):
                    yield Static(f"Register {i}", classes='column')
                    yield Input(value=f"0fsafdfafafda", classes='column')
                    yield Static(f"End {i}", classes='column')
        yield Button("Exit", id="yes", variant="primary")

    @on(Input.Changed)
    def show_invalid_reasons(self, event: Input.Changed) -> None:
        print(f"new value")

    # def on_load(self):
    #     self.screen.styles.background = "darkblue"

    def on_mount(self):
        self.log(self.tree)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.exit(event.button.id)


if __name__ == "__main__":
    LogApp().run()
