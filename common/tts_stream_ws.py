import queue
import json
import time
import threading
import websockets
import requests
import os
import asyncio
from datetime import datetime
import xlrd
from xlutils.copy import copy
from concurrent.futures import ThreadPoolExecutor
# from faker import Faker

start_date = datetime.now().strftime("%Y%m%d")
TOKEN = '222a9b28-c37e-4f23-baca-67b79f1afafe'
TEXT_DATA = ['测试tts，', '流式合成，', '分段传合成文本，', '最后一段文本。']
base_url = "wss://api.listenai.com/v1/tts/stream"
connParam = "?api_key=" + TOKEN

test_data = "./tts合成.xls"

param = {
    "status": 0,
    "payload": {
        "vcn": "x2_chongchong",
        "speed": 50,
        "volume": 50
    }
}


def custom_print(*args, **kwargs):
    # 打印到控制台
    print(*args, **kwargs)
    # 打印到文件
    log_dir = './log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    with open(f'{log_dir}/{start_date}.log', 'a') as f:
        print(*args, **kwargs, file=f)


def save_wav(q, url, text, row, cols):
    sid = url[len('http://api.iflyos.cn/external/skill_app_action/stream_tts/'):]
    new_worksheet.write(row, cols+1, sid)
    new_workbook.save(new_excel_name)
    signal = q.get()
    custom_print(signal)
    start_time = time.time()
    response = requests.get(url, stream=True)
    first_frame_flag = False
    total_bytes = 0
    wavSource = './wavSource'
    if not os.path.exists(wavSource):
        os.makedirs(wavSource)
    audio_filename = text + '.wav'
    audio_filename = os.path.join(wavSource,audio_filename)
    # Open the file in write mode
    with open(audio_filename, 'wb') as audio_file:
        for chunk in response.iter_content(chunk_size=10):
            if not first_frame_flag:
                first_frame_time = time.time() - start_time
                custom_print("first frame time:{}".format(first_frame_time))

                new_worksheet.write(row, cols, int(first_frame_time*1000))
                new_workbook.save(new_excel_name)
                first_frame_flag = True
            audio_file.write(chunk)
            total_bytes += len(chunk)
            custom_print(f'已合成音频大小: {total_bytes / 1024}kb', end='\r')

    custom_print(f'-------------------------最终音频大小: {total_bytes / 1024}kb-------------------------')


async def process_task(sheet_name, full_text, row, cols):
    try:
        async with websockets.connect(base_url + connParam) as ws:
            # 建立连接后，客户端需要发送tts合成参数初始化请求
            await ws.send(json.dumps(param))
            # 初始化后，服务端会回复tts音频拉取地址
            result = await ws.recv()
            result_json = json.loads(result)
            assert (result_json["error"] == 0)
            url = result_json["url"]
            custom_print(url)
            # 客户端持续发送文本请求用于合成
            q = queue.Queue()
            idx = 0
            text_array = full_text.split("，")
            while idx < len(text_array):
                if not text_array[idx] == '':
                    text_para = {
                        "status": 1,
                        "payload": {
                            "text": text_array[idx] + "，"
                        }
                    }
                    custom_print(f'-------------------------发送文本【{text_array[idx]}，】-------------------------')
                    await ws.send(json.dumps(text_para))
                    if idx == 0:
                        q.put("start_get_tts")
                        t1 = threading.Thread(target=save_wav, args=(q, url, text_array[idx], row, cols))
                        t1.start()
                time.sleep(3)
                idx += 1
            # 文本发送完成后，客户端发送结束请求
            end_para = {
                "status": 2
            }
            await ws.send(json.dumps(end_para))
            t1.join()

    except Exception as e:
        custom_print("error:{}".format(e))


def process_row(args):
    sheet_name, full_text, row, cols = args
    print(sheet_name, full_text, row, cols)
    asyncio.run(process_task(sheet_name, full_text, row, cols))


