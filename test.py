import requests


def setThreshold(deviceId, threshold):
    """
    threshold : [0-20),[0-40),[0-60),[0-80),[0-100)
    """
    # threshold
    # uat环境
    url = "https://uat.aimidea.cn:11003/v1/base2pro/data/transmit"
    # # sit环境
    # url = "http://sit.aimidea.cn:11003/v1/base2pro/data/transmit"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "serviceUrl": "/v1/device/awakeThreshold/set",
        "data": {"deviceId": deviceId, "mid": "54aabf504-6d4d-20220730", "threshold": threshold}
    }
    response = requests.post(url, headers=headers, data=data)
    print(response.text)


def setWakeupAudioUpload(deviceId, threshold):
    """
    threshold : 0/1
    """
    # threshold
    # uat环境
    url = "https://uat.aimidea.cn:11003/v1/base2pro/data/transmit"
    # # sit环境
    # url = "http://sit.aimidea.cn:11003/v1/base2pro/data/transmit"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "serviceUrl": "/v1/device/wakeAudioUploadSwitch/set",
        "data": {"deviceId": deviceId, "mid": "54aabf504-6d4d-4814", "wakeAudioUploadSwitch": threshold}
    }
    response = requests.post(url, headers=headers, data=data)
    print(response.text)


def fullDuplex(deviceId, fullDuplex=0):
    """
    fullDuplex:0,1
    """
    import requests

    # url = "http://sit.aimidea.cn:11003/v1/base2pro/data/transmit"
    url = "https://uat.aimidea.cn:11003/v1/base2pro/data/transmit"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "serviceUrl": "/v1/device/speech/fullDuplex",
        "data": {"fullDuplex": fullDuplex, "timeOut": 30, "deviceId": deviceId,
                 "mid": "echo-5bba2854-1c49-11ed-9a40-43de5ca55de5"}
    }

    response = requests.post(url, headers=headers, data=data)

    print(response.text)


# curl --location --request POST 'http://sit.aimidea.cn:11003/v1/base2pro/data/transmit' \
# --header 'Content-Type: application/x-www-form-urlencoded' \
# --data-urlencode 'serviceUrl=/v1/accent/list'

def switchCheck():
    url = "https://uat.aimidea.cn:11003/v1/base2pro/data/transmit"
    # # sit环境
    # url = "http://sit.aimidea.cn:11003/v1/base2pro/data/transmit"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "serviceUrl": "/v1/accent/set",
        "data": '{"mid":"echo-5bba2854-1c49-11ed-9a40-43de5ca55de5","deviceId":208907214415624,'
                '"accentId":"cantonese","enableAccent":"1", '
                '"mixedResEnable":"1"} '

    }

    response = requests.post(url, headers=headers, data=data)
    print(response.text)


def pad_numbers(version):
    parts = version.split('.')
    padded_parts = [str(int(part)).zfill(2) for part in parts]
    return '.'.join(padded_parts)


def wakeUpWordSwitch(deviceId, word):
    url = "https://uat.aimidea.cn:11003/v1/base2pro/data/transmit"
    # # sit环境
    # url = "http://sit.aimidea.cn:11003/v1/base2pro/data/transmit"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "serviceUrl": "/v1/wakeUpWord/set",
        "data": {"mid": "echo-5bba2854-1c49-11ed-9a40-43de5ca55de5", "deviceId": deviceId, "wakeUpWord": "word"}

    }

    response = requests.post(url, headers=headers, data=data)
    print(response.text)


if __name__ == '__main__':
    deviceID = '210006727464378'
    # setThreshold(deviceID, 10)
    # wakeUpWordSwitch(deviceID, "你好科慕")
    setWakeupAudioUpload(deviceID, 1)
