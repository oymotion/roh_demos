# 手套控制 ROHand

## 准备

安装python和pip
进入命令环境，如windows下的command或者linux下的BASH
进入演示项目目录，例如：

```SHELL
cd glove_ctrled_rohand
```

安装依赖的python库：

```SHELL
pip install -r requirements.txt
```

## 使用蓝牙版手套

打开`glove_ctrled_hand.py`并修改设备地址，例如：

```python
NODE_ID = 2
```

运行：

```python
python glove_ctrled_hand.py
```

按照指示进行初始标定后，即可通过蓝牙手套控制灵巧手。

## 使用USB版手套

打开`usb_glove_ctrled_hand.py`并修改设备地址，例如：

```python
NODE_ID = 2
```

运行：

```python
python usb_glove_ctrled_hand.py
```

按照指示进行初始标定后，即可通过usb版手套控制灵巧手。
