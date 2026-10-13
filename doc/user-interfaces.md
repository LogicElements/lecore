# User interfaces

Every Modbus device class (`RtdEmul`, `VmsRtd`, `PhaseDet`, `Rftb`) can open an interactive register browser.
Both interfaces are optional and need extra packages.

## Graphical (FreeSimpleGUI)

```
pip install lecore[extra]
```

```python
import lecore.Devices.RtdEmul as RE

rtd = RE.RtdEmul()
rtd.open(comport='COM2')

# Run the graphical application, close it automatically after 60 seconds (None = no timeout)
rtd.visual(60)
```

`FreeSimpleGUI` is used when installed, `PySimpleGUI` 4.x is only a fallback. PySimpleGUI 4.x does not work on
Python 3.14 (Tcl/Tk 9).

## Textual (terminal)

```
pip install lecore[tui]
```

```python
rtd.textual()
```

## Word documentation of a register map

`lecore.Doc.ModbusTable` generates a table of registers into a Word document and requires `python-docx`
(installed with `lecore[extra]`).
