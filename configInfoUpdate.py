# -*- coding: utf-8 -*-
__author__ = "bszheng"
__date__ = "2024/3/18"
__version__ = "1.0"

import argparse
import json


def load_json(file):
    """
    Load json file and switch to python dict type
    :param file: file name
    :return: python dict
    """
    try:
        with open(file, "r+", encoding="utf-8") as fp:
            content = json.load(fp)
        return content
    except Exception as e:
        print(f"load_json出错：{e}")
        return {}


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


def mideaConfigModify(updateInfo, baseInfoFile):
    #  "start_interval_time": 2.0,
    #  "ivw_interval_time": "3",
    #  "asr_interval_time": "5",
    #  "playtype": 2,
    #  "playtimes": 1000,
    #  "log_level": 1,
    #  "asr_retry": 0,
    #  "wxwork_appid": false,
    kyList = updateInfo.split("#")
    baseInfoMap = load_json(baseInfoFile)
    updateInfoMap = {}
    for ky in kyList:
        tempInfo = ky.split(":")
        print(f"更新 {tempKey}:{tempValue}")
        tempKey = tempInfo[0]
        tempValue = tempInfo[-1]
        baseInfoMap.update({tempKey: tempValue})
    jsonToJsonFile(baseInfoMap, baseInfoFile)
    formatted_json = json.dumps(baseInfoMap, ensure_ascii=False, indent=4)

    print("修改后当前配置文件内容为")
    print(formatted_json)


def main(args):
    jsonFile = args.testFile
    updateInfo = args.modifyCig
    mideaConfigModify(updateInfo, jsonFile)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="获取外部参数库args")
    parser.add_argument('-m', "--modifyCig", type=str, default="", help="修改测试json文件信息,key1:value1#key2:value2")
    parser.add_argument('-f', "--testFile", type=int, help="当前需要编辑的文件")
    args = parser.parse_args()
    main(args)
    # # 执行程序
