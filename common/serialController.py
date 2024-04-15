import os
import datetime
import re
import time
import threading
from common.Common_Func import get_serial,pinyin_to_hanzi,Num_to_hanzi,check_netconnect
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

class seriallog(threading.Thread):
    def __init__(self,name,port,baudrate,logfile,path,playType,wxwork_appid,wx):
        threading.Thread.__init__(self,daemon=True)
        #Process.__init__(self)
        self.name = name
        self.playType = playType
        self.port = port
        self.baudrate = baudrate
        self.log_file = logfile
        self.logstr = ''
        self.serial = get_serial(port,baudrate,time_out=0.5)
        self.is_running = False
        self.error_log = os.path.join(path,"error.log")
        self.kw_dict = dict()
        self.output = ""
        self.pinyinjson = ""
        self.numjosn = ""
        self.wxwork_appid = wxwork_appid
        self.wx = wx
        self.errorfile = open(self.error_log, "a")
        self.file = open(self.log_file, "wb")
        self.too_big_count = 0


    def mark_start(self):
        self.is_running = True

    def mark_stop(self):
        self.is_running = False
        self.log_clear()


    def getseial(self):
        return self.serial

    def read_lines(self):
        buffer = b""
        sep = b"\n"
        while self.is_running and self.serial.isOpen():
            buffer += self.serial.read(self.serial.inWaiting())
            while sep in buffer:
                line, _, buffer = buffer.partition(sep)
                yield line

    def check_yichang(self,logtime,info):
        print(f"{info}")
        self.errorfile.write(f"{info}\n")
        self.errorfile.flush()
        os.fsync(self.errorfile.fileno())
        if check_netconnect():
            if self.wxwork_appid:
                self.wx.send_text_to_wxwork(
                    f"""[异常]\n{info}请及时查看！""")
        else:
            print(f"{logtime}电脑网络连接异常，发送告警到企业微信失败！\n")
            self.errorfile.write(f"{logtime}电脑网络连接异常，发送告警到企业微信失败！\n")
            self.errorfile.flush()
            os.fsync(self.errorfile.fileno())

    def check_zhengchang(self, logtime, info):
        print(f"{info}")
        self.errorfile.write(f"{info}\n")
        self.errorfile.flush()
        os.fsync(self.errorfile.fileno())
        if check_netconnect():
            if self.wxwork_appid:
                self.wx.send_text_to_wxwork(
                    f"""[正常]\n{info}""")
        else:
            print(f"{logtime}电脑网络连接异常，发送告警到企业微信失败！\n")
            self.errorfile.write(f"{logtime}电脑网络连接异常，发送告警到企业微信失败！\n")
            self.errorfile.flush()
            os.fsync(self.errorfile.fileno())

    def write_to_file(self,lognowtime,line):
        if line:
            linelog = bytes(str(lognowtime), encoding='utf-8') + line + bytes("\n", encoding='utf-8')
            log_str = line.decode('utf8', 'ignore')  # 日志内存在不兼容的字符编码，加上ignore忽略异常
            log_str = ILLEGAL_CHARACTERS_RE.sub('', log_str)  # 去掉非法字符
            log_str = ''.join(log_str.split("[0m"))
            if "电源键已松开,真正开机,启动所有按键事件检测" in log_str:
                self.output.LOG_INFO(f"{lognowtime},测试设备已开机！")
            self.logstr += log_str + "\n"
            self.file.write(linelog)
            self.file.flush()
            os.fsync(self.file.fileno())
            if self.name == "测试串口" and os.path.getsize(self.log_file) > 1024*1024*100:
                self.file.close()
                self.too_big_count += 1
                self.log_file = self.log_file.split("&")[0] + f"&{self.too_big_count}"
                self.file = open(self.log_file, "wb")


    def write_log(self,lognowtime,line):
        buffer = line
        while True:
            if b'\n' in buffer or b'\r' in buffer:
                index_1 = buffer.find(b'\n')
                index_2 = buffer.find(b'\r')
                #print(index_1, index_2)
                if index_1 == -1:
                    line, _, buffer = buffer.partition(b'\r')
                    self.write_to_file(lognowtime,line)
                    #print(lognowtime,line)
                elif index_2 == -1:
                    line, _, buffer = buffer.partition(b'\n')
                    self.write_to_file(lognowtime,line)
                    #print(line, buffer)
                elif index_1 < index_2:
                    line, _, buffer = buffer.partition(b'\n')
                    self.write_to_file(lognowtime,line)
                    #print(line, buffer)
                elif index_1 > index_2:
                    line, _, buffer = buffer.partition(b'\r')
                    self.write_to_file(lognowtime,line)
                    #print(line, buffer)
            else:
                break
        return buffer

    def write(self,info):
        if self.serial:
            if self.serial.isOpen():
                self.serial.write(f"{info}\n".encode("utf-8"))
            else:
                print(f"串口已关闭，无法发送数据！")
        else:
            print("串口加载出错，无法发送数据！")

    def run(self):
        buffer = b''
        while self.is_running and self.serial:
            while self.is_running and self.serial.isOpen():
                try:
                    line = self.serial.read(self.serial.inWaiting())
                    if line:
                        nowtime = datetime.datetime.now()
                        lognowtime = "[" + str(nowtime) + "]"
                        buffer += line
                        buffer = self.write_log(lognowtime,buffer)
                except Exception as e:
                    print(f"{self.name}串口进程出错，出错信息{e}\n")
        self.errorfile.close()
        self.file.close()



    def read(self):
        times = 0
        result = ""
        while times < 30:
            result = self.logstr
            if result:
                break
            time.sleep(0.1)
            times += 1
        return result

    def get_serialresult(self,zhengze,content):
        resultlist = list()
        content = content.split("\n")
        for line in content:
            if line:
                get_result = re.match(zhengze, line)
                if get_result:
                    result = get_result.group(1)
                    result = ILLEGAL_CHARACTERS_RE.sub('',result)#去掉非法字符
                    result = ''.join(result.split("[0m"))
                    resultlist.append(result)
        # self.log_clear()
        return resultlist

    def get_serialresult_realtime(self,logtime,content):
        if self.kw_dict:
            content_list = content.split("\n")
            for kw_type in self.kw_dict:
                kw = self.kw_dict[kw_type]
                for line in content_list:
                    get_result = re.match(kw, line)
                    if get_result:
                        result = get_result.group(1)
                        result = ILLEGAL_CHARACTERS_RE.sub('',result)#去掉非法字符
                        result = ''.join(result.split("[0m"))
                        if kw_type == "离线识别" or kw_type == "离线唤醒":
                            hanzi_result = pinyin_to_hanzi(result,self.pinyinjson)
                            self.output.LOG_INFO(f"{logtime}{self.name},{kw_type}结果：{hanzi_result}\n\n")
                        elif kw_type == "离线tts" or kw_type == "离线唤醒tts":
                            local_tts = result.split(" ")
                            hanzi_result = Num_to_hanzi(local_tts, self.numjosn)
                            self.output.LOG_INFO(f"{logtime}{self.name},{kw_type}结果：{hanzi_result}\n\n")
                        elif kw_type == "在线tts":
                            tts = ''.join(result.split("[0;33m"))
                            self.output.LOG_INFO(f"{logtime}{self.name},{kw_type}结果：{tts}\n\n")
                        else:
                            self.output.LOG_INFO(f"{logtime}{self.name},{kw_type}结果：{result}\n\n")

    def set_kw_dict(self,kw_dict):
        self.kw_dict = kw_dict

    def set_output(self,output):
        self.output = output

    def set_pinyinjson(self,pinyinjson):
        self.pinyinjson = pinyinjson

    def set_numjson(self,numjson):
        self.numjosn = numjson

    def log_clear(self):
        self.logstr = ''


# if __name__ =="__main__":
#     kw_dict = {"wakeupkw": ".*wakeup_call(.*)",
#     "wakeupttskw": ".*wakeup_tts_callback, tts: (.*)",
#     "asrkw": ".*mwkcmd = (.*)",
#     "ttskw": ".*offline_tts_callbak, tts: (.*)"
#                }
#     try:
#         ser1 =seriallog("test","COM8","115200","CSK_test.log","./",1,None,None)
#         ser1.mark_start()
#         ser1.start()
#         t1 = threading.Thread(target=run_loop, args=(ser1, "CSK", kw_dict,), daemon=True)
#         ser2 = seriallog("test", "COM16", "115200", "WB01_test.log", "./", 1, None, None)
#         ser2.mark_start()
#         ser2.start()
#         t2 = threading.Thread(target=run_loop, args=(ser1, "WB01", kw_dict,), daemon=True)
#         t1.start()
#         t2.start()
#         t1.join()
#         t2.join()
#     except KeyboardInterrupt as e1:
#         print(f"退出：{e1}")



