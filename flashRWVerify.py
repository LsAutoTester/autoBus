# -*- coding: utf-8 -*-
__author__ = "bszheng"
__date__ = "2024/5/21"
__version__ = "1.0"

import argparse
import datetime
import os.path
import subprocess
import time

import common.pdusnmp as pdu
import hashlib

from Common_Func import createdirs
from common.USB2GPIO_Handle import *
from common.output_log import output_log
from common.usb_device import *

pdu.initEngine()
pdu_device_ip = '10.3.37.30'
usb2xxxNum = 553650600
sys.stdout.flush()
UART_NUM = 13
BOOT_ADDR = 0x000000
CSK_AP_ADDR = 0x45000
CSK_CP_ADDR = 0x200000
TONE_ADDR = 0x680000
TONE_ADDR_2 = 0x800000
CSK_EMPTY_ADDR = 0x40000
BAUD_RATE = 1500000


# 随机生成16进制字符的二进制文件
def generate_random_binary_file(file_path, size_in_bytes):
    """
    file_path:文件保存地址
    size_in_bytes:文件大小如1K: 1024、1M: 1024*1024、16M: 1024*1024*16
    """
    with open(file_path, 'wb') as file:
        file.write(os.urandom(size_in_bytes))


def calculate_md5(file_path):
    """
    计算给定文件路径的MD5哈希值
    :param file_path: 文件路径
    :return: 文件的MD5哈希值（十六进制字符串）
    """
    # 创建一个md5 hash对象
    hash_object = hashlib.md5()

    # 确保文件存在
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"No such file or directory: '{file_path}'")

        # 打开文件，以二进制模式读取
    with open(file_path, 'rb') as file:
        # 分块读取文件，每次读取4096字节（或更小的块），并更新哈希对象
        while True:
            # 读取4096个字节
            data = file.read(4096)
            if not data:
                # 没有更多的数据，跳出循环
                break
                # 更新哈希对象
            hash_object.update(data)

            # 获取十六进制哈希字符串
    return hash_object.hexdigest()


# wb01 烧录命令
def asrBootCmdGet(bootType, toolPath, bootPort, bootFile):
    asrBootCmd = ''
    if bootType == 'dl':
        asrBootCmd = f"{toolPath} {bootType} --port {bootPort} --chip 2"
    elif bootType == 'burn':
        asrBootCmd = f"{toolPath} {bootType} --port {bootPort} --chip 2 --path {bootFile} --multi"
    elif bootType == 'verify':
        asrBootCmd = f"{toolPath} {bootType} --port {bootPort} --chip 2 --path {bootFile} --multi"
    else:
        asrBootCmd = False
    return asrBootCmd


# csk 烧录命令
def cskBootCmdGet(bootType, toolPath, bootPort, bootFile, baudRate=BAUD_RATE):
    cskBootCmd = ''
    if bootType == "all":
        cskBootCmd = f"{toolPath} -b {baudRate} -p {bootPort} -c -t 10 -f {bootFile} -l -m -d -a {BOOT_ADDR} -s"
    elif bootType == "ap":
        cskBootCmd = f"{toolPath} -b {baudRate} -p {bootPort} -c -t 10 -f {bootFile} -l -m -d -a {CSK_AP_ADDR} -s"
    elif bootType == "cp":
        cskBootCmd = f"{toolPath} -b {baudRate} -p {bootPort} -c -t 10 -f {bootFile} -l -m -d -a {CSK_CP_ADDR} -s"
    return cskBootCmd


