# _*_ coding:utf-8 _*_
# 依赖pysnmp 请自行安装(可以使用命令 pip install pysnmp)
from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.proto import rfc1902
from pysnmp.entity import engine
import requests

global enter_key
enter_key = '1.3.6.1.4.1.23280.9.1.2'
enter_key = '1.3.6.1.4.1.23280.8.1.2'

snmpEngine = None


def initEngine():
    snmpEngine = engine.SnmpEngine()


def check_netconnect(device_ip):
    try:
        # http = urllib3.PoolManager()
        # re = http.request('GET', 'http://192.168.110.240:5000')
        # TODO 从fig文件统一配置url
        re = requests.get(f"http://{device_ip}", timeout=5)
        print(re)
        if re.status_code == 200:
            print('服务器正常')
            return True
        else:
            print('服务器异常，错误码为', re.status_code)
            return False
    except:
        return False


def validate_ip(ip_str):
    sep = ip_str.split('.')
    if len(sep) != 4:
        return False
    for i, x in enumerate(sep):
        try:
            int_x = int(x)
            if int_x < 0 or int_x > 255:
                return False
        except:
            return False
    return True


def validate_Sock(nSock):
    if (nSock <= 0 or nSock > 8):
        return False
    return True


def get_value(devip, soid):
    cg = cmdgen.CommandGenerator(snmpEngine)
    errorIndication, errorStatus, errorIndex, varBinds = cg.getCmd(
        cmdgen.CommunityData('pudinfo', 'public', 0),
        cmdgen.UdpTransportTarget((devip, 161)), soid)
    sResult = varBinds[0][1]
    return sResult


# 获取设备名称
def GetDeviceName(sDevIp):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    devName = get_value(sDevIp, '.1.3.6.1.2.1.1.1.0')
    devName.asOctets().decode('unicode_escape', 'ignore')
    return devName


# 获取总电压
def GetTotalVoltage(sDevIp):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    value = get_value(sDevIp, '.1.3.6.1.4.1.23280.6.1.2.1')
    rt_value = float(value) / 10
    return rt_value


# 获取总电流
def GetTotalCurrent(sDevIp):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    value = get_value(sDevIp, '.1.3.6.1.4.1.23280.6.1.3.1')
    rt_value = float(value) / 100
    return rt_value


# 获取总功率
def GetTotalPower(sDevIp):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    value = get_value(sDevIp, '.1.3.6.1.4.1.23280.6.1.4.1')
    rt_value = float(value) / 1000
    return rt_value


# 获取总电能
def GetTotalEnergy(sDevIp):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    value = get_value(sDevIp, '.1.3.6.1.4.1.23280.6.1.8.1')
    rt_value = float(value) / 1000
    return rt_value


# 获取温度
def GetTemprature(sDevIp):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    value = get_value(sDevIp, enter_key + '.4.6.0')
    rt_value = float(value) / 10
    return rt_value


# 获取湿度
def GetHumidity(sDevIp):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    value = get_value(sDevIp, enter_key + '.4.7.0')
    rt_value = float(value) / 10
    return rt_value


# 打开或关闭指定插口
def TurnOnOff(sDevIp, sock, onoff):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    if validate_Sock(sock) == False:
        print('invalid sock!')
        return None
    sOId = '.1.3.6.1.4.1.23280.9.1.2.%d' % (sock)
    if onoff == True:
        state = 1
    else:
        state = 2
    cg = cmdgen.CommandGenerator(snmpEngine)
    errorIndication, errorStatus, errorIndex, varBinds = cg.setCmd(
        cmdgen.CommunityData('pudinfo', 'private', 0),
        cmdgen.UdpTransportTarget((sDevIp, 161)),
        (sOId, rfc1902.Integer(state)))

    return errorStatus


# 获取插口状态 1-关闭 2-开启
def GetStatus(sDevIp, sock):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    if validate_Sock(sock) == False:
        print('invalid sock!')
        return None
    sOId = '.1.3.6.1.4.1.23280.8.1.2.%d' % (sock)
    # print("sOId:{0}".format(sOId))
    cg = cmdgen.CommandGenerator(snmpEngine)
    errorIndication, errorStatus, errorIndex, varBinds = cg.getCmd(
        cmdgen.CommunityData('pudinfo', 'public', 0),
        cmdgen.UdpTransportTarget((sDevIp, 161)), sOId)
    # print(varBinds)
    # print(varBinds[0])
    sResult = varBinds[0][1]
    # print(sResult)
    return sResult
    # if sResult == b'on':
    #   return 0
    # elif sResult == b'off':
    #   return 1

    # return errorStatus


# 获取指定插口电流
def GetCurrent(sDevIp, nsock):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    if validate_Sock(nsock) == False:
        print('invalid sock!')
        return None
    sOId = '.1.3.6.1.4.1.23280.8.1.4.%d' % (nsock)
    value = get_value(sDevIp, sOId)
    rt_value = float(value) / 100
    return rt_value


# 获取指定插口电能
def GetEnergy(sDevIp, nSock):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    if validate_Sock(nSock) == False:
        print('invalid sock!')
        return None
    sOId = enter_key + '.4.%d.0' % (31 + nSock)
    value = get_value(sDevIp, sOId)
    rt_value = float(value) / 100
    return rt_value


# 获取指定插口电压
# def GetCurrent(sDevIp,nsock):
#     if validate_ip(sDevIp) == False:
#        print ('invalid ip address!')
#        return None
#     if validate_Sock(nsock) == False:
#        print ('invalid sock!')
#        return None
#     sOId = '.1.3.6.1.4.1.23280.8.1.3.%d' % (nsock)
#     value = str(get_value(sDevIp, sOId))
#     rt_value = float(value)/10
#     return rt_value
# 获取指定插口名称
def GetSockName(sDevIp, nSock):
    if validate_ip(sDevIp) == False:
        print('invalid ip address!')
        return None
    if validate_Sock(nSock) == False:
        print('invalid sock!')
        return None
    sOId = '.1.3.6.1.4.1.23273.4' + '.%d.1' % (7 + nSock)
    value = get_value(sDevIp, sOId).asOctets().decode('unicode_escape', 'ignore')
    return value
