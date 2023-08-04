import time
from .RegisterMap import *
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
            layout.append([SG.Submit('Write'), SG.Button('Write All'), SG.Button('Read'),
                           SG.Button('Connect', key='B_COMPORT'), SG.Cancel('Close'),
                           SG.Text("Period"), SG.Input('1000', size=(5, 1), key='T_PERIOD'),
                           SG.Text("RSSI"), SG.Input('-1', size=(4, 1), key='T_RSSI')])
            layout.append([SG.Text('Status', key='T_STATUS', size=(width // 8, None))])

            self.window = SG.Window('LeBin visual application. Version: 1.1', layout, resizable=True, finalize=True)
            self.update()
        except AttributeError:
            raise ImportError("PySimpleGUI is probably missing")

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
            if self.connected:
                self.window['T_RSSI'].Update(self.regs.com.get_rssi())

            to = max(min(int(values['T_PERIOD']), 10000), 500)
        self.window.close()
        return True

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
            else:
                self.regs.com.reopen()
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

