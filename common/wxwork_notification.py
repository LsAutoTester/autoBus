# -*-coding:utf-8 -*-
__author__ = 'thierryCao'
import requests
import json
from requests_toolbelt import MultipartEncoder
import time
import os

# https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=e46c0c3c-09f9-4adc-a515-4aeac4cc6bb3

class WxWorkRobot(object):
    def __init__(self, appKey):
        self.init(appKey)

    def init(self, appKey):

        # 重要的key 需要密文保存
        # TO-DO
        # self.key = 'fbacb072-7774-4ee7-b69d-137bf68c79b5'
        self.key = appKey

    def get_file_url(self, path, rename=''):

        key = self.key
        type = 'file'
        url = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={}&type={}'.format(
            key, type)
        if not (path and os.path.isfile(path)):
            print(f'{path}文件不存在')
            return
        if rename == '':
            rename = os.path.basename(path)

        length = os.path.getsize(path)
        print(f'rename:{rename},path:{path},length:{length}')
        m = MultipartEncoder(
            fields={
                'name': 'media',
                'filename': rename,
                'filelength': str(length),
                'file': (rename, open(path, 'rb'), 'application/octet-stream')
            })
        r = requests.post(url=url, data=m,
                          headers={'Content-Type': m.content_type})
        dict_data = r.json()

        print(dict_data, 'media_id:', dict_data['media_id'])
        return dict_data['media_id']

    def post_media(self, media_id):
        key = self.key
        url = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={}'.format(
            key)
        headers = 'Content-Type: application/json'
        m = {
            "msgtype": "file",
            "file": {
                "media_id": media_id
            }
        }
        r = requests.post(url=url, data=json.dumps(m),
                          headers={'Content-Type': 'application/json'})
        dict_data = r.json()
        print(dict_data)
        return dict_data.get('errcode')

    def post_text(self, text):
        key = self.key
        url = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={}'.format(
            key)
        headers = 'Content-Type: application/json'
        m = {
            "msgtype": "text",
            "text": {
                "content": text,
                "mentioned_list": ["@all"],
                "mentioned_mobile_list": ["@all"]
            }
        }
        r = requests.post(url=url, data=json.dumps(m),
                          headers={'Content-Type': 'application/json'})
        dict_data = r.json()
        print(dict_data)
        return dict_data.get('errcode')

    def post_markdown(self, text):
        key = self.key
        url = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={}'.format(
            key)
        headers = 'Content-Type: application/json'
        m = {
            "msgtype": "markdown",
            "markdown": {
                "content": f'{text}'
            }
        }
        r = requests.post(url=url, data=json.dumps(m),
                          headers={'Content-Type': 'application/json'})
        dict_data = r.json()
        print(dict_data)
        return dict_data.get('errcode')

def init_app_key(appKey):
    global wxwork
    wxwork = WxWorkRobot(appKey)


def send_file_to_wxwork(path, rename='', textMessage='测试已经结束, 请查收测试报告'):
    global wxwork
    success = False
    retry_conut = 0
    while not success and retry_conut < 5:
        try:
            media_id = wxwork.get_file_url(path, rename)
            if media_id:
                wxwork.post_markdown(textMessage)
                wxwork.post_media(media_id)
                success = True
            else:
                print('测试结果上传异常，中止上传!')
        except requests.exceptions.Timeout:
            # 请求超时，等待重试
            retry_conut += 1
        except requests.exceptions.ConnectionError:
            retry_conut += 1
    if not success:
        print('\u001b[0;31m发送文件到企业微信失败\u001b[0m')


def send_text_to_wxwork(msg):
    global wxwork
    success = False
    retry_conut = 0
    while not success and retry_conut < 5:
        try:
            wxwork.post_text(msg)
            success = True
        except requests.exceptions.Timeout:
            # 请求超时，等待重试
            retry_conut += 1
        except requests.exceptions.ConnectionError:
            retry_conut += 1
    if not success:
        print('\u001b[0;31m发送消息到企业微信失败\u001b[0m')


def send_markdown_to_wxwork(msg):
    global wxwork
    success = False
    retry_conut = 0
    while not success and retry_conut < 5:
        try:
            wxwork.post_markdown(msg)
            success = True
        except requests.exceptions.Timeout:
            # 请求超时，等待重试
            retry_conut += 1
        except requests.exceptions.ConnectionError:
            retry_conut += 1
    if not success:
        print('\u001b[0;31m发送 Markdown 消息到企业微信失败\u001b[0m')


def main_entry(path, rename=''):
    send_file_to_wxwork(path, rename)
