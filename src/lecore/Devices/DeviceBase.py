"""
Common base of LE devices: configuration file declaration, path resolution and register access checks.
"""
from __future__ import annotations

import os
import sys
import warnings
from typing import Any, ClassVar, Dict, Optional, Tuple

from .Validation import PathLike, check_reg_name


class DeviceBase:
    """
    Base of generic devices. A concrete device is declared by class attributes, no constructor is needed::

        class MyDevice(ModbusDev):
            reg_map = "MyDevice_Modbus.json"   # required
            reg_names = MyDeviceRegs           # optional class with register name constants

    Configuration files are looked up in ``config_dir``, which defaults to the directory of the module where
    ``reg_map`` (or ``config_dir``) is declared.
    """
    #: Directory with configuration files (default: directory of the module declaring reg_map)
    config_dir: ClassVar[Optional[PathLike]] = None
    #: Register map JSON file name
    reg_map: ClassVar[Optional[PathLike]] = None
    #: Communication settings JSON file name
    com_settings: ClassVar[Optional[PathLike]] = "ComSettings.json"
    #: Class with string constants of register names, checked against the register map
    reg_names: ClassVar[Optional[type]] = None

    # Class attributes holding configuration file names, extended by subclasses
    _file_attrs: ClassVar[Tuple[str, ...]] = ('reg_map', 'com_settings')

    def __init_subclass__(cls, **kwargs):
        """
        Validate device declaration when the class is defined
        """
        super().__init_subclass__(**kwargs)
        own = cls.__dict__

        # Configuration directory
        if 'config_dir' in own and cls.config_dir is not None:
            if not isinstance(cls.config_dir, (str, os.PathLike)):
                raise TypeError(f"{cls.__name__}.config_dir must be str or PathLike, "
                                f"got {type(cls.config_dir).__name__}")
            cls.config_dir = os.path.abspath(cls.config_dir)
        elif 'reg_map' in own:
            module = sys.modules.get(cls.__module__)
            module_file = getattr(module, '__file__', None)
            if module_file is None:
                # Module executed without registration in sys.modules, use globals of the defining frame
                caller = sys._getframe(1).f_globals
                if caller.get('__name__') == cls.__module__:
                    module_file = caller.get('__file__')
            if module_file:
                cls.config_dir = os.path.dirname(os.path.abspath(module_file))
        if cls.config_dir is not None and not os.path.isdir(cls.config_dir):
            raise NotADirectoryError(f"{cls.__name__}.config_dir is not a directory: {cls.config_dir}")

        # Configuration files declared directly in this class must exist
        for attr in cls._file_attrs:
            if attr not in own or own[attr] is None:
                continue
            value = own[attr]
            if not isinstance(value, (str, os.PathLike)):
                raise TypeError(f"{cls.__name__}.{attr} must be str or PathLike, got {type(value).__name__}")
            if cls.config_dir is None:
                # Generic base classes resolve files at instance creation
                continue
            path = os.path.join(cls.config_dir, value)
            if not os.path.isfile(path):
                raise FileNotFoundError(f"{cls.__name__}.{attr} file not found: {path}")

        if 'reg_names' in own and own['reg_names'] is not None and not isinstance(own['reg_names'], type):
            raise TypeError(f"{cls.__name__}.reg_names must be a class with register name constants, "
                            f"got {type(own['reg_names']).__name__}")

    def _init_paths(self, config_dir: Optional[PathLike], reg_map: Optional[PathLike], custom_init: bool) -> bool:
        """
        Resolve configuration directory and decide between declarative and legacy initialization
        :param config_dir: Configuration directory override
        :param reg_map: Register map override
        :param custom_init: True if the device class defines its own constructor
        :return: True for declarative initialization, False for legacy subclass
        """
        if config_dir is not None:
            if not isinstance(config_dir, (str, os.PathLike)):
                raise TypeError(f"config_dir must be str or PathLike, got {type(config_dir).__name__}")
            if not os.path.isdir(config_dir):
                raise NotADirectoryError(f"config_dir is not a directory: {config_dir}")
            self._path = os.path.abspath(config_dir) + os.sep
        elif self.config_dir is not None:
            self._path = str(self.config_dir) + os.sep

        if reg_map is None and self.reg_map is None:
            if custom_init:
                # Legacy subclass sets _path/_def_regs and calls _com(), _reg_map() etc. itself
                warnings.warn(f"{type(self).__name__}: setting _path/_def_regs and calling _com()/_reg_map() "
                              f"in __init__ is deprecated, declare class attribute 'reg_map' instead",
                              DeprecationWarning, stacklevel=3)
                return False
            raise TypeError(f"{type(self).__name__} requires a register map: declare class attribute 'reg_map' "
                            f"or pass reg_map=...")
        if self.reg_map is not None:
            self._def_regs = self.reg_map
        return True

    def _path_complete(self, arg: Optional[PathLike], default: Optional[PathLike], what: str = "Configuration") -> str:
        """
        Resolve configuration file path.

        Default file names are relative to configuration directory. Explicitly passed paths are absolute or
        relative to current working directory, falling back to configuration directory.
        :param arg: Passed path override
        :param default: Default file name
        :param what: Description of the file used in error messages
        :return: Resolved path
        """
        if arg is None:
            if default is None:
                raise ValueError(f"{what} file is not defined")
            path = os.path.join(self._path, default) if self._path else str(default)
            candidates = [path]
        else:
            if not isinstance(arg, (str, os.PathLike)):
                raise TypeError(f"{what} file must be str or PathLike, got {type(arg).__name__} ({arg!r})")
            path = os.fspath(arg)
            candidates = [path]
            if self._path and not os.path.isabs(path):
                candidates.append(os.path.join(self._path, path))
        for p in candidates:
            if os.path.isfile(p):
                return p
        raise FileNotFoundError(f"{what} file not found: {' nor '.join(candidates)}")

    def _reg_dict(self) -> Dict[str, dict]:
        """
        Return all registers of loaded register map by name
        """
        raise NotImplementedError

    def _check_reg_names(self) -> None:
        """
        Check that all constants of reg_names class exist in the loaded register map
        """
        if self.reg_names is None:
            return
        consts = [v for k, v in vars(self.reg_names).items() if not k.startswith('_') and isinstance(v, str)]
        regs = self._reg_dict()
        missing = [c for c in consts if c not in regs]
        if missing:
            warnings.warn(f"{type(self).__name__}: register names of {self.reg_names.__name__} missing in register "
                          f"map {self._reg_file}: {', '.join(missing)}", UserWarning, stacklevel=3)

    def _get_reg(self, name: Any) -> dict:
        """
        Get register definition by name with a helpful error
        :param name: Register name
        :return: Register definition
        """
        regs = self._reg_dict()
        return regs[check_reg_name(name, regs.keys(), self._reg_file)]

    def register_names(self):
        """
        Return list of all register names in loaded register map
        """
        return list(self._reg_dict().keys())

    def close(self) -> None:
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def __repr__(self):
        return f"{type(self).__name__}(reg_map={self._reg_file!r})"
