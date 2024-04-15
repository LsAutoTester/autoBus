# 美的钰行单麦挂机 云端相关请求
import requests
import json


# 设置日志等级
def setLogLevel():
    url = 'https://uat.aimidea.cn:11003/v1/base2pro/data/transmit'
    data = {
        'serviceUrl': '/v1/device/log/set',
        'data': json.dumps({"deviceId": "211106233629340", "logLevel": 6, "status": "1"})
    }

    response = requests.post(url, data=data)
    print(response.text)


# 上传设备唤醒音频
def uploadDeviceWakeupAudio():
    import requests
    import json

    url = 'https://uat.aimidea.cn:11003/v1/base2pro/data/transmit'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {
        'serviceUrl': '/v1/device/wakeAudioUploadSwitch/set',
        'data': json.dumps({"deviceId": 211106233629340, "mid": "54aabf504-6d4d-4814", "wakeAudioUploadSwitch": 1})
    }

    response = requests.post(url, headers=headers, data=data)
    print(response.text)
