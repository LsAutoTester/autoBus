import argparse
import datetime
import os
import re
import subprocess
import sys
import time
import traceback
import threading
import time
import random

from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from common.Common_Func import get_serial
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from common.output_log import output_log
from common.Common_Func import get_serial, load_json, createdirs, generate_random_char, Random_time
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

    def regexMatch(self, log_info):
        if not self.regexMap:
            return
        for regexTag, regex in self.regexMap.items():
            if not regex:
                # self.output.LOG_ERROR(f"{regexTag}的正则内容为空：{regex}\n")
                # self.stop_flag = True
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
                    self.output.LOG_INFO(f"\t{self.deviceName}: {regexTag}正则匹配结果：{get_kw}")
                except Exception as e:
                    self.output.LOG_INFO(f"{self.deviceName}的正则表达式{regex}匹配出错，出错信息{e}")

    def getRegexResult(self):
        return self.regexResult

    def cleanRegexResultBuff(self):
        self.output.LOG_INFO(f"清除 {self.deviceName}串口 RegexResultBuff 信息")
        self.regexResult = {key: False for key in self.regexMap}

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
                        str_info = self.serFp.readline()
                        if str_info:
                            now_time = datetime.datetime.now()
                            b_info = bytes(f"[{now_time}]", encoding='utf-8') + str_info
                            logfile.write(b_info)
                            logfile.flush()
                            log_info = str_info.decode("utf-8", "ignore")  # 日志内存在不兼容的字符编码，加上ignore忽略异常
                            log_info = ILLEGAL_CHARACTERS_RE.sub('', log_info)  # 去掉非法字符
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
        self.cskCmdList = self.config.get("cskCmdList", {})
        self.asrCmdList = self.config.get("asrCmdList", {})

        # 初始化本地结果数据保存目录
        tempT = datetime.datetime.now()
        timeTag = tempT.strftime("%Y-%m-%d_%H_%M_%S")
        self.resultFolder = os.path.join(os.getcwd(), 'result', timeTag+ self.projectInfo)
        createdirs(self.resultFolder)
        self.output = output_log(1, self.resultFolder, timeTag )

        # 测试信息
        self.cskInfoKey = "cskApLog"
        self.asrInfoKey = "asrLog"
        self.deviceListInfo = self.config.get("deviceListInfo", {})
        self.otaType = self.config.get("otaType", {})
        self.testType = self.config.get("testType", "")
        self.flashClear = self.config.get("flashClear", 0)
        self.clearList = self.config.get("clearListAsr", 0)
        # args 外部传参的测试信息
        self.testType = self.testArgs.testType
        # csk 烧录信息
        self.cskBurnInfo = self.deviceListInfo.get("cskBurn", {})
        self.cskBurnFile = self.cskBurnInfo.get("cskBurnFile", "")
        self.cskBootPinNum = self.cskBurnInfo.get("pinNum", 8)
        self.cskBurnPort = self.cskBurnInfo.get("burnPort", '')
        # asr 烧录信息
        self.asrBurnInfo = self.deviceListInfo.get("asrLog", {})
        self.asrBurnFile = self.asrBurnInfo.get("asrBurnFile", "")
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
        self.isNotBurnDone = True
        self.serFpPools = {}
        self.otaTimes = 0
        self.otaCmdSetDone = False

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
        asrBurnTools = os.path.join(self.toolsFolder, "wb01Burn.exe")
        # asrBurnTools = r"D:\JenkinsWork\autoBus\tools\ASR_downloader_V1.1.4_0312\ASR_downloader_V1.1.4\ASR_downloader_V1.1.4.exe"
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

    def inBoot(self):
        # 进入烧录模式
        cskBoot = self.gpioHandle.setPinMaskPuPd(self.cskBootPinNum, 0)
        time.sleep(0.2)
        asrBoot = self.gpioHandle.setPinMaskPuPd(self.asrBootPinNum, 1)
        if cskBoot and asrBoot:
            return True
        else:
            if self.gpioHandle.resetRetry == 0:
                return False
            self.gpioHandle.usb2xxReset()
            self.inBoot()

    def outBoot(self):
        # 退出烧录模式
        cskBoot = self.gpioHandle.setPinMaskPuPd(self.cskBootPinNum, 1)
        time.sleep(0.2)
        asrBoot = self.gpioHandle.setPinMaskPuPd(self.asrBootPinNum, 0)
        if cskBoot and asrBoot:
            return True
        else:
            if self.gpioHandle.resetRetry == 0:
                return False
            self.gpioHandle.usb2xxResetBoot()
            self.outBoot()

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

        self.output.LOG_INFO(f"进入烧录模式")
        self.isNotBurnDone = False
        if not self.gpioHandle.dvOpen():
            input("当前usb2xxx设备初始化失败，请测试人员检查")
        if not self.inBoot():
            self.isNotBurnDone = True
            return self.isNotBurnDone
        self.closeAsrSer(asrFpName)
        self.gpioHandle.resetRetry = 3
        self.rebootDevice()
        if burnType == "csk":
            cskBurn = self.cskBurn()
        elif burnType == "asr":
            asrBurn = self.asrBurn()
        else:
            asrBurn = self.asrBurn()
            cskBurn = self.cskBurn()
            if not (asrBurn and cskBurn):
                self.isNotBurnDone = True
        if not self.outBoot():
            self.isNotBurnDone = True
        # self.output.LOG_INFO(f"ota前的第 {self.otaTimes} 次烧录结果 {not self.isNotBurnDone}!!!")
        self.rebootDevice()
        time.sleep(0.1)
        if not self.initSerDevice():
            input("当前设备初始化失败，请测试人员检查")
        return not self.isNotBurnDone

    def upgrade(self, cskSerFp, asrSerFp, buildInfo, netWorkConnect):
        otaCmd = self.otaType.get(buildInfo, "")
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
            try:
                # 获取当前可用的串口句柄，可读取对应的串口数据、和配置文件中需要正则的内容
                asrSerFp = self.serFpPools.get("asrLog", "")
                cskSerFp = self.serFpPools.get("cskApLog", "")
                # 清除当前句柄里正则到的信息为空
                cskSerFp.cleanRegexResultBuff()
                asrSerFp.cleanRegexResultBuff()
                self.output.LOG_INFO(f"\t^^^^^^^^^^CURRENT TESTTIMES {runtimes} START^^^^^^^^^^")
                time.sleep(3)
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
                # self.cmdShell(asrSerFp, "reboot")
                # time.sleep(5)
                # 获取asr和csk 的build信息
                asrInfo = asrSerFp.getRegexResult().get("buildInfo", '')
                cskInfo = cskSerFp.getRegexResult().get("buildInfo", '')
                self.output.LOG_ERROR(f"烧录后 asr 版本信息 :{asrInfo}")
                self.output.LOG_ERROR(f"烧录后 csk 版本信息 :{cskInfo}")
                if asrInfo == "3afcdd5d":
                    self.output.LOG_ERROR(f"当前版本烧录后asr信息不匹配")
                else:
                    self.output.LOG_ERROR(f"当前版本烧录后asr信息匹配,进入ota升级")
                buildInfo = cskSerFp.getRegexResult().get("buildInfo", '')
                otaCmd = self.otaType.get("initOta", "")
                if otaCmd == "burn":
                    runtimes += 1
                    continue
                time.sleep(4)
                # 执行命令
                self.cmdShell(asrSerFp, "listen flash show")
                otaTime = 400
                otaSetDone = False
                cmdRetryTime = 0
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

                        if cskSerFp.getRegexResult().get("otaDownLoadDone", False):
                            sleepTime = random.randint(10, 70)
                            self.output.LOG_INFO(f'testTime {runtimes} : 等待{sleepTime}s 后重启设备')
                            time.sleep(sleepTime)
                            self.rebootDevice()
                            otaTime -= sleepTime
                            cskSerFp.cleanRegexResultBuff()

                        if cskSerFp.getRegexResult().get("otaDone", False):
                            self.output.LOG_INFO(f"升级完成，将{otaTime} 重置为10s，10后开始进入烧录")
                            time.sleep(10)
                            otaTime = 0
                        if otaTime % 10 == 0:
                            self.output.LOG_INFO(f"当前OTA还剩 {otaTime}s")
                    except Exception as e:
                        self.output.LOG_ERROR(f"测试出现异常{str(e)}")
                    time.sleep(1)
                    otaTime -= 1
                # self.cmdShell(asrSerFp, "reboot")
                time.sleep(5)
            except Exception as e:
                self.output.LOG_ERROR(f"测试出现异常{str(e)}")
            time.sleep(1)
            runtimes += 1

    def run(self):
        try:
            if self.testType == "burn":
                # 只烧录指定固件
                pass
            elif self.testType == "burnLOtaH":
                # 烧录指定固件，ota升级到目标固件
                self.otaLoopSameAction()
            elif self.testType == "otaLoop1":
                # 循环ota升级某一个固定版本
                pass
            elif self.testType == "otaLoop2":
                # 循环ota升级某两个固定版本，来回升级
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
    parser.add_argument('-t', "--testType", type=str, default="burnLOtaH", help="当前测试的类型")
    args = parser.parse_args()
    if args.show:
        showCurrentDev()
        sys.exit()
    run_json_file = args.file
    if os.path.isfile(run_json_file):
        otaInfo = load_json(run_json_file)
        otaRobot = crazyOTA(otaInfo, args)
        otaRobot.run()
    else:
        print("请输入正确的测试配置文件")
