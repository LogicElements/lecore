import os
import src.lecore.Devices.RtdEmul as RE

pth = os.path.dirname(os.path.abspath(__file__))


rtd = RE.RtdEmul()
# rtd = RE.RtdEmul(reg_map='RtdEmul_Modbus.json',
#                  upg='UpgradeSettings.json',
#                  com='ComSettings.json',
#                  visual='VisualSettings.json')
rtd.open(comport='COM34', slave=32)
# rtd.visual(None)
rtd.textual()
