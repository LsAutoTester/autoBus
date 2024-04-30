# -*- coding: utf-8 -*-
__author__ = "bszheng"
__date__ = "2024/4/6"
__version__ = "1.0"
"""
支持功能:
1.脚本主要功能美的项目的设备自动烧录
2.OTA升级过程中断网断电
3.根据不同ota测试用例执行不同逻辑处理
依赖工具或设备:
1.pdu 继电器,主要用于设备断电
2usb2xxx ，主要用于csk和wb01 的烧录引脚短接
"""
import argparse
import datetime
import re
import subprocess
import traceback
import threading
import random
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from common.output_log import output_log
from common.Common_Func import get_serial, load_json, createdirs, fileIsExists
import common.pdusnmp as pdu
from common.USB2GPIO_Handle import *
from common.usb_device import *

pdu.initEngine()
# pdu_device_ip = '10.3.37.30'
sys.stdout.flush()
UART_NUM = 13
BOOT_ADDR = 0x000000
CSK_AP_ADDR = 0x45000
CSK_CP_ADDR = 0x200000
TONE_ADDR = 0x680000
TONE_ADDR_2 = 0x800000
CSK_EMPTY_ADDR = 0x40000
BAUD_RATE = 1500000


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


# 串口日志处理器
class serThread(threading.Thread):
    def __init__(self, projectInfo, deviceName, deviceInfo, output):
        super().__init__()
        self.projectInfo = projectInfo
        self.deviceName = deviceName
        self.portNum = deviceInfo.get("port", "")
        self.baudRate = deviceInfo.get("baudRate", 115200)
        self.regexMap = deviceInfo.get("regex", {})
        self.serial_data_type = deviceInfo.get("serial_data_type", "serial_data_type")
        # tempT = datetime.datetime.now()
        # timeTag = tempT.strftime("%Y-%m-%d_%H_%M_%S")
        # self.logName = os.path.join(output.path, f"{self.projectInfo}_{self.deviceName}_{self.portNum}_{timeTag}.log")
        self.logName = os.path.join(output.path, f"{self.projectInfo}_{self.deviceName}_{self.portNum}.log")
        self.output = output
        # 初始化需要正则结果的信息容器，一般设备重启或者指定场景需要重置所有信息为初始状态
        self.regexResult = {key: False for key in self.regexMap}
        self.serFp = ''
        self.stop_flag = False
        self.tempMsg = []
        self.currentBootReasonList = []

    def regexMatch(self, log_info):
        if not self.regexMap:
            return
        for regexTag, regex in self.regexMap.items():
            if not regex:
                continue
            kw = re.match(regex, log_info)
            if kw:
                try:
                    get_kw = kw.group(1).strip("\r\n ")
                    # TODO 正则到的结果二次处理
                    # 讲结果加入消息队列
                    self.regexResult.update({regexTag: get_kw})
                    if regexTag == 'otaDownloadProgress':
                        continue
                    if "Boot Reason" in regex:
                        self.currentBootReasonList.append(get_kw)
                    self.output.LOG_INFO(f"\t{self.deviceName}: {regexTag}正则匹配结果：{get_kw}")
                except Exception as e:
                    self.output.LOG_ERROR(f"{self.deviceName}的正则表达式{regex}匹配出错，出错信息{e}")

    def getRegexResult(self):
        return self.regexResult

    def cleanRegexResultBuff(self):
        self.output.LOG_INFO(f"清除 {self.deviceName}串口 RegexResultBuff 信息")
        self.regexResult = {key: False for key in self.regexMap}

    def clearSingleRegex(self, regexKey):
        self.output.LOG_INFO(f"清除 {self.deviceName}串口 {regexKey} 信息")
        self.regexResult.update({regexKey: False})

    def getBootReasonList(self):
        return self.currentBootReasonList

    def clearBootReasonList(self):
        self.currentBootReasonList = []

    def serActive(self):
        self.serFp = get_serial(self.portNum, self.baudRate)
        if self.serFp:
            return self.serFp.isOpen()
        else:
            self.output.LOG_ERROR(f"串口{self.portNum}无法连接！")
            return False
        # if not self.serFp.isOpen():
        #     raise EOFError("设备初始化失败")
        # return self.serFp.isOpen()

    def getSerMsg(self):
        return self.tempMsg

    def cleanMsgBuff(self):
        self.tempMsg.clear()

    def serWrite(self, cmd):
        if self.serFp:
            if self.serFp.isOpen():
                self.output.LOG_INFO(f"{self.deviceName}串口输入命令{cmd}")
                self.serFp.write(f"{cmd}\n".encode('utf-8'))

    def __del__(self):
        if self.serFp:
            if self.serFp.isOpen():
                self.serFp.close()

    def run(self):
        str_info = ""
        buffer = ""
        errorBefore = ''
        if self.serial_data_type == "hex":
            logfile = open(self.logName, "a+")
        else:
            logfile = open(self.logName, "ab+")
        if self.serActive():
            if self.serial_data_type == "hex":
                while not self.stop_flag:
                    try:
                        data = self.serFp.readline()
                        if data:
                            self.tempMsg.append(data)
                            now_time = datetime.datetime.now()
                            str_info = ''.join(['{:02x}'.format(b) for b in data]).upper()
                            buffer += str_info
                            self.output.LOG_DEBUG(f"buffer:{buffer}")
                            kw = re.match(self.deviceInfo['regex']["wakeupkw"], buffer)
                            if kw:
                                info = f"[{now_time}]{buffer}\n"
                                logfile.write(info)
                                logfile.flush()
                                self.regexMatch(buffer)
                                buffer = ""
                    except Exception as e:
                        if "拒绝访问" in str(e):
                            errorinfo = f"串口连接出现问题，请检查{self.portNum}串口是否掉线！！！\n"
                            self.stop_flag = True
                        else:
                            errorinfo = "Error info : %s, Current line : %s\n" % (e, str_info)
                        self.output.LOG_ERROR(f"{errorinfo}")
                    finally:
                        continue
            else:
                while not self.stop_flag:
                    try:
                        # num = self.serFp.inWaiting()
                        # str_info = self.serFp.read(num)
                        str_info = self.serFp.readline()
                        # if self.deviceName == "asrLog":
                        #     print(str_info)
                        #     print("==>:", str_info.decode('iso-8859-1'))
                        if str_info:
                            now_time = datetime.datetime.now()
                            b_info = bytes(f"[{now_time}]", encoding='utf-8') + str_info
                            logfile.write(b_info)
                            logfile.flush()
                            log_info = str_info.decode("utf-8", "ignore")  # 日志内存在不兼容的字符编码，加上ignore忽略异常
                            log_info = ILLEGAL_CHARACTERS_RE.sub('', log_info)  # 去掉非法字符
                            # asr 获取csk数据时，大量的写操作，此处避免将这些数据进入正则
                            if "lega_ota_write" in log_info:
                                continue
                            self.tempMsg.append(b_info)
                            self.regexMatch(log_info)
                    except Exception as e:
                        if errorBefore != str(e):
                            errorBefore = str(e)
                            if "拒绝访问" in str(e):
                                errorInfo = f"串口连接出现问题，请检查{self.portNum}串口是否掉线！！！\n"
                                self.stop_flag = True
                            else:
                                # traceback.print_exc()
                                errorInfo = "Error info : %s, Current line : %s\n" % (e, str_info)
                            self.output.LOG_ERROR(f"{errorInfo}")
                    finally:
                        continue
            logfile.close()
        else:
            logfile.close()
            self.output.LOG_ERROR(f"{self.portNum}串口连接出错，请重试！！")
            self.stop_flag = True


