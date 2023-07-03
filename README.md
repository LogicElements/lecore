# LE core package

This is package of core python utils for LE containing:
- Looger
- Proprietary LeBin protocol
- Proprietary Modbus RTU register map handling - VisualModbus
- Test frame
- Logic Elements devices

## Install

Install or update version
```
pip install lecore
pip install --upgrade lecore
```


# LE devices - Modbus RTU slave

The following Modbus RTU devices are supported:

## RTD Emulator

4-channel RTD emulator, see https://logicelements.cz/en/products/rtd-emulator.

Example of usage:
```python
import lecore.Devices.RtdEmul as RE

# Create RTD emulator object
rtd = RE.RtdEmul()

# Open communication at COM2 (default is COM1) with default COM parameters
rtd.open(comport='COM2')

# Read serial number
sn = rtd.read(RE.Reg.FACT_SERIAL_NUMBER)

# Write stock resistance and beta
rtd.write(RE.Reg.EMUL_NTC_STOCK_RES, 10000)
rtd.write(RE.Reg.EMUL_NTC_BETA, 3977)

# Write emulated temperature at output 1
rtd.write(RE.Reg.EMUL_TEMPERATURE_1, 30.5)
```


## VMS-1502 RTD Meter

6-channel RTD meter, see https://logicelements.cz/en/products/rtd-meter.

Example of usage:


```python
import lecore.Devices.VmsRtd as RTD

# Create RTD meter object
rtd = RTD.VmsRtd()

# Open communication at COM2 (default is COM1) with default COM parameters
rtd.open(comport='COM2')

# Read fixed-point temperature at input 1 (fix-point is multiplied by 100)
temp_fp = rtd.read(RTD.Reg.RTD_TEMPER_1) / 100

# Read floating-point temperature at input 1
temp_float = rtd.read(RTD.Reg.RTDE_TEMPER_FLOAT_1)

# Write RTD type to PT1000 for input 1
rtd.write(RTD.Reg.RTD_TYPE_1, 1)
```


## Phase Detector

6-channel Power Grid Voltage Detector, see https://logicelements.cz/en/products/power-grid-voltage-detector.

Example of usage:

```python
import lecore.Devices.PhaseDet as PE

# Create Phase Detector object
pe = PE.PhaseDet()

# Open communication at COM2 (default is COM1) with default COM parameters
pe.open(comport='COM2')

# Read Pulse count on phase input L1
count = pe.read(PE.Reg.PH_COUNTER_1)

# Clear counts on all phase inputs
pe.write(PE.Reg.PH_CLEAR_ALL, 1)
```


# Third-party devices

## FG-320

Function generator, see https://www.profess.cz/en/mms/products/accessories/service-instruments/fg320

Example of usage:

```python
import lecore.Fg320 as FG

# Create FG-320 object
fg = FG.Fg320('COM6')

# Print FG-320 parameters (serial number, firmware version, etc.)
fg.identify()

# Generate analog signal with key phase mark 
fg.normal(function="SQ", frequency=10, amplitude=1, dc=0, angle=90, kp_high=11, kp_low=1)
fg.write()

# Generate current loop signal
fg.current_dc(dc=5)
fg.write()

# Generate speed signal
fg.speed(frequency=10)
fg.write()
```

# Looger

Class Looger allows for sending debug data into Development Debug Server (DDS) a.k.a. 
Looger. Public instance run at https://looger.jablotron.cz

Create instance when default public endpoint is to be used 

```python
import lecore

# Create Looger object
looger = lecore.Looger()

# Set device properties
looger.set_device(0x111CC1234, 0, None)

# Send data collection and text message
data = {'data_1': 1, 'data_2': 2}
log = f"Message to log"
looger.send(data, log, 0)

# Send just log message
looger.send_log(log)
```





