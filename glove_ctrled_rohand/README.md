# Glove-Controlled ROHand

## Preparation

* Install Python and pip
* Open a command-line environment (e.g., Command Prompt on Windows or BASH on Linux)
* Navigate to the demonstration project directory, for example:

```SHELL
cd glove_ctrled_rohand
```

* Install the required Python libraries:

```SHELL
pip install -r requirements.txt
```

---

* Open the file `glove_ctrled_hand.py` and modify the device address as needed, for example:

```python
NODE_ID = 2
```

---

Choose the PosInput type according to the type of glove. ONLY ONE of the following should be uncommented :

* Using bluetooth version of glove:

```python
from pos_input_ble_glove import PosInputBleGlove as PosInput
```

* Using USB version of glove:

```python
from pos_input_usb_glove import PosInputUsbGlove as PosInput
```

## Run

```python
python glove_ctrled_hand.py
```

* Follow the on-screen instructions to perform the initial calibration, and then you can control the ROHand using the glove.
