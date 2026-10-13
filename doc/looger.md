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
