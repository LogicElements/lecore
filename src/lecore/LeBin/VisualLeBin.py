import time
from .RegisterMap import *
from .UpgradeFirmware import UpgradeFirmware
from .._version import __version__
try:
    import FreeSimpleGUI as SG
except ImportError:
    try:
        import PySimpleGUI as SG
    except ImportError:
        import datetime as SG


class VisualLeBin:
    """
    Visual application for LeBin protocol with serial communication
    """
    HEX_SUFFIX = "_H"
    READ_SUFFIX = "_READ_BTN"
    INF_SUFFIX = "_INFO_BTN"
    UPG_FILE = "T_UPG_FILE"

    def __init__(self, regs: RegisterMap):
        """
        Initialize application by passing instance of RegisterMap class which includes reference
        to communication interface
        :param regs: Register map object
        """
        self.regs = regs
        self.window = None
        self.info = None
        self.connected = 0

    def draw(self, height=800, width=600):
        """
        Create and draw the window application. Layout is defined hereafter
        :param height: Height of window
        :param width: Width of window
        :return: None
        """
        try:
            menu_def = [['&Settings', ['&Edit']],
                        ['&Help', '&About'], ]
            layout = [
                [SG.Menu(menu_def)],
            ]
            col1 = []
            for reg in self.regs.regs:
                line = [SG.Button("?", size=(2, 1), key=reg['Name'] + self.INF_SUFFIX, pad=(0, 0)),
                        SG.Button("R", size=(2, 1), key=reg['Name'] + self.READ_SUFFIX),
                        SG.Text(reg['Name'], size=(self.regs.max_len, 1), tooltip=reg['Label']),
                        SG.InputText('0', size=(20, 1), key=reg['Name']),
                        SG.InputText('0', size=(10, 1), key=reg['Name'] + self.HEX_SUFFIX)]
                if reg['Min'] != 0 or reg['Max'] != 0:
                    line.append(SG.Text(f"({reg['Min']}, {reg['Max']})"))
                col1.append(line)
            layout.append([SG.Column(col1, key='C_REGS', scrollable=True, vertical_scroll_only=True,
                                     size=(width, height), pad=(0, 0))])
            # layout.append()
            layout.append([SG.FileBrowse('Select file'), SG.Button('Upgrade', key='B_UPGRADE'),
                           SG.Input(key=self.UPG_FILE)])
            layout.append([SG.Submit('Write'), SG.Button('Write All'), SG.Button('Read'),
                           SG.Button('Connect', key='B_COMPORT'), SG.Cancel('Close'),
                           SG.Text("Period"), SG.Input('1000', size=(5, 1), key='T_PERIOD'),
                           SG.Text("RSSI"), SG.Input('-1', size=(4, 1), key='T_RSSI')])
            layout.append([SG.Text('Status', key='T_STATUS', size=(width // 8, None))])

            self.window = SG.Window('LeBin visual application. Version: ' + __version__, layout, resizable=True, finalize=True)
            self.update()
        except AttributeError:
            raise ImportError("FreeSimpleGUI is probably missing")

    def update(self):
        """
        Update register values inside application text box
        :return: None
        """
        for reg in self.regs.regs:
            self.window[reg['Name']].Update(reg['Value'])
            self.window[reg['Name'] + self.HEX_SUFFIX].Update(self.regs.val_to_hex(reg))

    def handle(self, timeout=None):
        """
        Window handle that runs for the whole time of application running
        :param timeout: Timeout of window appearance in seconds
        :return: None
        """
        to = 1000
        end_time = time.time()
        if timeout is not None:
            end_time += timeout
        while timeout is None or time.time() < end_time:
            # Read events and values from visual application
            event, values = self.window.Read(timeout=to, timeout_key='_TIMEOUT_')

            # Handle different events
            if event in (None, 'Close'):
                self.regs.com.close()
                break
            try:
                self._handle_event(event, values)
            except Exception as e:
                # Communication errors (e.g. not existing COM port) are reported, application keeps running
                self.window['T_STATUS'].Update(f'Error: {e}')

            to = max(min(int(values['T_PERIOD']), 10000), 500)
        self.window.close()
        return True

    def _handle_event(self, event, values):
        """
        Handle one window event
        :param event: Event from window
        :param values: Values from window
        :return: None
        """
        if 'Write' in event:
            self.regs.from_visual(values, self.HEX_SUFFIX)
            self.update()
        if 'Write All' in event:
            self.regs.write_all()
        if event in 'Read':
            self.regs.read_all()
            self.update()
        if event in 'B_COMPORT':
            self.connect_dis()
        if self.READ_SUFFIX in event:
            self.regs.read_by_name(event.replace(self.READ_SUFFIX, ""))
            self.update()
        if self.INF_SUFFIX in event:
            self.show_info(event.replace(self.INF_SUFFIX, ""))
        if event == 'B_UPGRADE' and values[self.UPG_FILE] != '':
            self.upgrade(values[self.UPG_FILE])
        if self.connected:
            self.window['T_RSSI'].Update(self.regs.com.get_rssi())

    def connect_dis(self):
        """
        Connect and disconnect button callback. It is separated just for clarity.
        :return: None
        """
        if self.connected == 0:
            # Ble or serial
            if self.regs.com.ble:
                dev = self.regs.com.scan(1, name="balb", scans=4)
                self.regs.com.connect(address=dev, interval=30, subscribe=True)
            elif not self.regs.com.reopen():
                self.window['T_STATUS'].Update(f'Cannot open COM port {self.regs.com.comport}')
                return
            self.window['T_STATUS'].Update('Connected')
            self.window['B_COMPORT'].Update('Disconn')
            self.connected = 1
        else:
            # Ble or serial
            if self.regs.com.ble:
                self.regs.com.disconnect()
            else:
                self.regs.com.close()
            self.window['B_COMPORT'].Update('Connect')
            self.connected = 0

    def upgrade(self, file_name):
        """
        Upgrade firmware from given binary file. Connects to the device if not connected yet. The device reboots
        afterwards, so the connection is closed and has to be opened again by the Connect button.
        :param file_name: Binary file to upgrade
        :return: True on successful upgrade
        """
        if not self.connected:
            self.connect_dis()
            if not self.connected:
                SG.popup(self.window['T_STATUS'].get(), title='Firmware upgrade')
                return False
        self.window['T_STATUS'].Update(f'Upgrading firmware from {file_name} ...')
        self.window.refresh()
        upg = UpgradeFirmware(self.regs.com)
        try:
            upg.load_file(file_name)
            ret = upg.run(lambda progress, size: SG.OneLineProgressMeter(
                'Upgrade progress bar', progress, size, 'KEY_PROGRESS'))
            if ret:
                msg = 'Upgrade finished, device is rebooting, reconnect'
            else:
                resp = bytes(upg.response or b'').hex(' ') or 'none'
                msg = f'Upgrade failed at offset {upg.offset} of {upg.length}, ' \
                      f'no or bad response from device: {resp}'
        except Exception as e:
            ret = False
            msg = f'Upgrade failed: {e}'
        SG.OneLineProgressMeterCancel('KEY_PROGRESS')
        # Device reboots after upgrade, close connection
        self.connect_dis()
        self.window['T_STATUS'].Update(msg)
        SG.popup(msg, title='Firmware upgrade')
        return ret

    def show_info(self, name):
        """
        Display information window about given register
        :param name:
        :return:
        """
        reg = next(x for x in self.regs.regs if x['Name'] == name)
        lay = [[SG.Text(json.dumps(reg, indent=4))]]
        if self.info is not None:
            self.info.close()
        self.info = SG.Window('Register information', lay, resizable=True, auto_size_text=True, finalize=True)

