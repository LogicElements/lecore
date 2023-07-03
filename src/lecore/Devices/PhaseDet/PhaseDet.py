from ..ModbusDev import *


class PhaseDet(ModbusDev):

    def __init__(self, com=None, reg_map=None, upg=None, visual=None):
        """
        Phase detector modbus slave device

        The respective parameters allow to redefine default settings. In most cases, it is not necessary.
        :param com: Communication settings file override
        :param reg_map: Register map definition file override
        :param upg: Upgrade settings file override
        :param visual: Visual settings file override
        """
        super().__init__()
        # Get path to Emulator directory
        self._path = os.path.dirname(os.path.abspath(__file__)) + "/"
        print(f"PATH RTD = {self._path}")
        # Set default register map
        self._def_regs = "PhaseDet_Modbus.json"

        # Initialize all internal structures
        self._com(com)
        self._reg_map(reg_map)
        self._upgrade(upg)
        self._visual(visual)


