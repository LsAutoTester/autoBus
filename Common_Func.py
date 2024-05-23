# -*- coding:utf-8 -*-
import configparser
import csv
import json
import os, re, sys
import string
import pyaudio, wave
import urllib3
import random
import chardet
from chardet.universaldetector import UniversalDetector
import serial
import serial.tools.list_ports


# 获取文件编码类型
def get_encoding(file):
    # 二进制方式读取，获取字节数据，检测类型
    with open(file, 'rb') as f:
        data = f.read()
        return chardet.detect(data)['encoding']


def get_encode_info(file):
    with open(file, 'rb') as f:
        detector = UniversalDetector()
        for line in f.readlines():
            detector.feed(line)
            if detector.done:
                break
        detector.close()
        return detector.result['encoding']


def read_file(file):
    with open(file, 'rb') as f:
        return f.read()


def write_file(content, file):
    with open(file, 'wb') as f:
        f.write(content)


def convert_encode2utf8(file, original_encode, des_encode):
    file_content = read_file(file)
    file_decode = file_content.decode(original_encode, 'ignore')
    file_encode = file_decode.encode(des_encode)
    write_file(file_encode, file)


def encodeFile2Utf8(fileName):
    encodeInfo = get_encode_info(fileName)
    if encodeInfo != 'utf-8':
        print(f"修改{fileName}文件编码格式为utf-8")
        convert_encode2utf8(fileName, encodeInfo, 'utf-8')


def traversalFile(rootdir):
    '''
    遍历指定文件夹下的所有文件，返回一个文件路径列表
    :param rootdir:
    :return:
    '''
    filelist = []
    subdirlist = []
    for maindir, subdir, file_name_list in os.walk(rootdir):
        if subdir != []:
            subdirlist = subdir
        for filename in file_name_list:
            if ".wav" in filename:
                filelist.append(os.path.join(maindir, filename))
    return filelist, subdirlist


# 生成文件夹
def createdirs(path):
    isExists = os.path.exists(path)  # 判断是否已存在目录
    if isExists == True:
        pass
    else:
        os.makedirs(path)


def get_Midea_log(debug, type, kw):
    """
    获取日志中的关键字信息
    :return:
    """
    # 获取日志中的关键信息
    local_info = ""
    if type == "adb":
        local_info = debug.get_adbresult(kw, debug.read())
    elif type == "串口":
        local_info = debug.get_serialresult(kw, debug.read())
    if local_info:
        local_info = local_info.strip("[0m\n\"\x1b[K\rcnt = ")  # 去掉异常字符和换行符和双引号
    return local_info


# 将拼音转为汉字
def pinyin_to_hanzi(asrstr, pinyinjson):
    asr_get_info_chinese = asrstr
    if asrstr in pinyinjson["p_c"]:
        asr_get_info_chinese = pinyinjson["p_c"][asrstr]
    else:
        pass
        # print(f"{asrstr}拼音不存在！")
    return asr_get_info_chinese


# 将离线tts的数字转为汉字
def Num_to_hanzi(ttsNumlist, ttsjson):
    new_list = list()
    for ttsNum in ttsNumlist:
        if ttsNum in ttsjson:
            tts_get_info_chinese = ttsjson[ttsNum]
            new_list.append(tts_get_info_chinese)
    if new_list:
        new_tts_str = "".join(new_list)
        return new_tts_str
    else:
        new_tts_str = "".join(ttsNumlist)
        return new_tts_str


