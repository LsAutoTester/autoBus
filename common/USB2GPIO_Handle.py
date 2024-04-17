"""
文件说明：USB2XXX GPIO操作相关函数集合
更多帮助：www.usbxyz.com
"""
import sys
import time
from ctypes import *
import platform
# Error code define
# from usb_device import *
from common.usb_device import *

GPIO_SUCCESS = 0  # success
GPIO_ERR_NOT_SUPPORT = -1  # USB2XXX not support
GPIO_ERR_USB_WRITE_FAIL = -2  # USB write data error
GPIO_ERR_USB_READ_FAIL = -3  # USB read data error
GPIO_ERR_CMD_FAIL = -4  # execute function error
pinNumMap = {
    0: 0x0001, 1: 0x0002, 2: 0x0004, 3: 0x0008,
    4: 0x0010, 5: 0x0020, 6: 0x0040, 7: 0x0080,
    8: 0x0100, 9: 0x0200, 10: 0x0400, 11: 0x0800,
    12: 0x1000, 13: 0x2000, 14: 0x4000, 15: 0x8000
}


# 将GPIO设置为输入模式
def GPIO_SetInput(DevHandle, PinMask, PuPd):
    return USB2XXXLib.GPIO_SetInput(DevHandle, PinMask, PuPd)


# 将GPIO设置为输出模式
def GPIO_SetOutput(DevHandle, PinMask, PuPd):
    return USB2XXXLib.GPIO_SetOutput(DevHandle, PinMask, PuPd)


# 将GPIO设置为开漏模式（可做双向引脚）
def GPIO_SetOpenDrain(DevHandle, PinMask, PuPd):
    return USB2XXXLib.GPIO_SetOpenDrain(DevHandle, PinMask, PuPd)


# 控制GPIO输出高电平或者低电平
def GPIO_Write(DevHandle, PinMask, PinValue):
    return USB2XXXLib.GPIO_Write(DevHandle, PinMask, PinValue)


# 读取GPIO引脚状态
def GPIO_Read(DevHandle, PinMask, pPinValue):
    return USB2XXXLib.GPIO_Read(DevHandle, PinMask, pPinValue)


def split_list(lst, step):
    return [lst[i:i + step] for i in range(0, len(lst), step)]


def binList2Hex(binList):
    hexStr = "0x"
    for bitList in binList:
        binStr = ''.join(str(num) for num in bitList)
        decimal_num = int(binStr, 2)
        hexStr += hex(decimal_num)[2:]
    return hexStr
    decimal_num = int(hexStr, 16)
    hexStr = hex(decimal_num)
    return hexStr


# 将引脚序号转化为16进制，便于usb2xxx识别
def pinNum2PinMask(pinNum):
    pinMaskList = [0] * 16
    pinMaskList[pinNum] = 1
    # print(pinMaskList[::-1])
    PinMask = binList2Hex(split_list(pinMaskList[::-1], 4))
    return pinNumMap[pinNum]
    # return PinMask


# 设置 P0-P7的初始电平状态，默认为低电平
def setP0_7Level(DevFp, initStatus=0):
    if initStatus:
        GPIO_Write(DevFp, 0x00FF, 0x00FF)
    else:
        GPIO_Write(DevFp, 0x00FF, 0x0000)


# 设置 P8-P156的初始电平状态，默认为高电平3.3v
def setP8_15Level(DevFp, initStatus=1):
    if initStatus:
        GPIO_Write(DevFp, 0xFF00, 0xFF00)
    else:
        GPIO_Write(DevFp, 0x00FF, 0x0000)


# 设置指定引脚为低电平P0-P7为高电平，P8-P15为低电平
def setP0_7LP8_15H(DevFp):
    GPIO_Write(DevFp, 0xFFFF, 0xFF00)


# 设置指定引脚为低电平P0-P7为高电平，P8-P15为低电平
def setP0_7HP8_15L(DevFp):
    GPIO_Write(DevFp, 0xFFFF, 0x00FF)


