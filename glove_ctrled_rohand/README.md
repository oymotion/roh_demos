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

## 运行

打开`glove_ctrled_hand.py`并修改端口和设备地址，例如：

```python
COM_PORT = "COM8"
NODE_ID = 2
```

运行：

```python
python glove_ctrled_hand.py
```

按'1'或者'2'切换大拇指位置，按'ctrl-c'退出。
