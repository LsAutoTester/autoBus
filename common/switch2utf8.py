# -*- coding:utf-8 -*-
'''
可以转任意编码到utf-8编码
'''
import json
import sys

import chardet
from chardet.universaldetector import UniversalDetector


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


if __name__ == '__main__':
    a = load_json('test.json')
    print(a)
    sys.exit()
    filename = 'test.log'
    encode_info = get_encode_info(filename)  # 获取文件编码
    print(encode_info)

    encodeFile2Utf8(filename)  # 转文件编码到utf8格式
    encode_info = get_encode_info(filename)  # 获取文件编码
    print(encode_info)

    # encodeSwitch2utf8(file_path)
    # encoding = detect_encoding(file_path)
    # print(f"Detected encoding: {encoding}")
    #
    # # 假设我们已经检测到了编码
    # utf8_content_str = convert_to_utf8(file_path, encoding)
    # print("Content converted to UTF-8.")
    #
    # encoding = detect_encoding(file_path)
    # print(f"Detected encoding: {encoding}")