# 设置单个的引脚电平，默认为低
def setPinLevel(DevFp, pinNum, level=0):
    PinMask = pinNum2PinMask(pinNum)
    checkValueBefore = checkPinMaskLevel(DevFp, pinNum)
    print(f"开始设置P{pinNum} {PinMask}的值为: {level}")

    if level:
        GPIO_SetOutput(DevFp, PinMask, 1)
        GPIO_Write(DevFp, PinMask, PinMask)
    else:
        GPIO_SetOutput(DevFp, PinMask, 2)
        GPIO_Write(DevFp, PinMask, 0x0000)
    checkValueAfter = checkPinMaskLevel(DevFp, pinNum)
    if checkValueBefore == checkValueAfter:
        print("引脚电平重复设置")
        return False
    else:
        print("引脚电平设置成功")
        return True


def checkPinMaskLevel(DevFp, pinNum):
    PinValue = c_uint(0)
    PinMask = pinNum2PinMask(pinNum)
    # 设置引脚为输入模式，可读其状态
    GPIO_Read(DevFp, PinMask, byref(PinValue))
    value = "%04X" % PinValue.value
    return value


def showCurrentDev():
    DevHandles = (c_int * 20)()
    devNums = USB_ScanDevice(byref(DevHandles))
    for num in range(0, devNums):
        currentDevNum = DevHandles[num]
        print(f"当前设备号：{currentDevNum}")


def decimal_to_four_hex(decimal_number):
    hex_string = hex(decimal_number)[2:]  # 去掉0x前缀
    return "0x" + hex_string.zfill(4)  # 如果不足4位，用0填充


def closeDev(DevFp):
    ret = USB_CloseDevice(DevFp)
    if ret:
        print("Close device success!")
        return True
    else:
        print("Close device faild!")
        return False