def generate_random_text():
    fake = Faker('zh-CN')
    text = fake.text()

    # 复制表格并读新表内容
    old_workbook = xlrd.open_workbook(test_data, formatting_info=True)
    new_workbook = copy(old_workbook)
    new_workbook.save(test_data)

    # Get worksheet names
    worksheet_names = old_workbook.sheet_names()

    for sheet_name in worksheet_names:

        old_worksheet = old_workbook.sheet_by_name(sheet_name)
        new_worksheet = new_workbook.get_sheet(sheet_name)

        # 获取表的行数与列数（并判断是否抽取行数，不够抽取所有行）
        rows = old_worksheet.nrows
        cols = old_worksheet.ncols
    for row, split_text in enumerate(text.split('\n')):
        print(split_text)
        for sub_row, sub_split_text in enumerate(split_text.split('.')):
            print(sub_split_text)
            # Write headers to old worksheet
            new_worksheet.write(rows + row, sub_row, sub_split_text)

    new_workbook.save(test_data)


def merge_text():

    # 复制表格并读新表内容
    old_workbook = xlrd.open_workbook(test_data, formatting_info=True)
    new_workbook = copy(old_workbook)
    new_workbook.save(test_data)

    # Get worksheet names
    worksheet_names = old_workbook.sheet_names()

    for sheet_name in worksheet_names:

        old_worksheet = old_workbook.sheet_by_name(sheet_name)
        new_worksheet = new_workbook.get_sheet(sheet_name)

        # 获取表的行数与列数（并判断是否抽取行数，不够抽取所有行）
        rows = old_worksheet.nrows
        cols = old_worksheet.ncols
        for row in range(1, rows):

            text = old_worksheet.row_values(row)[0] + '，'
            if not old_worksheet.row_values(row)[1] == "":
                text += old_worksheet.row_values(row)[1] + '，'
            if not old_worksheet.row_values(row)[2] == "":
                text += old_worksheet.row_values(row)[2] + '，'
            if not old_worksheet.row_values(row)[3] == "":
                text += old_worksheet.row_values(row)[3] + '，'
            print(text)
            new_worksheet.write(row, 4, text)

    new_workbook.save(test_data)


def main(config_file, extract_sheet=[], extract_sheet_num=0, is_parallel=False):
    global new_excel_name, new_workbook, new_worksheet

    # 复制表格并读新表内容
    name, extension = os.path.splitext(config_file)
    new_excel_name = f"{name}_结果汇总_{start_date}{extension}"
    old_workbook = xlrd.open_workbook(config_file, formatting_info=True)
    new_workbook = copy(old_workbook)
    new_workbook.save(new_excel_name)

    # Get worksheet names
    worksheet_names = extract_sheet if extract_sheet else old_workbook.sheet_names()

    for sheet_name in worksheet_names:

        old_worksheet = old_workbook.sheet_by_name(sheet_name)
        new_worksheet = new_workbook.get_sheet(sheet_name)

        # 获取表的行数与列数（并判断是否抽取行数，不够抽取所有行）
        rows = min(old_worksheet.nrows,
                   extract_sheet_num + 1 if 1 < extract_sheet_num + 1 < old_worksheet.nrows else old_worksheet.nrows)
        cols = old_worksheet.ncols

        # 获取对应的列名和索引
        col_name = [old_worksheet.cell(0, i).value for i in range(cols)]
        custom_print("列名:", col_name)
        text_index = col_name.index('文本')

        # Write headers to new worksheet
        new_worksheet.write(0, cols, f'首帧ms时间-{start_date}')
        new_worksheet.write(0, cols + 1, f'tts的sid-{start_date}')
        new_workbook.save(new_excel_name)

        # Prepare tasks for processing
        tasks = [(sheet_name,
                  old_worksheet.row_values(row)[text_index],
                  row, cols,)
                 for row in range(1, rows) if old_worksheet.row_values(row)[text_index] != '']

        # Process tasks
        if is_parallel and sheet_name != '云端识别耗时':
            # 并行执行
            with ThreadPoolExecutor(max_workers=4) as executor:
                executor.map(process_row, tasks)
        else:
            # 串行执行
            for index, task in enumerate(tasks):
                custom_print("{}/{}".format(index + 1, len(tasks)))
                asyncio.run(process_task(*task))

    custom_print("#####运行完成,点击查看结果按钮查看结果!##########")


if __name__ == '__main__':
    main(test_data, ['Sheet1'], 0, True)

    # generate_random_text()
    # merge_text()