def jiexi_testcase(testcase):
    wake_up_play_txt = []
    playTxt = []
    exceptTTS = []
    except_Skill = []
    if testcase:
        with open(testcase, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                wake_up = row["wake_up"]
                recognize = row["recognize"]
                expect_tts = row["expect_tts"]
                except_skill = row["except_skill"]
                wake_up_play_txt.append(wake_up)
                playTxt.append(recognize)
                exceptTTS.append(expect_tts)
                except_Skill.append(except_skill)
    else:
        print("testCase不存在！！\n")
        # 程序直接退出
        sys.exit()
        # 解析结束
    return wake_up_play_txt, playTxt, exceptTTS, except_Skill


def load_json(file):
    """
    Load json file and switch to python dict type
    :param file: file name
    :return: python dict
    """
    encodeFile2Utf8(file)
    with open(file, "r+", encoding="utf-8") as fp:
        content = json.load(fp)
    return content


def jsonToJsonFile(json_content, filename):
    """
    将json对象写入json文件中
    :param json_content: json对象
    :param filename: 要写入的json文件名，如 base.json
    :return: NONE
    """
    content = json.dumps(json_content, ensure_ascii=False, indent=1)
    with open(filename, 'w+', encoding='utf-8') as f:
        f.write(content)


def check_serial():
    # 检测电脑连接的串口
    serialName_list = list()
    plist = list(serial.tools.list_ports.comports())
    if len(plist) <= 0:
        print("没有发现串口端口!\n")
    else:
        for p in plist:
            serialName = p[0]
            serialName_list.append(serialName)
    return serialName_list


def Random_time(get_time):
    random_time = 1.0
    if "-" in get_time:
        get_time_list = ((get_time.strip("[")).strip("]")).split("-")
        if len(get_time_list) == 2:
            random_time = '{:.1f}'.format(random.uniform(float(get_time_list[0]), float(get_time_list[1])))
        else:
            print("随机时间编写有问题，请检查后再重试！")
    else:
        random_time = get_time
    return float(random_time)


def get_serial(port, baudrate=115200, time_out=0.5):
    """
    实例化串口对象
    :param port: 串口名，如 "COM87"
    :param baudrate: 默认115200
    :param time: 超时时间，默认0.5s
    :return: 串口实例化对象
    """
    serials = ""
    try:
        # serials = serial.Serial(port, baudrate,timeout=0.5,
        #                         parity=serial.PARITY_NONE,
        #                         stopbits=serial.STOPBITS_ONE,
        #                         xonxoff=0,writeTimeout=1,
        #                         rtscts=0)  # /dev/ttyUSB0
        serials = serial.Serial(port, baudrate, timeout=time_out)

    except Exception as e:
        print(f"串口连接出错，出错信息{e}")
    return serials


def change_list_order(l, online):
    if online:
        if len(l) >= 7:
            l.insert(0, l[-5])
            l.insert(1, l[-8])
            l.insert(2, l[-7])
            l.insert(3, l[-6])
            l.pop(-8)
            l.pop(-7)
            l.pop(-6)
            l.pop(-5)
    else:
        if len(l) >= 6:
            l.insert(0, l[-5])
            l.insert(1, l[-7])
            l.insert(2, l[-6])
            l.pop(-7)
            l.pop(-6)
            l.pop(-5)
    return l


def check_netconnect():
    try:
        http = urllib3.PoolManager()
        http.request('GET', 'https://qyapi.weixin.qq.com')
        return True
    except:
        return False


def tryint(s):
    try:
        return int(s)
    except ValueError:
        return s


def str2int(v_str):  # 将元素中的字符串和数字分割开
    return [tryint(sub_str) for sub_str in re.split('([0-9]+)', v_str)]


def sort_humanly(v_list):  # 以分割后的list为单位进行排序
    return sorted(v_list, key=str2int)


def generate_random_char():
    return random.choice(string.ascii_letters + string.digits)


def fileIsExists(file_path):
    if os.path.exists(file_path):
        return True
    else:
        print(f"{file_path} 文件不存在！")
        return False


def pad_numbers(version):
    """
    填充版本号信息4.0.7->04.00.07
    """
    parts = version.split('.')
    padded_parts = [str(int(part)).zfill(2) for part in parts]
    return '.'.join(padded_parts)


# print(Random_time("[1-5]"))
# random_char = generate_random_char()
# print("随机字符：", random_char)
#
# random_char = generate_random_char()
# print("随机字符：", random_char)