class usb2xxGpioHandle:
    def __init__(self, deviceNum, output):
        self.deviceNum = deviceNum
        self.output = output
        self.resetRetry = 10

    def dvOpen(self):
        # # wb01 的ser 脚。默认低电平，拉高进烧录
        # wb01SelPinNum = 0
        # # csk 的boot脚。默认高电平，拉低进烧录
        # cskBootPinNum = 8

        ret = USB_OpenDevice(self.deviceNum)
        if not ret:
            self.output.LOG_ERROR(f"usb2xxx {self.deviceNum} 设备打开失败，请检查 ")
            return False
        # 设置P0-P15引脚为输出模式，可以通过调用GPIO_Write函数将指定引脚设置为高电平或者低电平。
        GPIO_SetOutput(self.deviceNum, 0xFFFF, 0)
        # 设置指定引脚为低电平P0-P7为低电平，P8-P15为高电平
        setP0_7LP8_15H(self.deviceNum)
        self.resetRetry = 3
        return True

    def pinValueCheck(self, pinNum):
        self.setInput(pinNum)
        time.sleep(0.1)
        serPinValue = checkPinMaskLevel(self.deviceNum, pinNum)
        self.output.LOG_INFO(f"引脚P{pinNum}，当前值为：{serPinValue}")
        return serPinValue

    def setInput(self, pinNum):
        PinMask = pinNum2PinMask(pinNum)
        ret = GPIO_SetInput(self.deviceNum, PinMask, 0x00)
        if ret != 0:
            self.output.LOG_ERROR(f"P{pinNum}引脚设置输入模式失败, error: {ret}")
            return False
        return True

    def setOutput(self, pinNum, PuPd):
        PinMask = pinNum2PinMask(pinNum)
        ret = GPIO_SetOutput(self.deviceNum, PinMask, PuPd)
        if ret != 0:
            self.output.LOG_ERROR(f"P{pinNum}引脚设置输入模式失败, error: {ret}")
            return False
        return True

    def setPinMaskPuPd(self, pinNum, PuPd):
        PinMask = pinNum2PinMask(pinNum)
        checkValueBefore = checkPinMaskLevel(self.deviceNum, pinNum)

        self.output.LOG_INFO(f"检查P{pinNum}引脚初始值为：{checkValueBefore}")

        if PuPd:
            self.output.LOG_INFO(f"开始拉高 P{pinNum}引脚")
            GPIO_SetOutput(self.deviceNum, PinMask, 1)
            time.sleep(0.1)
            GPIO_Write(self.deviceNum, PinMask, PinMask)
        else:
            self.output.LOG_INFO(f"开始拉低 P{pinNum}引脚")
            GPIO_SetOutput(self.deviceNum, PinMask, 2)
            time.sleep(0.1)
            GPIO_Write(self.deviceNum, PinMask, 0x0000)
        checkValueAfter = checkPinMaskLevel(self.deviceNum, pinNum)
        self.output.LOG_INFO(f"检查P{pinNum}引脚初始值为：{checkValueAfter}")
        if checkValueBefore == checkValueAfter:
            self.output.LOG_ERROR(f"\t\t**********P{pinNum} 脚控制失败**********")
            return False
        else:
            self.output.LOG_ERROR(f"\t\t**********P{pinNum} 脚控制成功**********")
            return True
        #
        #
        #
        #
        #
        # PinMask = pinNum2PinMask(pinNum)
        # print(PinMask)
        # pValueBefore = self.pinValueCheck(pinNum)
        # if PuPd:
        #     GPIO_SetOutput(self.deviceNum, PinMask, 1)
        #     time.sleep(0.1)
        #     self.output.LOG_INFO(f"开始拉高 P{pinNum}引脚")
        #     GPIO_Write(self.deviceNum, PinMask, PinMask)
        #     time.sleep(0.2)
        #     pValueAfter = self.pinValueCheck(pinNum)
        # else:
        #     GPIO_SetOutput(self.deviceNum, PinMask, 2)
        #     time.sleep(0.1)
        #     self.output.LOG_INFO(f"开始拉低 P{pinNum}引脚")
        #     GPIO_Write(self.deviceNum, PinMask, 0x00)
        #     time.sleep(0.2)
        #     pValueAfter = self.pinValueCheck(pinNum)
        # if pValueBefore != pValueAfter:
        #     self.output.LOG_ERROR(f"\t\t**********P{pinNum} 脚控制成功**********")
        #     return True
        # self.output.LOG_ERROR(f"\t\t**********P{pinNum} 脚控制失败**********")
        # return False

    def usb2xxReset(self):
        GPIO_SetOutput(self.deviceNum, 0xFFFF, 0)
        self.resetRetry -= 1
        self.output.LOG_INFO(f"重新复位usb2xxx gpio 引脚值，P0-P7为低电平，P8-P15为高电平，retryTimes 还剩:{self.resetRetry}")
        setP0_7LP8_15H(self.deviceNum)

    def usb2xxResetBoot(self):
        GPIO_SetOutput(self.deviceNum, 0xFFFF, 0)
        self.resetRetry -= 1
        self.output.LOG_INFO(f"重新复位usb2xxx gpio 引脚值，P0-P7为高电平，P8-P15为低电平，retryTimes 还剩:{self.resetRetry}")
        setP0_7HP8_15L(self.deviceNum)

    def dvClose(self):
        GPIO_SetOutput(self.deviceNum, 0xFFFF, 0)
        setP0_7LP8_15H(self.deviceNum)
        self.output.LOG_INFO(f"关闭usb2xxx")
        closeDev(self.usb2xxxDevNum)


if __name__ == '__main__':
    showCurrentDev()
    sys.exit()
    # 设备号
    devNum = 553650634
    # wb01 的ser 脚。默认低电平，拉高进烧录
    wb01SelPinNum = 0
    # csk 的boot脚。默认高电平，拉低进烧录
    cskBootPinNum = 8
    ret = USB_OpenDevice(devNum)
    if not ret:
        print(f"设备{devNum}打开失败")
    # 设置P0-P15引脚为输出模式，可以通过调用GPIO_Write函数将指定引脚设置为高电平或者低电平。
    GPIO_SetOutput(devNum, 0xFFFF, 0)
    # 设置指定引脚为低电平P0-P7为低电平，P8-P15为高电平
    setP0_7LP8_15H(devNum)
    time.sleep(1)
    # 设置boot和ser进入烧录模式
    setPinLevel(devNum, cskBootPinNum, 0)
    time.sleep(0.1)
    setPinLevel(devNum, wb01SelPinNum, 1)

    # TODO
    # 烧录文件中
    input()
    # 烧录完成后恢复正常引脚
    setPinLevel(devNum, cskBootPinNum, 1)
    time.sleep(0.1)
    setPinLevel(devNum, wb01SelPinNum, 0)

    # setP0_7LP8_15H(devNum)
    closeDev(devNum)
    sys.exit()
