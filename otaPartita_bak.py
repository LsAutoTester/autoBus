import argparse
import datetime
import inspect
import json
import os
import re
import subprocess
import sys
import threading
import time
import traceback
import random
import winsound

import requests
import serial
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


def setLogUploadLevel(deviceId=210006727464378, level=3):
    url = 'https://uat.aimidea.cn:11003/v1/base2pro/data/transmit'
    args = {"deviceId": deviceId, "logLevel": level, "status": "1"}
    dataStr = json.dumps(args, ensure_ascii=False)
    data = {
        'serviceUrl': '/v1/device/log/set',
        'data': dataStr
    }
    response = requests.post(url, data=data)
    return checkPostResponse(response)


def setWakeupUpFilelaod(deviceId=210006727464378):
    url = 'https://uat.aimidea.cn:11003/v1/base2pro/data/transmit'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    # args = {"deviceId":210006727464378,"mid":"54aabf504-6d4d-4814","wakeAudioUploadSwitch":1 }
    args = {"deviceId": deviceId, "mid": "54aabf504-6d4d-4814", "wakeAudioUploadSwitch": 1}
    dataStr = json.dumps(args, ensure_ascii=False)
    data = {
        'serviceUrl': '/v1/device/wakeAudioUploadSwitch/set',
        'data': dataStr
    }

    response = requests.post(url, data=data)
    return checkPostResponse(response)


def checkPostResponse(response):
    print(f"\n\n响应信息 {response.text}\n")
    # print(response.status_code)
    if response.status_code == 200:
        tempInfo = json.loads(response.text)
        result = tempInfo.get('result', {})
        returnData = result.get('returnData', {})
        msg = returnData.get('msg', {})
        code = returnData.get('code', {})
        if msg == "success" and int(code) == 200:
            print("设置成功")
            return True
    return False


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


