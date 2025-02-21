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

## Running the Program

* Open the file `glove_ctrled_hand.py` and modify the port and device address as needed, for example:

```python
COM_PORT = "COM8"
NODE_ID = 2
```

* Run the program:

```python
python glove_ctrled_hand.py
```

* Follow the on-screen instructions to perform the initial calibration, and then you can control the ROHand using the glove.