class cskFlashRWC():
    def __init__(self, fileSize, burnPort, cskBootPin, pduNum):
        # 初始化本地结果数据保存目录
        self.fileSize = fileSize
        self.fileByteSize = self.fileSize * 1024 * 1024
        tempT = datetime.datetime.now()
        timeTag = tempT.strftime("%Y-%m-%d_%H_%M_%S")
        self.resultFolder = os.path.join(os.getcwd(), 'result', f"{timeTag}-{self.fileSize}M")
        createdirs(self.resultFolder)
        self.output = output_log(1, self.resultFolder, timeTag)
        self.burnFilePath = os.path.join(self.resultFolder, "burnFile.bin")
        self.toolsFolder = os.path.join(os.getcwd(), 'tools')
        self.cskBurnPort = burnPort
        self.cskBurnFile = self.burnFilePath
        self.cskBootPinNum = 8
        self.asrBootPinNum = 0
        self.pduIp = pdu_device_ip
        self.pduDeviceNum = pduNum
        self.usb2xxNum = usb2xxxNum
        self.gpioHandle = usb2xxGpioHandle(self.usb2xxNum, self.output)

    def shell(self, cmd, tag, purpose, timeOut=10):
        # 使用subprocess.Popen执行exe文件并获取输出
        self.output.LOG_INFO(f"当前执行命令：{cmd}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = process.communicate(timeout=timeOut)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()

        # 将输出从字节转换为字符串
        stdout_str = stdout.decode("utf-8", "ignore")
        stderr_str = stderr.decode("utf-8", "ignore")
        self.output.LOG_INFO(f"\t\t**********{tag} 待验证**********")
        if tag in stdout_str:
            self.output.LOG_INFO(f"\t\t**********{purpose} 成功**********")
            return True
        else:
            self.output.LOG_ERROR(f"\t\t**********{purpose} 失败**********")
            self.output.LOG_INFO(f"shell 命令执行输出： {str(stdout_str)}")
            self.output.LOG_INFO(f"shell 命令执行异常： {str(stderr_str)}")
            return False

    def cskBurn(self):
        cskBurnTools = os.path.join(self.toolsFolder, "Uart_Burn_Tool.exe")
        tag = 'FLASH DOWNLOAD SUCCESS'
        purpose = 'csk 全量烧录 '
        burnNotDone = False
        cskBurnCmd = cskBootCmdGet("all", cskBurnTools, self.cskBurnPort, self.cskBurnFile, baudRate=BAUD_RATE)
        if not self.shell(cskBurnCmd, tag, purpose, timeOut=180):
            burnNotDone = True
        self.output.LOG_INFO(f"csk 烧录{not burnNotDone}")
        return not burnNotDone

    def verifyMd5(self, vType, size, md5Value):
        # size = tempMd5Info.get("size", 0)
        startAddr = 0x00
        # md5Value = tempMd5Info.get("md5Base", 0)
        cskBurnFilePath = os.path.join(self.toolsFolder, "cskburn.exe")
        cmd = f"{cskBurnFilePath} -C 6 -s {self.cskBurnPort} --verify {startAddr}:{size}"
        return self.shell(cmd, md5Value, f"{vType} 校验 md5 ")

    def bootControl(self, bootType):
        if bootType == 'inBoot':
            cskPinValue = 0
            asrPinValue = 1
        elif bootType == 'outBoot':
            cskPinValue = 1
            asrPinValue = 0
        else:
            self.output.LOG_INFO(f"当前boot类型为{bootType}，设置错误")
            return False
        retryTimes = 10
        bootControlValue = False
        self.output.LOG_INFO(f"当前boot类型为{bootType}，设置 cskPinValue：{cskPinValue}，设置 asrPinValue：{asrPinValue}")
        while retryTimes > 0:
            self.output.LOG_INFO(f"第 {10 - retryTimes} 次 控制引脚 {bootType} ")
            cskBoot = self.gpioHandle.setOnePinMaskPuPd(self.cskBootPinNum, cskPinValue)
            time.sleep(0.2)
            asrBoot = self.gpioHandle.setOnePinMaskPuPd(self.asrBootPinNum, asrPinValue)
            if cskBoot and asrBoot:
                bootControlValue = True
                break
            retryTimes -= 1
        self.output.LOG_INFO(f"第 {10 - retryTimes} 次 控制引脚 {bootType} : {bootControlValue}")
        return bootControlValue

    def burnFile(self):
        retry_times = 10
        self.output.LOG_INFO(f"进入烧录模式")
        if not self.gpioHandle.dvOpen():
            input("当前usb2xxx设备初始化失败，请测试人员检查")
        if not self.bootControl("inBoot"):
            input("当前烧录模式进入失败，请测试人员检查")
            self.bootControl("inBoot")
            return False
        self.gpioHandle.resetRetry = 3
        cskBurnRes = False
        while retry_times > 0:
            self.rebootDevice()
            cskBurnRes = self.cskBurn()
            if cskBurnRes:
                break
            retry_times -= 1
            self.output.LOG_INFO(f"当前烧录失败，还剩{retry_times}次重试")

        if not cskBurnRes:
            self.output.LOG_ERROR(f"当前烧录固件失败，请检查设备")
            return False
        if not self.bootControl("outBoot"):
            input("当前退出boot模式失败，请测试人员检查")
            self.bootControl("outBoot")
            return False
        # self.output.LOG_INFO(f"ota前的第 {self.otaTimes} 次烧录结果 {not self.isNotBurnDone}!!!")
        self.rebootDevice()
        time.sleep(0.1)
        return True

    def checkMd5(self, vType, size, md5Value):
        retry_times = 10
        self.output.LOG_INFO(f"进入md5检查模式")
        if not self.gpioHandle.dvOpen():
            input("当前usb2xxx设备初始化失败，请测试人员检查")
        if not self.bootControl("inBoot"):
            input("当前烧录模式进入失败，请测试人员检查")
            self.bootControl("inBoot")
        self.rebootDevice()
        time.sleep(0.5)
        checkRes = self.verifyMd5(vType, size, md5Value)
        if not self.bootControl("outBoot"):
            input("当前退出boot模式失败，请测试人员检查")
            self.bootControl("outBoot")
        # self.output.LOG_INFO(f"ota前的第 {self.otaTimes} 次烧录结果 {not self.isNotBurnDone}!!!")
        self.rebootDevice()
        return checkRes

    def pduPowerHandle(self, num, status):
        """
        num:第几个插头的序号
        status:True为开启，False为关闭
        """
        try:
            if pdu.check_netconnect(self.pduIp):
                pdu.TurnOnOff(self.pduIp, num, status)
                while True:
                    GetStatus = pdu.GetStatus(self.pduIp, num)
                    if status:
                        if GetStatus == 2:
                            self.output.LOG_INFO(f"第{num}个插座， ！")
                            return True
                        else:
                            self.output.LOG_INFO(f"第{num}个插座，正在检查上电状态，当前状态为{GetStatus}")
                    else:
                        if GetStatus == 1:
                            self.output.LOG_INFO(f"第{num}个插座，断电成功！")
                            return True
                        else:
                            self.output.LOG_INFO(f"第{num}个插座，正在检查断电状态，当前状态为{GetStatus}")
                    time.sleep(1)
            else:
                self.output.LOG_ERROR(f"IP地址：{self.pduIp}无法访问！！")
                return False
        except Exception as e:
            self.output.LOG_ERROR(f"继电器第{num}个插座上下电出错了，出错信息{e}")
            return False

    def rebootDevice(self, waitTime=8):
        # 重启设备
        self.output.LOG_INFO(f"开始给设备上硬重启，间隔{waitTime}s")
        self.pduPowerHandle(self.pduDeviceNum, False)
        time.sleep(waitTime)
        self.pduPowerHandle(self.pduDeviceNum, True)
        self.output.LOG_INFO(f"设备硬重启完成")

    def run(self):
        runtimes = 0
        checkFail = 0
        while True:

            generate_random_binary_file(self.burnFilePath, self.fileByteSize)
            if not os.path.exists(self.burnFilePath):
                time.sleep(1)
                continue
            currentMd5 = calculate_md5(self.burnFilePath)
            self.output.LOG_INFO(f"生成随机烧录文件，md5值为：{currentMd5}，文件大小：{self.fileByteSize}")
            # 开始烧录
            if not self.burnFile():
                self.output.LOG_ERROR(f"\t\t 当前测试{runtimes}次，烧录异常")
                continue
            # 断电重启
            # TODO 后续重启多次
            self.rebootDevice()
            # 检验md5值是否一致
            if not self.checkMd5("csk all", self.fileByteSize, currentMd5):
                self.output.LOG_ERROR(f"\t\t 当前测试{runtimes}次，md5 校验出现异常{checkFail}次")
                checkFail += 1
            else:
                self.output.LOG_INFO(f"\t\t 当前测试{runtimes}次，md5 校验成功")
            runtimes += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="获取外部参数库args")
    parser.add_argument('-f', "--fileSize", type=int, default=4, help="文件大小，默认4M,最大16M")
    parser.add_argument('-p', "--burnPort", type=str, default="COM36", help="csk烧录串口，如COM23")
    parser.add_argument('-c', "--cskBootPin", type=int, default=0, help="csk boot 脚接到usb2xxx 上的引脚，高电平拉低即可进入boot")
    parser.add_argument('-n', "--pduNum", type=int, default=8, help="pdu 控制序号")
    parser.add_argument('-s', "--show", type=int, default=0, help="显示当前设备号,0:不显示,1:显示")

    args = parser.parse_args()
    if args.show:
        showCurrentDev()
        sys.exit()
    if args.burnPort:
        otaRobot = cskFlashRWC(args.fileSize, args.burnPort, args.cskBootPin, args.pduNum)
        otaRobot.run()
    else:
        print(f"请输入正确的csk烧录串口号，如COM34")
