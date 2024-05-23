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

pdu.initEngine()
pdu_device_ip = '10.3.37.30'
sys.stdout.flush()


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


# setLogUploadLevel(level=7)
#
# class timeCount(threading.Thread):


class serThead(threading.Thread):
    def __init__(self, deviceName, deviceInfo, output, config):
        super().__init__()
        self.devicesName = deviceName
        self.com = deviceInfo["com"]
        self.baudrate = deviceInfo["baudrate"]
        self.serial_data_type = deviceInfo["serial_data_type"]
        tempT = datetime.datetime.now()
        sjc = tempT.strftime("%Y-%m-%d_%H_%M_%S")
        self.logName = os.path.join(output.path, sjc + deviceInfo["logname"])
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
            # self.output.LOG_INFO(f"\t当前ota 已开始")
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
            self.output.LOG_INFO(f"\tOTA升级中，CSK正在解压文件。。。")
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
            self.logpath = os.path.join(f".\\result\\{sjc}")
            createdirs(self.logpath)
            self.output = output_log(1, self.logpath, sjc)
            self.deviceInfo = self.config.get("deviceInfo")
            self.deviceInfoWb01 = self.config.get("deviceInfoWb01")
            self.pduNum = self.config.get("pduNum")
            self.URL_list = list()
            self.countdown = self.config.get("countdown")
            for key in self.config.get("OTA_url"):
                self.URL_list.append(key)
            self.serFpThead = ""
        except:
            pass

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

    def power_onoroff(self, num, status):
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

    def run(self):
        try:
            if not self.initDevices():
                self.output.LOG_ERROR(f"退出当前测试")
            self.serFpThead.clearCurrentStatus()
            step = 0
            buildInfo = {
                0: 0,
                1: 0,
                2: 0,
                3: 0,
                4: 0,
                5: 0,
            }
            currentVersion = self.getCurrentVersionInfo()
            otaDoneVersion = currentVersion
            otaTimes = 0
            power_onoff_count = 0
            start_time = datetime.datetime.now()
            if self.power_onoroff(self.pduNum, True):
                self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-1***** 上电成功！")
            else:
                self.output.LOG_ERROR(f"*****otaTimes: {otaTimes} ## step-1***** 上电失败！")
            while True:
                try:
                    if self.countdown != 0:
                        time.sleep(1)
                        nowtime = datetime.datetime.now()
                        d_time = ((nowtime - start_time).total_seconds()) / 60
                        if int(d_time) != 0 and int((d_time) % self.countdown) == 0:
                            if power_onoff_count < 2:
                                self.output.LOG_INFO(f"当前已运行{d_time}分钟,开始上下电！\n")
                                if self.power_onoroff(self.pduNum, False):
                                    self.output.LOG_INFO(f"***** 每间隔{self.countdown}分钟，断电成功！")
                                    power_onoff_count += 1
                                else:
                                    self.output.LOG_ERROR(f"***** 每间隔{self.countdown}分钟，断电失败！")
                                    power_onoff_count -= 1
                                self.output.LOG_INFO(f"等待5s,让电控的余电释放完再上电")
                                time.sleep(5)  # 等待5s让电控的余电释放完再上电
                                if self.power_onoroff(self.pduNum, True):
                                    self.output.LOG_INFO(f"***** 每间隔{self.countdown}分钟，上电成功！")
                                    power_onoff_count += 1
                                else:
                                    self.output.LOG_ERROR(f"***** 每间隔{self.countdown}分钟，上电失败！")
                                    power_onoff_count -= 1
                        else:
                            # print(f"\n每间隔{self.countdown}分钟时间未到，还不能自动上下电！\n")
                            power_onoff_count = 0
                    buildInfo[step] = buildInfo[step] + 1
                    if step == 0:
                        step += 1
                        self.getCurrentVersionInfo()
                        continue
                        print(f"\r检查当前设备网络是否正常.执行时间{buildInfo[step]}s", end="")
                        if self.getDeviceNetConnected():
                            # 随机选择一个url下载链接
                            num = random.randint(0, len(self.URL_list) - 1)
                            otaDoneVersion = self.URL_list[num]
                            otaCmd = self.config.get("OTA_url")[otaDoneVersion]
                            self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-0***** 检查当前网络正常，10s后准备ota升级")
                            time.sleep(10)
                            self.output.LOG_INFO(f"当前版本 ：{currentVersion}")
                            self.output.LOG_INFO(f"发送的升级命令 ：{otaCmd}")
                            self.serFpThead.serWrite("\r")
                            self.serFpThead.serWrite("\r\n")
                            self.serFpThead.serWrite(otaCmd)
                            self.serFpThead.serWrite("\r")
                            self.serFpThead.serWrite("\r\n")
                            step += 1
                    elif step == 1:
                        print(f"\r检查当前OTA是否正在更新.执行时间{buildInfo[step]}s", end="")
                        if self.serFpThead.otaStart:
                            print("")
                            self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-1***** 检查到当前OTA文件正在下载")
                            self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-1***** 开始上下电")
                            if self.power_onoroff(self.pduNum, False):
                                self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-1***** 断电成功！")
                            else:
                                self.output.LOG_ERROR(f"*****otaTimes: {otaTimes} ## step-1***** 断电失败！")
                            self.output.LOG_INFO(f"等待5s,让电控的余电释放完再上电")
                            time.sleep(5)  # 等待5s让电控的余电释放完再上电
                            if self.power_onoroff(self.pduNum, True):
                                self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-1***** 上电成功！")
                            else:
                                self.output.LOG_ERROR(f"*****otaTimes: {otaTimes} ## step-1***** 上电失败！")
                            step += 1
                    elif step == 2:
                        print(f"\r检查当前OTA文件是否下载完成.执行时间{buildInfo[step]}s", end="")
                        if self.serFpThead.otaFileLoadDone:
                            print("")
                            self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-2***** 检查到当前OTA文件已下载完成")
                            if self.power_onoroff(self.pduNum, False):
                                self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-2***** 断电成功！")
                            else:
                                self.output.LOG_ERROR(f"*****otaTimes: {otaTimes} ## step-2***** 断电失败！")
                            self.output.LOG_INFO(f"等待5s,让电控的余电释放完再上电")
                            time.sleep(5)  # 等待5s让电控的余电释放完再上电
                            if self.power_onoroff(self.pduNum, True):
                                self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-2***** 上电成功！")
                            else:
                                self.output.LOG_ERROR(f"*****otaTimes: {otaTimes} ## step-2***** 上电失败！")
                            step += 1
                    elif step == 3:
                        print(f"\r检查当前OTA是否完成.执行时间{buildInfo[step]}s", end="")
                        if self.serFpThead.otaDone:
                            print("")
                            self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-3***** 检查当前OTA已完成")
                            step += 1
                    elif step == 4:
                        print(f"\r检查当前设备是否重启.执行时间{buildInfo[step]}s", end="")
                        if self.serFpThead.deviceReboot:
                            print("")
                            self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-4***** 检测到当前设备已重启,开始检查版本号")
                            if self.serFpThead.deviceReboot:
                                currentVersion = self.getCurrentVersionInfo()
                                if otaDoneVersion == currentVersion:
                                    otaTimes += 1
                                    step = 0
                                    self.serFpThead.clearCurrentStatus()
                                    buildInfo = {key: 0 for key in buildInfo}
                    elif step == 5:
                        print("")
                        self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-5***** 当前升级存在问题，准备断电重启设备重新升级")
                        self.serFpThead.clearCurrentStatus()
                        if self.power_onoroff(self.pduNum, False):
                            self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-5***** 断电成功！")
                        else:
                            self.output.LOG_ERROR(f"*****otaTimes: {otaTimes} ## step-5***** 断电失败！")
                        self.output.LOG_INFO(f"等待5s,让电控的余电释放完再上电")
                        time.sleep(5)  # 等待5s让电控的余电释放完再上电
                        if self.power_onoroff(self.pduNum, True):
                            self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-5***** 上电成功！")
                        else:
                            self.output.LOG_ERROR(f"*****otaTimes: {otaTimes} ## step-5***** 上电失败！")
                        while True:
                            if self.serFpThead.deviceReboot:
                                step = 0
                                break
                        currentVersion = self.getCurrentVersionInfo()
                        buildInfo = {key: 0 for key in buildInfo}
                        otaTimes += 1
                    tempCount = buildInfo[step]
                    if step == 2:
                        # if tempCount > 360:
                        if tempCount > 60:
                            self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-2 ***** 运行超时，进入步骤5")
                            step = 5
                    else:
                        if tempCount > 200:
                            self.output.LOG_INFO(f"*****otaTimes: {otaTimes} ## step-{step} ***** 运行超时，进入步骤5")
                            step = 5
                    time.sleep(1)
                except KeyboardInterrupt:
                    self.serFpThead.stop_flag = True
                    if self.serFpThead.serFp:
                        if self.serFpThead.serFp.isOpen():
                            self.output.LOG_INFO(f"关闭设备串口")
                            self.serFpThead.serFp.close()
                    break
                except Exception as e:
                    traceback.print_exc()
                    self.output.LOG_ERROR(f"*****otaTimes: {otaTimes} ## step-{step} ***** 运行异常，{str(e)}")
                    print(e)
                    break
        except KeyboardInterrupt:
            self.serFpThead.stop_flag = True
            if self.serFpThead.serFp:
                if self.serFpThead.serFp.isOpen():
                    self.output.LOG_INFO(f"关闭设备串口")
                    self.serFpThead.serFp.close()
            sys.exit()
        except Exception as e:
            traceback.print_exc()
            print(e)
        sys.exit()

    def rebootTest(self):
        runtimes = 0
        runTag = True
        rebootTag = False
        try:
            if not self.initDevices():
                self.output.LOG_ERROR(f"退出当前测试")
            self.serFpThead.clearCurrentStatus()
            self.serFpThead.serWrite('mai.setloglev 4')
            self.serFpThead.serWrite('flash.setloglev 4')
            self.serFpThead.serWrite('console 1')
            currentTime = 0
            while runTag:
                print(f'\r 正在检测 是否进入升级状态,已等待{round(currentTime, 2)} s', end="")
                if self.serFpThead.otaStart and self.serFpThead.otaDone:
                    self.serFpThead.otaStart = False
                    print('\n')
                    self.output.LOG_INFO(f"*****runtimes: {runtimes} ##  wb01 开始重启")
                    self.serFpThead.clearCurrentStatus()
                    self.serFpTheadWB01.serWrite('reboot')
                    times = 0
                    rebootTag = False
                    while times < 8:
                        if self.serFpThead.deviceReboot:
                            print("\n")
                            self.output.LOG_INFO(f"*****runtimes: {runtimes} ##  csk 重启成功")
                            rebootTag = True
                            break
                        if times == 5:
                            winsound.Beep(1000, 1000)
                        time.sleep(1)
                        print(f"\r当前测试 {runtimes} 次，等待csk重启 {times}s", end="")
                        times += 1
                    print("\n")
                    if not rebootTag:
                        self.output.LOG_INFO(f"*****runtimes: {runtimes} ##  重启失败")

                        winsound.Beep(1000, 100000000)
                        input("出现问题，请暂停")
                    self.serFpThead.serWrite('mai.setloglev 4')
                    self.serFpThead.serWrite('flash.setloglev 4')
                    self.serFpThead.serWrite('console 1')
                    self.serFpThead.clearCurrentStatus()
                    currentTime = 0
                    # self.output.LOG_INFO(f"*****runtimes: {runtimes} ##  等待 {sleepTime}s 重新进入wb01重启")
                    runtimes += 1
                time.sleep(0.1)
                currentTime += 0.1
        except Exception as e:
            print(e)
        except KeyboardInterrupt as e:
            runTag = False
            self.serFpThead.stop_flag = True
            self.serFpTheadWB01.stop_flag = True
            print("外部输入打断测试")

    def randomReboot(self):
        runtimes = 0
        runTag = True
        rebootTag = False
        if not self.initDevices():
            self.output.LOG_ERROR(f"退出当前测试")
        try:
            while runTag:
                if self.serFpThead.otaStart:
                    self.serFpThead.clearCurrentStatus()
                    sleepTimes = random.randint(10, 50)
                    self.output.LOG_INFO(f"*****runtimes: {runtimes} ##  当前休眠 {sleepTimes / 10}s 重新进入wb01重启")
                    time.sleep(sleepTimes / 10)
                    self.serFpTheadWB01.serWrite('reboot')
                    time.sleep(1)
                    times = 0
                    rebootTag = False
                    while times < 4:
                        if self.serFpThead.deviceReboot:
                            print("\n")
                            self.output.LOG_INFO(f"*****runtimes: {runtimes} ##  csk 重启成功")
                            rebootTag = True
                            break
                        if times == 2:
                            winsound.Beep(1000, 1000)
                        time.sleep(1)
                        print(f"\r当前测试 {runtimes} 次，等待csk重启 {times}s", end="")
                        times += 1
                    if not rebootTag:
                        self.output.LOG_INFO(f"*****runtimes: {runtimes} ##  重启失败")

                        winsound.Beep(1000, 100000000)
                        input("出现问题，请暂停")
                    runtimes += 1
                time.sleep(0.1)
        except:
            pass

    def wb01Reboot(self):
        runtimes = 0
        if not self.initDevices():
            self.output.LOG_ERROR(f"退出当前测试")
        try:
            sleepTime = 0
            self.serFpTheadWB01.serWrite('reboot')
            while True:
                sleepTime = random.randint(180, 320)
                self.output.LOG_INFO(f"*****runtimes: {runtimes} ##  休眠 {sleepTime} s后重启")
                time.sleep(sleepTime)
                self.serFpThead.clearCurrentStatus()
                self.serFpTheadWB01.serWrite('reboot')
                times = 0

                rebootTag = False
                while times < 4:
                    if self.serFpThead.deviceReboot:
                        print("\n")
                        self.output.LOG_INFO(f"*****runtimes: {runtimes} ##  csk 重启成功")
                        rebootTag = True
                        break
                    time.sleep(1)
                    print(f"\r当前测试 {runtimes} 次，等待csk重启 {times}s", end="")
                    times += 1
                if not rebootTag:
                    self.output.LOG_INFO(f"*****runtimes: {runtimes} ##  重启失败")
                print("end")
                runtimes += 1
        except KeyboardInterrupt as e:
            self.serFpThead.stop_flag = True
            self.serFpTheadWB01.stop_flag = True
        except Exception as e:
            print(e)

    def randomPowerOff(self, pduNum, randomLimit=360, pduSwitchTime=10):
        while True:
            sleepTime = random.randint(10, randomLimit)
            self.output.LOG_INFO(f"pdu : {pduNum}号， 休眠{sleepTime}s,后开始断电")
            time.sleep(sleepTime)
            self.power_onoroff(pduNum, False)
            time.sleep(pduSwitchTime)
            self.power_onoroff(pduNum, True)

    def otaLoop(self):
        runtimes = 0
        if not self.initDevices():
            self.output.LOG_ERROR(f"退出当前测试")
        try:
            sleepTime = 0
            self.serFpTheadWB01.serWrite('reboot')
            self.serFpThead.serWrite('flash.setloglev 4')
            self.serFpThead.serWrite('console 1')

            # otaCmd2High = "ota.set.url https://listenai-test-internal.oss-accelerate.aliyuncs.com/NAS_Sync/OTA/dmgj/V1.0.35.bin@186FCC41B229991938E5ED2CA3282978@0"
            # otaCmd2High = "ota.set.url http://listenai-firmware-delivery.oss-cn-beijing.aliyuncs.com/OTA/Midea_OTA_V1.0.37_20240401100725.bin@F939B55A328D552F574492646ED099D7@0"
            # otaCmd2Low = "ota.set.url http://listenai-firmware-delivery.oss-cn-beijing.aliyuncs.com/OTA/Midea_OTA_V1.0.36.bin@B65D32153799AC4017C845986681C1AD@0"
            # otaCmd2Low = "ota.set.url http://listenai-test-internal.oss-cn-beijing.aliyuncs.com/NAS_Sync/OTA/dmgj/V1.0.34.bin@11F2EDB9CE2ADA7AB25EE17C5E5B60AC@0"
            # otacmd = "ota.set.url https://listenai-test-internal.oss-accelerate.aliyuncs.com/NAS_Sync/OTA/dmgj/Midea_OTA_20240327180452.bin@6356A78BF9A6B4FDBD41F10B01AB4586@0"
            # otacmd = "ota.set.url http://listenai-firmware-delivery.oss-cn-beijing.aliyuncs.com/Midea-CSK/Midea_V1.0.36_20240327142653.bin@E54923F223CCD3524AFAC8A7167C3477@0"
            self.serFpTheadWB01.serWrite('reboot')
            start_time = datetime.datetime.now()
            # 升级超时时间，超过时间则重启再输入ota命令
            timeOutMin = 15

            # if self.power_onoroff(self.pduNum, True):
            #     self.output.LOG_INFO(f"上电成功！")
            # else:
            #     self.output.LOG_ERROR(f"上电失败！")
            #     return
            # wifi pdu num : 3
            wifiThread = threading.Thread(target=self.randomPowerOff, args=(3, 360, 2))
            wifiThread.start()
            # device pdu num : 7
            deviceThread = threading.Thread(target=self.randomPowerOff, args=(7, 3600, 10))
            deviceThread.start()
            while True:
                nowtime = datetime.datetime.now()
                tempSecond = (nowtime - start_time).total_seconds()
                print(f"\r距离上一次重启时间为{round(tempSecond, 1)}s", end="")
                # d_time = tempSecond / 60
                # if d_time > timeOutMin:
                #     print('\n')
                #     self.output.LOG_INFO(f"*****重启{runtimes}次时，当前升级超过{timeOutMin}分钟未升级完成，重启软启动设备***")
                #     self.serFpTheadWB01.serWrite('reboot')
                #     time.sleep(2)
                #     print('\n')
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
                if self.serFpThead.on_unzip:
                    random_char = generate_random_char()
                    self.output.LOG_INFO(f"*****给csk输入随机字符:{random_char}")
                    self.serFpThead.serWrite(f'{random_char}')
                    s_time = Random_time("[1-4]")
                    self.output.LOG_INFO(f"*****等待随机时间:{s_time}s")
                    time.sleep(s_time)
                # if self.serFpThead.deviceNetConnected:
                #     currentVersion = self.getCurrentVersionInfo()
                #     self.output.LOG_INFO(f"当前设备版本信息：{currentVersion}")
                #     print('\n')
                #    # if currentVersion == "010036":
                #     print('\n')
                #     self.output.LOG_INFO(f"*****开始升级*1.0.37*{otaCmd2High}***")
                #     self.serFpThead.serWrite("\r")
                #     self.serFpThead.serWrite("\r\n")
                #     self.serFpThead.serWrite(otaCmd2High)
                #     self.serFpThead.serWrite("\r")
                #     self.serFpThead.serWrite("\r\n")
                # elif currentVersion == "010037":
                #     print('\n')
                #     self.output.LOG_INFO(f"*****开始升级*1.0.36*{otaCmd2Low}***")
                #     self.serFpThead.serWrite("\r")
                #     self.serFpThead.serWrite("\r\n")
                #     self.serFpThead.serWrite(otaCmd2Low)
                #     self.serFpThead.serWrite("\r")
                #     self.serFpThead.serWrite("\r\n")
                # else:
                #    self.output.LOG_INFO(f"当前版本信息非正常，请检查！")
                # self.serFpThead.get_ota_url("loop 0")
                # time.sleep(2)
                # if self.serFpThead.ota_url_OK:
                #     self.serFpThead.ota_url_OK = False
                #     self.serFpThead.get_ota_url("")
                #     self.serFpThead.clearCurrentStatus()
                # else:
                #     self.output.LOG_INFO(f"*****发送OTA升级命令失败，将再次重试！***")
                time.sleep(1)

        except KeyboardInterrupt as e:
            self.serFpThead.stop_flag = True
            self.serFpTheadWB01.stop_flag = True
        except Exception as e:
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
            self.serFpThead.stop_flag = True
            self.serFpTheadWB01.stop_flag = True
        except Exception as e:
            print(e)


if __name__ == '__main__':
    run_json_file = "run.json"
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