class serThead(threading.Thread):
    def __init__(self, deviceName, deviceInfo, output, config):
        super().__init__()
        self.devicesName = deviceName
        self.com = deviceInfo["com"]
        self.baudrate = deviceInfo["baudrate"]
        self.serial_data_type = deviceInfo["serial_data_type"]
        tempT = datetime.datetime.now()
        sjc = tempT.strftime("%Y-%m-%d_%H_%M_%S")
        # self.logName = os.path.join(output.path, sjc + deviceInfo["logname"])
        self.logName = os.path.join(output.path, deviceInfo["logname"])
        self.output = output
        self.serFp = ''
        self.stop_flag = False
        self.tempMsg = []
        self.regexTagConfig = config

        self.otaStart = False
        self.otaFileLoadDone = False
        self.otaDone = False
        self.deviceNetConnected = False
        self.deviceReboot = False
        self.cmdToolLong = False
        self.versionInfo = ""
        self.ota_url = ""
        self.ota_url_OK = False
        self.wakeup = ""
        self.yichang = False
        self.OTA_net_fail = False
        self.OTA_download_fail = False
        self.on_unzip = False

    def clearCurrentStatus(self):
        self.otaStart = False
        self.otaFileLoadDone = False
        self.otaDone = False
        self.deviceNetConnected = False
        self.deviceReboot = False
        self.cmdToolLong = False
        self.versionInfo = ""
        self.ota_url = ""
        self.ota_url_OK = False
        self.wakeup = ""
        self.yichang = False
        self.OTA_net_fail = False
        self.OTA_download_fail = False
        self.on_unzip = False

    def regexMatch(self, log_info):
        pattern = r"AP Version: .*.(\d{2}\.\d{2}\.\d{2}?)"
        result = re.search(pattern, log_info)
        wakeupkeyword = re.search(r".*wakeup_callback, keyword:(.*)", log_info)
        # if "OTA download progress 89%" in log_info:
        #     self.otaStart = True
        if wakeupkeyword:
            self.wakeup = wakeupkeyword.group(1)
            self.output.LOG_INFO(f"\t唤醒信息为：{self.wakeup}")
        if result:
            self.versionInfo = result.group(1)
            self.output.LOG_INFO(f"\t当前版本信息为：{self.versionInfo}")
        if self.regexTagConfig.get("otsStart") in log_info:
            self.otaStart = True
            self.output.LOG_INFO(f"\t当前ota 已开始")
        if self.regexTagConfig.get("otaFileLoadDone") in log_info:
            self.otaFileLoadDone = True
            self.output.LOG_INFO(f"\t当前ota文件已下载完成")
        if self.regexTagConfig.get("otaDone") in log_info:
            self.otaDone = True
            self.output.LOG_INFO(f"\t当前ota已完成")
        if self.regexTagConfig.get("rebootTag") in log_info:
            self.deviceReboot = True
            self.output.LOG_INFO(f" \t当前设备已重启")
        if self.regexTagConfig.get("netConnectTag") in log_info:
            self.deviceNetConnected = True
            self.output.LOG_INFO(f" \t当前设备网络已连接")
        if "[HTTPC][ERR]Get: Send Request failed.." in log_info:
            self.OTA_net_fail = True
        if "ota_downloader] HTTPC_read failed" in log_info:
            self.OTA_download_fail = True
        if self.ota_url:
            if self.ota_url in log_info:
                self.ota_url_OK = True
        if "wait algo suspend result timeout" in log_info:
            self.output.LOG_INFO(f" \t出现异常日志：{log_info}")
            self.yichang = True
        if "listen_client_rollback_csk" in log_info:
            self.output.LOG_INFO(f"\tCSK进入兜底了。。。")
        if "reset csk boot & reset pin" in log_info:
            self.output.LOG_INFO(f"\tWB01开始拉csk的引脚进行重启。。。")
        if "ota exp ota_count:" in log_info:
            self.output.LOG_INFO(f"\tOTA包下载完成，检测心跳兜底倒计数开始。。。{log_info}")
        if "match file(ota/respak.bin)" in log_info:
            self.output.eeeeeeeeeeeeeeeee(f"\tOTA升级中，CSK正在解压文件。。。")
            self.on_unzip = True

    def get_ota_url(self, ota_url):
        self.ota_url = ota_url

    def getRegexResult(self):
        return self.regexResult

    def cleanRegexResultBuff(self):
        self.regexResult.clear()

    def serActive(self):
        self.serFp = get_serial(self.com, self.baudrate)
        if self.serFp:
            self.serFp.write(f"version\n".encode('utf-8'))
            return self.serFp.isOpen()
        else:
            self.output.LOG_ERROR(f"串口{self.com}无法连接！")
            return False
        # if not self.serFp.isOpen():
        #     raise EOFError("设备初始化失败")
        # return self.serFp.isOpen()

    def getSerMsg(self):
        return self.tempMsg

    def cleanMsgBuff(self):
        self.tempMsg.clear()

    def serWrite(self, cmd):
        if len(cmd) > 3:
            self.output.LOG_INFO(f"当前执行shell 命令: {str(cmd)}")
        if self.serFp:
            if self.serFp.isOpen():
                self.serFp.write(f"{cmd}\n".encode('utf-8'))

    # def __del__(self):
    #     if self.serFp:
    #         if self.serFp.isOpen():
    #             self.serFp.close()

    def run(self):
        str_info = ""
        buffer = ""
        if self.serial_data_type == "hex":
            logfile = open(self.logName, "w")
        else:
            logfile = open(self.logName, "wb")
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
                                self.regexMatch(self.devicesName, buffer)
                                buffer = ""
                    except Exception as e:
                        if "拒绝访问" in str(e):
                            errorinfo = f"串口连接出现问题，请检查{self.com}串口是否掉线！！！\n"
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
                        if "拒绝访问" in str(e):
                            errorinfo = f"串口连接出现问题，请检查{self.com}串口是否掉线！！！\n"
                            self.stop_flag = True
                        else:
                            errorinfo = "Error info : %s, Current line : %s\n" % (e, str_info)
                        self.output.LOG_ERROR(f"{errorinfo}")
                    finally:
                        continue
            logfile.close()
        else:
            logfile.close()
            self.output.LOG_ERROR(f"{self.com}串口连接出错，请重试！！")
            self.stop_flag = True


