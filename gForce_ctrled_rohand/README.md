# Controlling ROHand with gForce Armband

## Preparation

* Install Python and pip
* Open a command-line environment (e.g., Command Prompt on Windows or BASH on Linux)
* Navigate to the demonstration project directory, for example:

```SHELL
cd gForce_ctrled_rohand
```

* Install the required Python libraries:

```SHELL
pip install -r requirements.txt
```

## Running the Program

* Open the `gForce_ctrled_hand.py` file and modify the port and device address as needed, for example:

```python
COM_PORT = "COM7"
NODE_ID = 2
```

* Run the program:

```python
python gForce_ctrled_hand.py
```

* Press 'ctrl-c' to exit the program.