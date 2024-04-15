# -*- coding:utf-8 -*-
# 主要将字符串中的数字转成汉字，并且读音符合中文发音

import sys
import os


def num2chinese(num):
    if not num.isdigit():
        return num
    chinese_num = {
        0: "零",
        1: "一",
        2: "二",
        3: "三",
        4: "四",
        5: "五",
        6: "六",
        7: "七",
        8: "八",
        9: "九"
    }
    unit = ["十", "百", "千"]
    result = ""
    num_str = str(num)
    length = len(num_str)
    for i in range(length):
        if int(num_str[i]) != 0:
            if num_str[i] == '1' and length == 2 and i == 0:
                # 此处功能将11 读成 十一而不是一十一
                result += unit[length - i - 2] if length - i - 2 >= 0 else ""
            else:
                result += chinese_num[int(num_str[i])] + (unit[length - i - 2] if length - i - 2 >= 0 else "")
        elif i < length - 1 and int(num_str[i + 1]) != 0:
            result += chinese_num[int(num_str[i])]
    return result


def stringNum2cn(str_):
    temp_digit = ''
    result = ['']
    strList = ''
    for s in str_:
        if s.isdigit():
            temp_digit += s
            strList = ''
            temp = temp_digit
        else:
            temp_digit = ''
            strList += s
            temp = strList
        if result[-1].isdigit() == temp[0].isdigit():
            result[-1] = temp
        else:
            result.append(temp)

    strRes = ''
    for temp_str_ in result:
        strRes += num2chinese(temp_str_)
    return strRes


def get_all_files_in_subdirectories(directory):
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_list.append(os.path.join(root, file))
    return file_list


def rename_files(file_list):
    for i, file_path in enumerate(file_list):
        directory, old_name = os.path.split(file_path)
        new_name = stringNum2cn(os.path.basename(old_name))
        new_file_path = os.path.join(directory, new_name)

        os.rename(file_path, new_file_path)


if __name__ == '__main__':
    if len(sys.argv) == 2:
        folder = sys.argv[1]
        print(folder)
        file_list = get_all_files_in_subdirectories(folder)
        rename_files(file_list)
    else:
        print("请输入需要改名的目录地址")