class TimerThread(threading.Thread):
    def __init__(self, interval=0.1):
        super().__init__()
        self.interval = interval
        self.stop_flag = False
        self.timeCost = 0
        self.serFp = ""
        self.rebootTime = 0
        self.logSetLevel = 0
        self.rebootTime = 0
        self.rebootTime = 0
        self.rebootTime = 0
        self.rebootTime = 0

    def run(self):
        while not self.stop_flag:
            time.sleep(self.interval)
            self.timeCost += 0.1

    def stop(self):
        self.stop_flag = True

    def reFresh(self, monitorType=0):
        # if monitorType:
        self.timeCost = 0

    def getTimeCost(self, monitorType=0):
        return self.timeCost


class crazyOTA:
    def __init__(self, config, testArgs):
        super().__init__()

        self.config = config
        self.testArgs = testArgs

        # 初始化设备参数
        self.projectInfo = self.config.get("projectInfo", "")
        self.deviceListInfo = self.config.get("deviceListInfo", {})
        self.configFolder = os.path.join(os.getcwd(), 'config', 'Firmware')

        # self.cskCmdList = self.config.get("cskCmdList", {})
        # self.asrCmdList = self.config.get("asrCmdList", {})

        self.cmdInfoFile = os.path.join(self.configFolder, 'otaTestInfo.json')
        if not fileIsExists(self.cmdInfoFile):
            print(f"首先检查挂载目录是否有Firmware文件信息，再检查本地config文件下是否有对应的烧录文件信息")
            sys.exit()
        self.otaInfo = load_json(self.cmdInfoFile)
        # 测试信息
        self.cskInfoKey = "cskApLog"
        self.asrInfoKey = "asrLog"
        self.deviceListInfo = self.config.get("deviceListInfo", {})
        self.clearList = self.config.get("clearListAsr", 0)
        # args 外部传参的测试信息
        self.testType = self.testArgs.testType
        self.testProject = self.testArgs.project
        self.testLable = self.testArgs.lable
        self.burnVersion = self.testArgs.version
        self.otaVersion = self.testArgs.otaVersion
        self.mideaOtaInfo = self.otaInfo.get("mideaOtaInfo", {})
        self.otaCmd = self.mideaOtaInfo.get(self.otaVersion, "")

        self.burnFolder = os.path.join(self.configFolder, self.testProject, f"V{self.burnVersion}")
        # createdirs(self.burnFolder)
        if not self.otaCmd:
            print(f"请检查{self.cmdInfoFile} 文件是否存在{self.otaVersion} 版本的ota升级命令。")
            print(f"如非jenkins平台执行此脚本，请在本地构建一个Firmware文件夹，详情询问bszheng")
            sys.exit()
        self.breakPower = self.testArgs.breakPower
        self.flashClear = self.testArgs.flashClear

        # 初始化本地结果数据保存目录
        tempT = datetime.datetime.now()
        timeTag = tempT.strftime("%Y-%m-%d_%H_%M_%S")
        self.resultFolder = os.path.join(os.getcwd(), 'result', timeTag + self.projectInfo + "-" + self.testLable)
        createdirs(self.resultFolder)
        self.output = output_log(1, self.resultFolder, timeTag)

        # csk 烧录信息
        self.cskBurnInfo = self.deviceListInfo.get("cskBurn", {})
        # 复制挂载目录下的烧录文件
        self.cskBurnFile = os.path.join(self.burnFolder, f"fw.img")
        self.cskBootPinNum = self.cskBurnInfo.get("pinNum", 8)
        self.cskBurnPort = self.cskBurnInfo.get("burnPort", '')
        # asr 烧录信息
        self.asrBurnInfo = self.deviceListInfo.get("asrLog", {})
        # 复制挂载目录下的烧录文件
        self.asrBurnFile = os.path.join(self.burnFolder, r"asr.bin")
        self.asrBootPinNum = self.asrBurnInfo.get("pinNum", 0)
        self.asrBurnPort = self.asrBurnInfo.get("port", '')

        # 初始化usb2xxx控制句柄
        self.usb2xxNum = self.config.get("usb2xxNum", "")
        self.gpioHandle = usb2xxGpioHandle(self.usb2xxNum, self.output)

        # pdu 信息
        self.pduInfo = self.config.get("pduInfo", {})
        self.pduDeviceNum = self.pduInfo.get("pduDeviceNum", "")
        self.pduWifiNum = self.pduInfo.get("pduWifiNum", "")
        self.pduIp = self.pduInfo.get("pduIp", "")

        # 初始化脚本中使用到的变量
        self.toolsFolder = os.path.join(os.getcwd(), 'tools')
        self.serFpPools = {}
        self.otaTimes = 0
        self.otaCmdSetDone = False

        if not fileIsExists(self.cskBurnFile) or not fileIsExists(self.asrBurnFile):
            print(f"首先检查挂载目录是否有Firmware文件信息，再检查本地config文件下是否有对应的烧录文件信息")
            sys.exit()

    def initSerDevice(self):
        # isDeviceInitDone = True
        if not self.deviceListInfo:
            self.output.LOG_ERROR(f"配置文件中设备信息异常，请检查")
            return
        for deviceName, deviceInfo in self.deviceListInfo.items():
            try:
                if "Log" in deviceName:
                    # 后续烧录完成后会重新初始化句柄，当句柄存在则不用重复初始化
                    if deviceName in self.serFpPools:
                        continue
                    self.output.LOG_INFO(f"开始初始化{deviceName}串口信息")
                    serFpThread = serThread(self.projectInfo, deviceName, deviceInfo, self.output)
                    self.serFpPools.update({deviceName: serFpThread})
                    serFpThread.start()
                    while True:
                        if serFpThread.serFp:
                            if serFpThread.serFp.isOpen():
                                self.output.LOG_INFO(f"{deviceName}串口正常打开！")
                                break
                            else:
                                self.output.LOG_INFO(f"{deviceName}串口打开失败！,清除已打开的设备后关闭退出测试")
                                self.clearSerThread()
                                sys.exit()
                        time.sleep(0.5)
            except Exception as e:
                self.output.LOG_ERROR(f"设备初始化失败{str(e)}")
                # traceback.print_exc()
                self.clearSerThread()
                return
        return True

    # 清除指定串口句柄
    def closeAsrSer(self, asrSerName):
        asrSerFp = self.serFpPools.get(asrSerName, "")
        self.serFpPools = {key: value for key, value in self.serFpPools.items() if key != asrSerName}

        clearStep = 0
        self.output.LOG_INFO(f"清除asr 串口信息")
        if asrSerFp.serFp:
            clearStep += 1
            asrSerFp.stop_flag = True
            if asrSerFp.serFp.isOpen():
                asrSerFp.serFp.close()
                self.output.LOG_INFO(f"asr 串口信息清除成功")
            if not asrSerFp.serFp.isOpen():
                # asrSerFp.stop_flag = True
                return True
            else:
                time.sleep(0.5)
                self.closeAsrSer(asrSerName)
        else:
            time.sleep(0.5)
            self.closeAsrSer(asrSerName)

    def clearSerThread(self):
        # 清除所有串口句柄
        self.output.LOG_INFO("销毁串口线程和对应串口句柄")
        for serFpName, tempSerFp in self.serFpPools.items():
            tempSerFp.stop_flag = True
            self.output.LOG_INFO(f"清除{serFpName}信息")
            if tempSerFp.serFp:
                if tempSerFp.serFp.isOpen():
                    tempSerFp.serFp.close()
            # tempSerFp.stop_flag = True
        self.serFpPools = {}

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

    def clearFlashInfo(self, cmdSer, clearArgsList, retryTimes=3):
        # 清除asr flash 信息
        # clearList = ['lsboot_ver', "ota_url", "ota_md5", "ota_step"]
        for args in clearArgsList:
            tempCmd = f"listen flash clear {args}"
            self.cmdShell(cmdSer, tempCmd)
        self.cmdShell(cmdSer, "listen flash show")
        unClearArgsList = self.verifyIsClean(cmdSer, clearArgsList)
        if unClearArgsList:
            retryTimes -= 1
            if retryTimes > 0:
                self.clearFlashInfo(cmdSer, unClearArgsList, retryTimes)
            else:
                argsStr = ' ## '.join(unClearArgsList)
                self.output.LOG_INFO(f"还剩{argsStr}没清理完成")
                return False
        else:
            argsStr = ' ## '.join(clearArgsList)
            self.output.LOG_INFO(f"参数{argsStr}清理完成")
            return True

    def verifyIsClean(self, cmdSer, clearArgsList):
        # 检查某些配置命令信息是否清除完成
        # clearArgsList = ['lsboot_ver', "ota_url", "ota_md5", "ota_step"]
        unClearArgsList = []
        for agrs in clearArgsList:
            if self.verifyCmdIsWork(cmdSer, tag=f"{agrs}="):
                unClearArgsList.append(agrs)
        return unClearArgsList

    def cmdShell(self, cmdSer, cmd):
        # 串口命令输入
        if cmdSer.serFp:
            if cmdSer.serFp.isOpen():
                cmdSer.cleanMsgBuff()
                cmdSer.serWrite(cmd)
                time.sleep(0.5)

    # def verifyCmdIsWork(self, cskSer, regex):
    def verifyCmdIsWork(self, cmdSer, tag="success"):
        # 检查命令是否设置成功
        for line in cmdSer.getSerMsg():
            log_info = line.decode("utf-8", "ignore")  # 日志内存在不兼容的字符编码，加上ignore忽略异常
            log_info = ILLEGAL_CHARACTERS_RE.sub('', log_info)
            # kw = re.match(regex, log_info)
            # if kw:
            #     return kw.group(1)
            # return False
            if tag in log_info:
                self.output.LOG_INFO(f"验证命令执行成功：{log_info}")
                return True
        return False

    def logLevelSet(self, cmdSer, level=4):
        self.output.LOG_INFO(f"设置日志等级为{level}")
        self.cmdShell(cmdSer, f"flash.setloglev {level}")
        self.cmdShell(cmdSer, f"console 1")
        if not self.verifyCmdIsWork(cmdSer):
            time.sleep(1)
            self.cmdShell(cmdSer, "\n")
            time.sleep(0.1)
            self.cmdShell(cmdSer, "\r\n")
            time.sleep(0.1)
            self.logLevelSet(cmdSer)

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

    def asrBurn(self):
        burnNotDone = False
        asrBurnTools = os.path.join(self.toolsFolder, "ASR_downloader_V1.1.5", "ASR_downloader.exe")
        dlTag = 'welcome to download'
        burnTag = 'burn ok'
        verifyTag = 'crc done'
        asrBurnCmd_dl = asrBootCmdGet("dl", asrBurnTools, self.asrBurnPort, self.asrBurnFile)
        self.output.LOG_INFO(f"开始asr 的固件{self.asrBurnFile}烧录。")
        if not self.shell(asrBurnCmd_dl, dlTag, 'asr 串口检查  ', timeOut=120):
            burnNotDone = True
        asrBurnCmd_burn = asrBootCmdGet("burn", asrBurnTools, self.asrBurnPort, self.asrBurnFile)
        if not self.shell(asrBurnCmd_burn, burnTag, 'asr 全量烧录 burn ', timeOut=120):
            burnNotDone = True
        asrBurnCmd_verify = asrBootCmdGet("verify", asrBurnTools, self.asrBurnPort, self.asrBurnFile)
        if not self.shell(asrBurnCmd_verify, verifyTag, 'asr 全量烧录 verify ', timeOut=120):
            burnNotDone = True
        self.output.LOG_INFO(f"asr 烧录{not burnNotDone}")
        return not burnNotDone

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

    def rebootDevice(self, waitTime=10):
        # 重启设备
        self.output.LOG_INFO(f"开始给设备上硬重启，间隔{waitTime}s")
        self.pduPowerHandle(self.pduDeviceNum, False)
        time.sleep(waitTime)
        self.pduPowerHandle(self.pduDeviceNum, True)
        self.output.LOG_INFO(f"设备硬重启完成")

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

    def otaFile(self, cskSer, cmd, retryTimes=10):
        # ota命令下发，可指定重复次数，
        cmdSetTotal = retryTimes
        otaCmdSetDone = False
        self.output.LOG_INFO(f"进入ota命令升级模式，当前执行次数{retryTimes}")
        while retryTimes > 0:
            self.cmdShell(cskSer, "\n")
            time.sleep(0.1)
            self.cmdShell(cskSer, "\r\n")
            time.sleep(0.1)
            self.cmdShell(cskSer, cmd)
            tag = "loop"
            time.sleep(1)
            if self.verifyCmdIsWork(cskSer, tag):
                otaCmdSetDone = True
                break
            time.sleep(2)
            retryTimes -= 1
        self.output.LOG_INFO(f"ota 烧录命令下发第{cmdSetTotal - retryTimes}次，结果{otaCmdSetDone}！")
        return otaCmdSetDone

    def burnFile(self, asrFpName, burnType="all"):
        retry_times = 10

        self.output.LOG_INFO(f"进入烧录模式")
        if not self.gpioHandle.dvOpen():
            input("当前usb2xxx设备初始化失败，请测试人员检查")
        if not self.bootControl("inBoot"):
            input("当前烧录模式进入失败，请测试人员检查")
            self.bootControl("inBoot")
        self.closeAsrSer(asrFpName)
        self.gpioHandle.resetRetry = 3
        cskBurnRes = False
        asrBurnRes = False
        while retry_times > 0:
            self.rebootDevice()
            if burnType == "csk" and not cskBurnRes:
                cskBurnRes = self.cskBurn()
            elif burnType == "asr" and not asrBurnRes:
                asrBurnRes = self.asrBurn()
            else:
                if not asrBurnRes:
                    asrBurnRes = self.asrBurn()
                if not cskBurnRes:
                    cskBurnRes = self.cskBurn()
            if cskBurnRes and asrBurnRes:
                break
            retry_times -= 1
            self.output.LOG_INFO(f"当前烧录失败，还剩{retry_times}次重试")

        if not (asrBurnRes and cskBurnRes):
            self.clearSerThread()
            self.output.LOG_ERROR(f"当前烧录固件失败，请检查设备")
            raise EnvironmentError("当前烧录异常")
        if not self.bootControl("outBoot"):
            input("当前退出boot模式失败，请测试人员检查")
            self.bootControl("outBoot")
        # self.output.LOG_INFO(f"ota前的第 {self.otaTimes} 次烧录结果 {not self.isNotBurnDone}!!!")
        self.rebootDevice()
        time.sleep(0.1)
        if not self.initSerDevice():
            input("当前设备初始化失败，请测试人员检查")
        return True

    def upgrade(self, cskSerFp, asrSerFp, buildInfo, netWorkConnect):
        otaCmd = self.otaCmd
        if not otaCmd:
            self.output.LOG_ERROR(f"当前版本 {buildInfo},升级命令为空，请检查配置文件")
            return False
        if otaCmd == "burn":
            self.output.LOG_INFO(f"开始烧录文件")
            if self.flashClear:
                self.output.LOG_INFO(f"开始清理 asr flash info")
                self.clearFlashInfo(asrSerFp, self.clearList)
                self.cmdShell(asrSerFp, "listen flash show")
            else:
                self.output.LOG_INFO(f"开始清理部分 asr  flash info")
                infoList = ["lsboot_ver", "bootcfg_num"]
                self.clearFlashInfo(asrSerFp, infoList)
                self.cmdShell(asrSerFp, "listen flash show")
                self.output.LOG_INFO(f"无需清理 asr flash info")
            cskSerFp.cleanRegexResultBuff()
            asrSerFp.cleanRegexResultBuff()
            self.burnFile(self.asrInfoKey, "all")

            time.sleep(2)
            # self.logLevelSet(cskSerFp)
        else:
            if netWorkConnect and not self.otaCmdSetDone:
                self.output.LOG_INFO(f"当前版本 {buildInfo},待升级{otaCmd}")
                if self.otaFile(cskSerFp, otaCmd):
                    self.output.LOG_INFO(f'ota 命令下发成功')
                    return True

    def onlyBurn(self):
        self.output.LOG_INFO(f"当前测试类型为低版本升级到高版本，再烧录回低版本")
        if not self.initSerDevice() or not self.gpioHandle.dvOpen():
            self.output.LOG_ERROR(f"退出当前测试")
        self.burnFile(self.asrInfoKey, "all")
        time.sleep(10)
        asrSerFp = self.serFpPools.get("asrLog", "")
        cskSerFp = self.serFpPools.get("cskApLog", "")
        self.cmdShell(cskSerFp, "version")
        self.cmdShell(cskSerFp, f"flash.setloglev {4}")
        self.cmdShell(cskSerFp, f"console 1")
        time.sleep(2)
        self.clearSerThread()

    def rebootThread(self, effectTime, cskSerFp, asrSerFp):
        try:
            self.output.LOG_INFO(f" {effectTime}s 后重启设备")
            time.sleep(effectTime)
            cskSerFp.cleanRegexResultBuff()
            self.rebootDevice()
        except Exception as e:
            self.output.LOG_ERROR(f" 硬重启异常： {str(e)}")

    def otaLoop(self):
        runtimes = 0
        self.output.LOG_INFO(f"当前测试类型为ota 升级自身循环")
        if not self.initSerDevice():
            self.output.LOG_ERROR(f"退出当前测试")
        # 获取当前可用的串口句柄，可读取对应的串口数据、和配置文件中需要正则的内容
        asrSerFp = self.serFpPools.get("asrLog", "")
        cskSerFp = self.serFpPools.get("cskApLog", "")
        self.cmdShell(asrSerFp, "listen flash setloglev 4")
        otaCmd = self.otaCmd
        while True:
            otaStep = 0
            try:
                # 清除当前句柄里正则到的信息为空
                cskSerFp.cleanRegexResultBuff()
                asrSerFp.cleanRegexResultBuff()
                self.output.LOG_INFO(f"\t\t^^^^^^^^^^CURRENT TESTTIMES {runtimes} START^^^^^^^^^^")
                # 执行命令
                self.cmdShell(asrSerFp, "listen flash show")
                otaTime = 400
                otaSetDone = False
                cmdRetryTime = 0
                cskRebootTimes = 0
                breakPower = False
                otaDone = False
                while otaTime > 0:
                    try:
                        # 当ota 命令未设置成功或者重复次数少于20次继续设置ota的升级命令
                        if not otaSetDone and cmdRetryTime < 20:
                            cmdRetryTime += 1
                            self.cmdShell(cskSerFp, "version")
                            self.cmdShell(cskSerFp, f"flash.setloglev {4}")
                            self.cmdShell(cskSerFp, f"console 1")
                            if self.otaFile(cskSerFp, otaCmd, 1):
                                otaSetDone = True
                                otaStep = 1

                        # if cskSerFp.getRegexResult().get("otaDownLoadDone", False):
                        #     # 清除asr的正则结果
                        #     asrSerFp.cleanRegexResultBuff()
                        #     if self.breakPower == 2 and not breakPower:
                        #         breakPower = True
                        #         sleepTime = random.randint(10, 70)
                        #         rebootThreadFp = threading.Thread(target=self.rebootThread,
                        #                                           args=[sleepTime, cskSerFp, asrSerFp, ])
                        #         rebootThreadFp.start()
                        #     cskSerFp.clearSingleRegex("otaDownLoadDone")

                        if cskSerFp.getRegexResult().get("otaDone", False) and not otaDone:
                            otaStep = 2
                            otaDone = True
                            self.output.LOG_INFO(f"升级完成，将此轮ota升级剩余时间{otaTime}s 重置为10s，10s后开始进入下一轮测试")
                            otaTime = 10
                        if otaTime % 20 == 0:
                            self.output.LOG_INFO(f"当前OTA还剩 {otaTime}s")
                        # 检测当前是否有异常信息
                        currentBootReason = cskSerFp.getRegexResult().get("bootReason", False)
                        if currentBootReason:
                            cskRebootTimes += 1
                            if currentBootReason not in ['POWER|HWPIN 0x03', 'REBOOT 0x60']:
                                self.output.LOG_ERROR(
                                    f"########## 运行{runtimes}次当前csk异常重启：{currentBootReason}##########")
                            cskSerFp.clearSingleRegex("bootReason")
                    except Exception as e:
                        self.output.LOG_ERROR(f"测试出现异常{str(e)}")
                    time.sleep(1)
                    otaTime -= 1
                # self.cmdShell(asrSerFp, "reboot")
                time.sleep(5)
            except Exception as e:
                self.output.LOG_ERROR(f"测试出现异常{str(e)}")
            # 检查当前lsboot 是否升级
            upgradeFailList = []
            for bootOtaTag in ["bootSet1", "bootSet2", "bootSet3", "bootSet4"]:
                tempBootTag = asrSerFp.getRegexResult().get(bootOtaTag, False)
                if not tempBootTag:
                    upgradeFailList.append(bootOtaTag)
            if upgradeFailList:
                self.output.LOG_INFO(f"当前测试第{runtimes}次结束,检测到boot升级存在异常，异常阶段：{','.join(upgradeFailList)}")
            self.output.LOG_INFO(f"当前测试第{runtimes}次结束,csk 重启{cskRebootTimes}次")
            time.sleep(10)
            runtimes += 1

    def otaLoopSameAction(self):
        runtimes = 0
        self.output.LOG_INFO(f"当前测试类型为低版本升级到高版本，再烧录回低版本")
        if not self.initSerDevice() or not self.gpioHandle.dvOpen():
            self.output.LOG_ERROR(f"退出当前测试")
        # timeMonitor = TimerThread()
        # timeMonitor.start()
        # self.serFpPools.update({"timeMonitor": timeMonitor})
        tempVerifyAsrBoot = 0
        while True:
            exceptionMsg = ''
            otaStep = 0
            try:
                # 获取当前可用的串口句柄，可读取对应的串口数据、和配置文件中需要正则的内容
                asrSerFp = self.serFpPools.get("asrLog", "")
                cskSerFp = self.serFpPools.get("cskApLog", "")
                # 清除当前句柄里正则到的信息为空
                cskSerFp.cleanRegexResultBuff()
                asrSerFp.cleanRegexResultBuff()
                cskSerFp.clearBootReasonList()

                self.output.LOG_INFO(f"\t\t^^^^^^^^^^CURRENT TESTTIMES {runtimes} START^^^^^^^^^^")
                time.sleep(5)
                self.cmdShell(asrSerFp, "listen flash setloglev 4")
                # 清除当前asr 相关信息
                if self.flashClear:
                    self.output.LOG_INFO(f"testTime {runtimes} :开始清理 asr  flash info")
                    self.clearFlashInfo(asrSerFp, self.clearList)
                    self.cmdShell(asrSerFp, "listen flash show")
                else:
                    self.output.LOG_INFO(f"testTime {runtimes} :开始清理部分 asr  flash info")
                    infoList = ["lsboot_ver", "bootcfg_num"]
                    self.clearFlashInfo(asrSerFp, infoList)
                    self.cmdShell(asrSerFp, "listen flash show")
                # 文件烧录
                self.burnFile(self.asrInfoKey, "all")
                time.sleep(10)
                # 烧录完成后，更新当前句柄库里的对应句柄，获取最新的串口句柄。
                asrSerFp = self.serFpPools.get("asrLog", "")
                cskSerFp = self.serFpPools.get("cskApLog", "")
                asrInfo = asrSerFp.getRegexResult().get("buildInfo", '')
                cskInfo = cskSerFp.getRegexResult().get("buildInfo", '')
                self.output.LOG_INFO(f"烧录后 asr 版本信息 :{asrInfo}")
                self.output.LOG_INFO(f"烧录后 csk 版本信息 :{cskInfo}")
                buildInfo = cskSerFp.getRegexResult().get("buildInfo", '')
                otaCmd = self.otaCmd
                if otaCmd == "burn":
                    runtimes += 1
                    continue
                time.sleep(4)
                # 执行命令
                self.cmdShell(asrSerFp, "listen flash show")
                otaTime = 400
                otaSetDone = False
                cmdRetryTime = 0
                cskRebootTimes = 0
                breakPower = False
                otaDone = False
                breakPowerTime = 0

                while otaTime > 0:
                    try:
                        # 当ota 命令未设置成功或者重复次数少于20次继续设置ota的升级命令
                        if not otaSetDone and cmdRetryTime < 20:
                            cmdRetryTime += 1
                            self.cmdShell(cskSerFp, "version")
                            self.cmdShell(cskSerFp, f"flash.setloglev {4}")
                            self.cmdShell(cskSerFp, f"console 1")
                            self.output.LOG_INFO(f"当前build信息{buildInfo},命令{otaCmd}")
                            if self.otaFile(cskSerFp, otaCmd, 1):
                                otaSetDone = True
                                otaStep = 1

                        if cskSerFp.getRegexResult().get("otaDownLoadDone", False):
                            # 清除asr的正则结果
                            otaStep = 2
                            asrSerFp.cleanRegexResultBuff()
                            cskSerFp.clearSingleRegex("otaDownLoadDone")
                            if self.breakPower == 2 and not breakPower:
                                breakPower = True
                                sleepTime = random.randint(10, 70)
                                breakPowerTime = otaTime - sleepTime
                                self.output.LOG_INFO(f"当前下载已完成，预计 {sleepTime} s后重启设备")
                                rebootThreadFp = threading.Thread(target=self.rebootThread,
                                                                         args=[sleepTime, cskSerFp, asrSerFp, ])
                                rebootThreadFp.start()
                                # time.sleep(sleepTime)
                                # self.output.LOG_INFO(f"开始重启当前设备")
                                # cskSerFp.cleanRegexResultBuff()
                                # self.rebootDevice()
                                # otaTime -= sleepTime

                        # if breakPower and otaTime == breakPowerTime:
                        #     self.output.LOG_INFO(f"开始重启当前设备")
                        #     cskSerFp.cleanRegexResultBuff()
                        #     self.rebootDevice()
                        #     otaTime -= 10
                        if cskSerFp.getRegexResult().get("otaDone", False) and not otaDone:
                            otaStep = 3
                            otaDone = True
                            self.output.LOG_INFO(f"升级完成，将此轮ota升级剩余时间{otaTime}s 重置为10s，10s后开始进入下一轮测试")
                            otaTime = 10
                        if otaTime % 20 == 0:
                            self.output.LOG_INFO(f"当前OTA还剩 {otaTime}s")
                        # 检测当前是否有异常信息
                        currentBootReason = cskSerFp.getRegexResult().get("bootReason", False)
                        if currentBootReason:
                            cskRebootTimes += 1
                            if currentBootReason not in ['POWER|HWPIN 0x03', 'REBOOT 0x60']:
                                self.output.LOG_ERROR(
                                    f"########## 运行{runtimes}次当前csk异常重启：{currentBootReason}##########")
                            cskSerFp.clearSingleRegex("bootReason")
                    except Exception as e:
                        self.output.LOG_ERROR(f"测试出现异常{str(e)}")
                    time.sleep(1)
                    otaTime -= 1
                # self.cmdShell(asrSerFp, "reboot")
                time.sleep(5)
            except Exception as e:
                self.output.LOG_ERROR(f"测试出现异常{str(e)}")
                traceback.print_exc()
            # 检查当前lsboot 是否升级
            upgradeFailList = []
            for bootOtaTag in ["bootSet1", "bootSet2", "bootSet3", "bootSet4"]:
                tempBootTag = asrSerFp.getRegexResult().get(bootOtaTag, False)
                if not tempBootTag:
                    upgradeFailList.append(bootOtaTag)
            if upgradeFailList:
                self.output.LOG_ERROR(f"当前测试第{runtimes}次结束,检测到boot升级存在异常，异常阶段：{','.join(upgradeFailList)}")
            else:
                otaStep = 4
            cskBootReasonList = cskSerFp.getBootReasonList()
            tempBootReasonTag = ' -==- '.join(cskBootReasonList)
            self.output.LOG_INFO(f"csk 重启原因如下 {tempBootReasonTag}")
            self.output.LOG_INFO(
                f"\t\t\t\t ********** 当前测试第{runtimes}次结束,csk 重启{len(cskBootReasonList)}次,ota 执行最后阶段 {otaStep} **********\n\n")
            time.sleep(10)
            runtimes += 1

    def run(self):
        try:
            if self.testType == "onlyBurn":
                # 只烧录指定固件
                self.onlyBurn()
                # testTime = 20
                # while testTime > 0:
                #     self.output.LOG_INFO(f"当前烧录第 {20 - testTime} 次")
                #     self.onlyBurn()
                #     testTime -= 1
            elif self.testType == "burnLOtaH":
                # 烧录指定固件，ota升级到目标固件
                self.otaLoopSameAction()
            elif self.testType == "burnLOtaM2H":
                # 烧录到指定版本，ota升级某一个固定版本，在升级到最终版本
                pass
            elif self.testType == "onlyOta":
                # 循环ota升级某一个固定版本，循环升级
                pass
            else:
                pass
        except KeyboardInterrupt as e:
            print(e)
        except Exception as e:
            traceback.print_exc()
            print(e)
        finally:
            self.clearSerThread()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="获取外部参数库args")
    parser.add_argument('-f', "--file", type=str, default="", help="测试配置文件路径")
    parser.add_argument('-s', "--show", type=int, default=0, help="显示当前设备号,0:不显示,1:显示")
    parser.add_argument('-p', "--project", type=str, default="Midea_Offline_CSK6011B_WB01", help="当前测试的类型")
    parser.add_argument('-v', "--version", type=str, default="1.0.26", help="当前测试的类型")
    parser.add_argument('-t', "--testType", type=str, default="burnLOtaH", help="当前测试的类型")
    parser.add_argument('-b', "--breakPower", type=int, default=0, help="当前随机断电阶段。0:不断电,1:下载断电,2:升级断电,3:下载断网,4:下载断电断网")
    parser.add_argument('-c', "--flashClear", type=int, default=0, help="asr升级信息清除。0:不不清除,1:清除")
    parser.add_argument('-o', "--otaVersion", type=str, default=r"1.0.52", help="当前测试的类型")
    parser.add_argument('-l', "--lable", type=str, default="测试一下", help="当前测试的标注，标记当前的测试内容")

    args = parser.parse_args()
    if args.show:
        showCurrentDev()
        sys.exit()
    deviceInfo = args.file
    if os.path.isfile(deviceInfo):
        otaInfo = load_json(deviceInfo)
        otaRobot = crazyOTA(otaInfo, args)
        otaRobot.run()
    else:
        print(f"请输入正确的测试配置文件,当前配置文件不存在{deviceInfo}")
    # filePath = os.path.join("Z:\\","Firmware","Midea_Offline_CSK6011B_WB01","V1.0.26",
    # "Midea_Offline_WB01_3IN1_1.0.26.bin") filePath_ = os.path.join("Z:\\","Firmware","Midea_Offline_CSK6011B_WB01")
    # shutil.copy(filePath,filePath_)
