import time
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Button, Header, Static, Input, Footer
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.screen import Screen
from textual.message import Message
from textual.widgets import DataTable

from MbClient import MbClient
from RegMap import RegMap
from VmSettings import *


class MyDataTable(DataTable):

    t_click = time.time()

    class Selected(Message):
        pass

    async def on_click(self, event):
        if time.time() - self.t_click < 0.3:
            self.post_message(self.Selected())
        self.t_click = time.time()
        await super()._on_click(event)

    def action_select_cursor(self):
        self.post_message(self.Selected())


class MyInput(Input):

    class Return(Message):
        pass

    async def on_key(self, event):
        self.log(event, event.key)
        if event.key == 'escape':
            self.post_message(self.Return())
        await super()._on_key(event)


class Settings(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Pop screen")]

    def compose(self) -> ComposeResult:
        for p in s.keys():
            with Horizontal(classes='column'):
                yield Static(p, id=f'set_{p}', classes='description')
                yield MyInput(value=str(s[p]), id=f"val_{p}", classes='descr_value')


class LogApp(App):
    CSS_PATH = "TextMbAppCss.tcss"
    TITLE = "Modbus state"
    SUB_TITLE = "Disconnected"
    SCREENS = {"settings": Settings()}

    BINDINGS = [
        Binding("c", "ftr_connect", "Connect"),
        Binding("d", "ftr_disconnect", "Disconnect"),
        Binding("a", "ftr_read_all", "Read All"),
        Binding("r", "ftr_read", "Read"),
        Binding("s", "push_screen('settings')", "Settings"),
        Binding("q", "ftr_quit", "Quit"),
    ]

    def __init__(self, visual='VisualSettings.json', upgrade='UpgradeSettings.json', com='ComSettings.json',
                 slave=None, reg_map=None, mb=None):
        super().__init__()
        if isinstance(mb, MbClient):
            self.mb = mb
        else:
            self.mb = MbClient()
        self._com_settings = com
        read_settings([com, visual, upgrade])
        self.slave = s['slave_address'] if slave is None else slave
        self.reg = RegMap(self.mb, slave=self.slave)
        self.reg.load(s['reg_map'] if reg_map is None else reg_map)
        self._reg_idx = 0
        self._table = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield MyDataTable()
        with Horizontal(classes='column'):
            yield Static(f"Register description", id='desc', classes='description')
            yield MyInput(value=f"Value", id='val_dec', classes='descr_value')
            yield MyInput(value=f"HEX", id='val_hex', classes='descr_value')
        yield Footer()

    def on_load(self):
        pass

    def on_mount(self):
        self.log(self.tree)
        self._table = self.query_one(DataTable)
        self._table.cursor_type = "row"
        self._table.zebra_stripes = True
        self._table.add_columns(*('Address', 'Type', 'Name', 'Value', 'Value HEX'))
        for reg in self.reg.input + self.reg.hold:
            self._table.add_row(f"{reg['Address']}", reg['Type'], reg['Name'], str(reg['Value']),
                                self.reg.val_to_hex(reg))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.exit(event.button.id)

    def on_data_table_row_highlighted(self, message):
        self._reg_idx = message.cursor_row
        reg_name = self._table.get_row_at(self._reg_idx)[2]
        self._update_bottom(reg_name)

    def on_my_data_table_selected(self, message):
        self.log(message)
        self.query_one("#val_dec").focus()

    def on_my_input_return(self):
        self._table.focus()

    @on(MyInput.Submitted, '#val_dec')
    def on_dec_submitted(self, message):
        in_dec = self.query_one("#val_dec")
        self._write_value(in_dec.value)

    @on(MyInput.Submitted, '#val_hex')
    def on_hex_submitted(self, message):
        in_hex = self.query_one("#val_hex")
        value = str(int(in_hex.value.replace("0x", ""), 16))
        self._write_value(value)

    def action_ftr_read(self):
        reg_name = self._table.get_row_at(self._reg_idx)[2]
        reg = self.reg.get_by_name(reg_name)
        self.reg.read_by_name(reg_name)
        self._update_reg_value(self._reg_idx, reg)

    def action_ftr_read_all(self):
        self.reg.read_in()
        self.reg.read_hold()
        i = 0
        for reg in self.reg.input + self.reg.hold:
            self._update_reg_value(i, reg)
            i += 1

    def action_ftr_quit(self):
        self.exit()

    def action_ftr_connect(self):
        self.mb.open(self._com_settings)
        self.sub_title = "Connected"
        self.log("Connected to ")

    def action_ftr_disconnect(self):
        self.mb.close()
        self.sub_title = "Disconnected"
        self.log("Disconnected from ")

    def _update_bottom(self, reg_name):
        st = self.query_one("#desc")
        in_dec = self.query_one("#val_dec")
        in_hex = self.query_one("#val_hex")
        reg = self.reg.get_by_name(reg_name)
        st.update(reg['Description'])
        in_dec.value = str(reg['Value'])
        in_hex.value = self.reg.val_to_hex(reg)

    def _write_value(self, value):
        reg_name = self._table.get_row_at(self._reg_idx)[2]
        reg = self.reg.get_by_name(reg_name)
        self.log('Write register', register=reg_name, value=value)
        self.reg.write_by_name(reg_name, value)
        self._update_reg_value(self._reg_idx, reg)

    def _update_reg_value(self, idx, reg):
        self._table.update_cell_at((idx, 3), reg['Value'], update_width=True)
        self._table.update_cell_at((idx, 4), self.reg.val_to_hex(reg), update_width=True)
        if idx == self._reg_idx:
            self._update_bottom(reg['Name'])




if __name__ == "__main__":
    LogApp(reg_map='../../../tests/RtdEmul_Modbus.json',
           upgrade='../../../tests/UpgradeSettings.json',
           com='../../../tests/ComSettings.json',
           visual='../../../tests/VisualSettings.json').run()