class autoOTA():
    def __init__(self, runjson):
        super().__init__()
        try:
            self.config = load_json(runjson)
            tempT = datetime.datetime.now()
            sjc = tempT.strftime("%Y-%m-%d_%H_%M_%S")
            self.logpath = os.path.join(os.getcwd(), 'result', sjc)
            createdirs(self.logpath)
            self.output = output_log(1, self.logpath, sjc)
            self.deviceInfo = self.config.get("deviceInfo", {})
            self.cskBootPinMask = self.deviceInfo.get("pinNum", 8)
            self.cskBurnPort = self.deviceInfo.get("burnPort", '')
            self.deviceInfoWb01 = self.config.get("deviceInfoWb01")
            self.serPinMask = self.deviceInfoWb01.get("pinNum", 0)
            self.md5Info = self.config.get("md5Info")
            self.pduNum = self.config.get("pduNum")
            self.usb2xxxDevNum = self.config.get("usb2xxNum", "")
            self.cskBurnFile = self.config.get("cskBurnFile", "")
            self.asrBurnFile = self.config.get("asrBurnFile", "")
            self.toolsFolder = os.path.join(os.getcwd(), 'tools')
            self.isNotBurnDone = True
            self.URL_list = list()
            self.countdown = self.config.get("countdown")
            for key in self.config.get("OTA_url"):
                self.URL_list.append(key)
            self.serFpThead = ""
        except:
            pass

    def usb2xxxInit(self):
        # # wb01 的ser 脚。默认低电平，拉高进烧录
        # wb01SelPinNum = 0
        # # csk 的boot脚。默认高电平，拉低进烧录
        # cskBootPinNum = 8
        ret = USB_OpenDevice(self.usb2xxxDevNum)
        if not ret:
            self.output.LOG_ERROR(f"usb2xxx {self.usb2xxxDevNum} 设备打开失败，请检查 ")
            return False
        # 设置P0-P15引脚为输出模式，可以通过调用GPIO_Write函数将指定引脚设置为高电平或者低电平。
        GPIO_SetOutput(self.usb2xxxDevNum, 0xFFFF, 0)
        # 设置指定引脚为低电平P0-P7为低电平，P8-P15为高电平
        setP0_7LP8_15H(self.usb2xxxDevNum)
        serPinValue = checkPinMaskLevel(self.usb2xxxDevNum, self.serPinMask)
        self.output.LOG_INFO(f"初始化asr引脚P{self.serPinMask}，默认值为：{serPinValue}")
        cskPinValue = checkPinMaskLevel(self.usb2xxxDevNum, self.cskBootPinMask)
        self.output.LOG_INFO(f"初始化csk引脚P{self.cskBootPinMask}，默认值为：{cskPinValue}")
        return True

    def initDevices(self):
        try:
            self.serFpThead = serThead("AP日志", self.deviceInfo, self.output, self.config)
            self.serFpThead.start()
            time.sleep(2)
            if self.serFpThead.serFp.isOpen():
                print("csk 正常")
            self.serFpTheadWB01 = serThead("WB01日志", self.deviceInfoWb01, self.output, self.config)
            self.serFpTheadWB01.start()
            time.sleep(2)
            if self.serFpTheadWB01.serFp.isOpen():
                print("wb01 正常")
        except Exception as e:
            self.output.LOG_ERROR(f"设备初始化失败{str(e)}")
            return False
        return True

    def closeSer(self):
        self.serFpThead.stop_flag = True
        self.serFpTheadWB01.stop_flag = True
        if self.serFpThead.serFp.isOpen():
            self.serFpThead.serFp.close()
        if self.serFpTheadWB01.serFp.isOpen():
            self.serFpTheadWB01.serFp.close()

    def getCurrentVersionInfo(self):
        self.serFpThead.serWrite(self.config.get("versionCMD", " "))
        time.sleep(1)
        tempVersion = self.serFpThead.versionInfo.replace(".", "")
        if not tempVersion or tempVersion is None:
            time.sleep(1)
            self.getCurrentVersionInfo()
        else:
            return tempVersion

    def play_wakeup(self):
        self.serFpThead.wakeup = ""
        while True:
            self.output.LOG_INFO(f"\t开始播放唤醒音频文件")
            subprocess.call(["start", "小美小美.wav"], shell=True)
            time.sleep(2)
            if self.serFpThead.wakeup:
                self.serFpThead.yichang = False
                self.serFpThead.wakeup = ""
                break

    def getDeviceNetConnected(self):
        deviceId = self.config.get("deviceNum")
        if setLogUploadLevel(deviceId=deviceId, level=7):
            self.output.LOG_INFO(f" 当前设备已联网")
            return True
        self.output.LOG_WARNING(f" 当前设备未联网，请测试人员检查wifi是否正常,休眠10s")
        time.sleep(10)
        return False

    def deviceReboot(self):
        # self.serFpThead.serWrite(self.config.get("rebootCMD", " "))
        # time.sleep(5)
        if self.serFpThead.deviceReboot:
            return True

    def power_onoroff(self, num, status, pdu_device_ip):
        """
        num:第几个插头的序号
        status:True为开启，False为关闭
        """
        try:
            if pdu.check_netconnect(pdu_device_ip):
                pdu.TurnOnOff(pdu_device_ip, num, status)
                while True:
                    GetStatus = pdu.GetStatus(pdu_device_ip, num)
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
                self.output.LOG_ERROR(f"IP地址：{pdu_device_ip}无法访问！！")
                return False
        except Exception as e:
            self.output.LOG_ERROR(f"继电器第{num}个插座上下电出错了，出错信息{e}")
            return False

    def randomPowerOff(self, pduNum, randomLimit=360, pduSwitchTime=10):
        while True:
            sleepTime = random.randint(10, randomLimit)
            self.output.LOG_INFO(f"pdu : {pduNum}号， 休眠{sleepTime}s,后开始断电")
            time.sleep(sleepTime)
            self.power_onoroff(pduNum, False)
            time.sleep(pduSwitchTime)
            self.power_onoroff(pduNum, True)

    def inBoot(self):
        isBoot = False
        self.output.LOG_INFO(f"进入boot模式")
        GPIO_SetOutput(self.usb2xxxDevNum, 0xFFFF, 0)
        # 设置指定引脚为低电平P0-P7为低电平，P8-P15为高电平
        setP0_7LP8_15H(self.usb2xxxDevNum)
        time.sleep(0.1)
        # 设置boot和ser进入烧录模式
        cskBoot = setPinLevel(self.usb2xxxDevNum, self.cskBootPinMask, 0)
        self.output.LOG_INFO(f"拉低csk P{self.cskBootPinMask}脚 进入boot: {cskBoot}")
        time.sleep(0.1)
        asrBoot = setPinLevel(self.usb2xxxDevNum, self.serPinMask, 1)
        self.output.LOG_INFO(f"拉高asr P{self.serPinMask}脚 进入boot: {asrBoot}")
        if cskBoot and asrBoot:
            return True
        else:
            return False

    def outBoot(self):
        self.output.LOG_INFO(f"退出boot模式")
        setPinLevel(self.usb2xxxDevNum, self.cskBootPinMask, 1)
        time.sleep(0.1)
        setPinLevel(self.usb2xxxDevNum, self.serPinMask, 0)
        time.sleep(0.1)
        setP0_7LP8_15H(self.usb2xxxDevNum)

    def usb2xxReset(self):
        self.output.LOG_INFO(f"重新复位usb2xxx")
        self.outBoot()
        self.usb2xxClose()
        self.usb2xxxInit()

    def usb2xxClose(self):
        self.output.LOG_INFO(f"关闭usb2xxx")
        closeDev(self.usb2xxxDevNum)

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
        self.output.LOG_INFO(f"shell 命令执行输出： {str(stdout_str)}")
        self.output.LOG_INFO(f"shell 命令执行异常： {str(stderr_str)}")
        if tag in stdout_str:
            self.output.LOG_INFO(f"\t\t**********{purpose} 成功**********")
            return True
        else:
            self.output.LOG_ERROR(f"\t\t**********{purpose} 失败**********")
            return False

    def asrBurn(self):
        asrBurnTools = os.path.join(self.toolsFolder, "wb01Burn.exe")
        dlTag = 'welcome to download'
        burnTag = 'burn ok'
        verifyTag = 'crc done'
        asrBurnPort = self.deviceInfoWb01.get("com", "")
        asrBurnCmd_dl = asrBootCmdGet("dl", asrBurnTools, asrBurnPort, self.asrBurnFile)
        self.output.LOG_INFO(f"开始asr 的固件{self.asrBurnFile}烧录。")
        if not self.shell(asrBurnCmd_dl, dlTag, 'asr 串口检查  ', timeOut=120):
            return
        asrBurnCmd_burn = asrBootCmdGet("burn", asrBurnTools, asrBurnPort, self.asrBurnFile)
        if not self.shell(asrBurnCmd_burn, burnTag, 'asr 全量烧录 burn ', timeOut=120):
            return
        asrBurnCmd_verify = asrBootCmdGet("verify", asrBurnTools, asrBurnPort, self.asrBurnFile)
        if not self.shell(asrBurnCmd_verify, verifyTag, 'asr 全量烧录 verify ', timeOut=120):
            return
        self.output.LOG_INFO(f"asr 烧录成功")
        self.isNotBurnDone = False

    def cskBurn(self):
        cskBurnTools = os.path.join(self.toolsFolder, "Uart_Burn_Tool.exe")
        tag = 'FLASH DOWNLOAD SUCCESS'
        purpose = 'csk 全量烧录 '
        cskBurnCmd = cskBootCmdGet("all", cskBurnTools, self.cskBurnPort, self.cskBurnFile, baudRate=BAUD_RATE)
        if not self.shell(cskBurnCmd, tag, purpose, timeOut=180):
            return
        self.isNotBurnDone = False
        self.output.LOG_INFO(f"csk 烧录成功")

    def burnFile(self, burnType="all"):
        self.closeSer()
        self.isNotBurnDone = True
        if not self.inBoot():
            # 退出烧录模式
            self.usb2xxReset()
            # pdu重启设备
            self.rebootDevice()
            return
        self.rebootDevice()
        if burnType == "csk":
            self.cskBurn()
        elif burnType == "asr":
            self.asrBurn()
        else:
            self.asrBurn()
            self.cskBurn()
        if self.isNotBurnDone:
            self.output.LOG_ERROR(f"当前烧录失败")
        self.outBoot()
        self.rebootDevice()
        time.sleep(5)
        self.initDevices()
        self.logLevelSet()

    def verifyMd5(self, vType):
        tempMd5Info = self.md5Info.get(vType, {})
        size = tempMd5Info.get("size", 0)
        startAddr = tempMd5Info.get("startAddr", 0x00)
        md5Value = tempMd5Info.get("md5Base", 0)
        cskBurnFilePath = os.path.join(self.toolsFolder, "cskburn.exe")
        cmd = f"{cskBurnFilePath} -C 6 -s {self.cskBurnPort} --verify {startAddr}:{size}"
        return self.shell(cmd, md5Value, f"{vType} 校验 md5 ")

    def rebootDevice(self, waitTime=10):
        self.output.LOG_INFO(f"开始给设备上硬重启，间隔{waitTime}s")
        self.power_onoroff(self.pduNum, False)
        time.sleep(waitTime)
        self.power_onoroff(self.pduNum, True)
        self.output.LOG_INFO(f"设备硬重启完成")

    def checkMd5(self):
        # 设置引脚进入烧录模式
        self.output.LOG_INFO(f"开始检查md5值")
        if not self.inBoot():
            # 退出烧录模式
            self.usb2xxReset()
            # pdu重启设备
            self.rebootDevice()
            return False
        # pdu重启设备
        self.rebootDevice()
        time.sleep(2)
        # 获取ap md5
        apMd5 = self.verifyMd5('ap')
        # pdu重启设备

        self.rebootDevice()
        time.sleep(2)
        # 获取cp md5
        cpMd5 = self.verifyMd5('cp')

        # pdu重启设备
        self.rebootDevice()
        time.sleep(2)
        # 获取tone md5
        toneMd5 = self.verifyMd5('tone')
        if apMd5 == cpMd5 == toneMd5 == True:
            # 退出烧录模式
            self.outBoot()
            # pdu重启设备
            self.rebootDevice()
            time.sleep(2)
            return
        self.output.LOG_ERROR(f"md5校验失败")
        input("当前md5校验失败，等待测试人员处理！！！")

    def logLevelSet(self, level=4):
        self.serFpThead.serWrite(f'flash.setloglev {level}')
        self.serFpThead.serWrite('console 1')

    def otaLoop(self):
        runtimes = 0
        self.usb2xxxInit()
        if not self.initDevices() or not self.usb2xxxInit():
            self.output.LOG_ERROR(f"退出当前测试")
        try:
            sleepTime = 0
            self.serFpTheadWB01.serWrite('reboot')
            self.logLevelSet()
            start_time = datetime.datetime.now()
            # 升级超时时间，超过时间则重启再输入ota命令
            timeOutMin = 15

            while True:
                nowtime = datetime.datetime.now()
                tempSecond = (nowtime - start_time).total_seconds()
                print(f"\r距离上一次重启时间为{round(tempSecond, 1)}s", end="")
                if self.serFpThead.OTA_net_fail:
                    print('\n')
                    self.output.LOG_INFO(f"检测到[HTTPC][ERR]Get: Send Request failed..,重启一下wb01..")
                    self.serFpTheadWB01.serWrite('reboot')
                    self.serFpThead.clearCurrentStatus()
                    time.sleep(2)
                if self.serFpThead.OTA_download_fail:
                    print('\n')
                    self.output.LOG_INFO(f"检测到ota_downloader] HTTPC_read failed,重启一下wb01..")
                    self.serFpTheadWB01.serWrite('reboot')
                    self.serFpThead.clearCurrentStatus()
                    time.sleep(2)
                if self.serFpThead.deviceReboot:
                    runtimes += 1
                    start_time = datetime.datetime.now()
                    self.output.LOG_INFO(f"*****重启{runtimes}次***")
                    self.serFpThead.serWrite('\n')
                    self.serFpThead.clearCurrentStatus()
                    print('\n')
                # if self.serFpThead.yichang:
                #     # self.serFpThead.serWrite('version')
                #     self.play_wakeup()
                if self.serFpThead.otaDone:
                    time.sleep(2)
                    self.checkMd5()
                    self.serFpThead.clearCurrentStatus()

                # 如果需要烧录
                # if needBurn:
                #     self.burnFile()
                time.sleep(1)

        except KeyboardInterrupt as e:
            self.closeSer()
        except Exception as e:
            self.closeSer()
            print(e)

    def auto_burn_OTA(self):
        runtimes = 0
        if not self.initDevices():
            self.output.LOG_ERROR(f"退出当前测试")
        try:
            sleepTime = 0
            self.serFpTheadWB01.serWrite('reboot')
            start_time = datetime.datetime.now()
        except KeyboardInterrupt as e:
            self.closeSer()
        except Exception as e:
            print(e)


if __name__ == '__main__':
    # parser = argparse.ArgumentParser(description="获取外部参数库args")
    # parser.add_argument('-s', "--devInfo", type=str, default="", help="测试文件路径")
    # args = parser.parse_args()
    if len(sys.argv) > 1:
        for i in range(1, len(sys.argv)):
            if "usb2xx" in i:
                showCurrentDev()
                sys.exit()
            print("第{}个参数是：{}".format(i, sys.argv[i]))
    else:
        print("没有提供参数")

    run_json_file = "otaTest.json"
    if os.path.isfile(run_json_file):
        e = autoOTA(run_json_file)
        # e.run()
        e.otaLoop()
    else:
        print(f"{run_json_file}路径不存在！")

# robot = actionMain()
# robot()
# info = "773325][2024-03-07 15:34:24.760][I][evs_event # algo] set wake threshold, [MID_HIGH 75]"
# regex = ".*set wake threshold, (.*)"
# ke = re.match(regex,info)
# if ke:
#     print(ke.group(1))
