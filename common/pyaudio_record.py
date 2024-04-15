#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# ------------- 音频设备操作模块 -------------------
#
#   功能:   录制/获取音频流/播放音频
#   时间：  2021-09-13
#
# --------------------------------------------------

import sys, pyaudio, wave
# from tqdm import tqdm


class UacAudioInAndOut:
    def __init__(self):
        """
            功能:   录音参数初始化
                    创建vad检测模块对象
            参数:   /
            返回值: /
        """
        self.input_format_dict = {"S8_LE": 16, "S16_LE": 8, "S24_LE": 4, "S32_LE": 2}
        self.framerate_list = [8000, 11025, 16000, 22050, 32000, 44100, 48000,
                               88200, 96000, 176400, 192000, 352800, 384000]
        self.stop_record = False
        self.UacAudioInHandle = False
        self.StreamHandle =False
        self.load_parame_dict = False


    def re_stop(self):
        self.stop_record = True

    def _inforPrintf(self, infor_content):
        """
            功能:   检测操作系统，使用正确编码
                    输出打印信息
            参数:   infor_content: 信息内容
            返回值: /
        """
        if sys.platform != "linux" and sys.platform != "darwin":
            infor_content = str(infor_content).encode("gbk", "ignore").decode("gbk")
        print(infor_content)

    def GetAllDevInfor(self):
        """
            功能:   显示支持设备信息
            参数:   /
            返回值: /
        """
        index_dict = dict()
        PA = pyaudio.PyAudio()
       #self._inforPrintf("----------------------< 本机支持设备 >------------------------------")
        for dev_index in range(PA.get_device_count()):
            #self._inforPrintf("\n-------------------------------------------------------")
            # print(PA.get_device_info_by_index(dev_index))
            for key in PA.get_device_info_by_index(dev_index):
                if key == "name":
                    index_dict[dev_index] = str(PA.get_device_info_by_index(dev_index)[key])
                    if index_dict[dev_index] == '麦克风 (CSK6_Audio)':
                        print(PA.get_device_info_by_index(dev_index))

                # self._inforPrintf("%s:%s" % (key, str(PA.get_device_info_by_index(dev_index)[key])))
            # self._inforPrintf("========================================================")
        #print(f"index_dict:{index_dict}")
        PA.terminate()
        return index_dict

    def GetUacDevInfor(self, devKeywordOrIndex=None):
        """
            功能:   获取UAC设备信息
            参数:   devKeywordOrIndex: 设备名称关键字或索引
            返回值: dic 设备信息字典
                    False 设备信息获取失败
        """
        PA = pyaudio.PyAudio()
        if devKeywordOrIndex == None:
            self._inforPrintf("\033[0;36;31m[UacAudioInAndOut] 未设设备, 当前使用默认设备\033[0m")
            return PA.get_default_input_device_info()
        if str(devKeywordOrIndex).isdigit():
            devKeywordOrIndex = int(devKeywordOrIndex)
            return PA.get_device_info_by_index(devKeywordOrIndex)

        uac_infor_list = []
        for uac_index in range(PA.get_device_count()):
            if PA.get_device_info_by_index(uac_index).get("name").find(str(devKeywordOrIndex)) >= 0:
                uac_infor_list.append(PA.get_device_info_by_index(uac_index))

        if len(uac_infor_list) > 1:
            self._inforPrintf("\033[0;36;33m[UacAudioInAndOut] UAC 设备有多个，\
                    请修正关键字, 当前设备如下: %s\033[0m" % str(uac_infor_list))
            return False
        else:
            return uac_infor_list.pop()

    def is_framerate_supported(self, setFramerate, UacAudioInHandle,
                               load_parame_dict, input_or_output="input"):
        """
            功能:   判断当配置在指定设备中是否支持
            参数:   setFramerate:       设置采样率
                    UacAudioInHandle:   设备句柄
                    load_parame_dict:   加载字典
                    input_or_output:    输入/输出功能
            返回值: bool True/False
        """
        try:
            if input_or_output == "input":
                UacAudioInHandle.is_format_supported(rate=float(setFramerate),
                                                     input_device=load_parame_dict['index'],
                                                     input_channels=load_parame_dict['setInputChannels'],
                                                     input_format=load_parame_dict['_setInputFormat'])
            else:
                UacAudioInHandle.is_format_supported(rate=float(setFramerate),
                                                     output_device=load_parame_dict['index'],
                                                     output_channels=load_parame_dict['maxOutputChannels'],
                                                     output_format=UacAudioInHandle.get_format_from_width(
                                                         load_parame_dict['setOutputFormat']))
            return True
        except:
            return False

    def LoadUacAudioInDevice(self, maxStreamDuration=1000, setInputChannels=None,
                             setInputFormat=None, setInputFramerate = None, devKeywordOrIndex=None,output = None):
        """
            功能:   加载音频获取设备
            参数:   maxStreamDuration=1000 默认一段流时长
                    setInputChannels:           通道数
                    setInputFormat:             位宽
                    devKeywordOrIndex:    录音设备关键字/索引
            返回值:
                    成功: UacAudioInHandle, StreamHandle, load_parame_dict
                    失败: False
        """
        try:
            load_parame_dict = {}
            uac_infor_dict = self.GetUacDevInfor(devKeywordOrIndex)
            print(f"uac_infor_dict:{uac_infor_dict}")
            if not setInputFormat:
                _Format = "S16_LE"
                #self._inforPrintf("\033[0;36;33m[UacAudioInAndOut] 未设置位宽，使用默认 S16_LE \033[0m")
                if output:
                    output.LOG_DEBUG("[UacAudioInAndOut] 未设置位宽，使用默认 S16_LE ")
            else:
                _Format = setInputFormat
            setInputFormat = self.input_format_dict[_Format]

            if not setInputChannels or int(setInputChannels) > uac_infor_dict["maxInputChannels"]:
                setInputChannels = uac_infor_dict["maxInputChannels"]
                #self._inforPrintf("\033[0;36;33m[UacAudioInAndOut] 输入通道未设置/超出当前设备最大值,使用默认最大通道 %s\033[0m" % setInputChannels)
                if output:
                    output.LOG_DEBUG("[UacAudioInAndOut] 输入通道未设置/超出当前设备最大值,使用默认最大通道 %s" % setInputChannels)
            else:
                setInputChannels = int(setInputChannels)
            dev_index = uac_infor_dict["index"]
            load_parame_dict["index"] = dev_index
            load_parame_dict["setInputFormat"] = _Format
            load_parame_dict["_setInputFormat"] = setInputFormat
            load_parame_dict["setInputChannels"] = setInputChannels
            UacAudioInHandle = pyaudio.PyAudio()
            if setInputFramerate:
                if self.is_framerate_supported(setInputFramerate, UacAudioInHandle, load_parame_dict):
                    load_parame_dict["setInputFramerate"] = setInputFramerate
                else:
                    for setInputFramerate in self.framerate_list:
                        if self.is_framerate_supported(setInputFramerate, UacAudioInHandle, load_parame_dict):
                            load_parame_dict["setInputFramerate"] = setInputFramerate
                            break
            else:
                for setInputFramerate in self.framerate_list:
                    if self.is_framerate_supported(setInputFramerate, UacAudioInHandle, load_parame_dict):
                        load_parame_dict["setInputFramerate"] = setInputFramerate
                        break
            # 计算数据大小一段
            CHUNK_SIZE = int(setInputFramerate * maxStreamDuration / 1000)
            load_parame_dict["CHUNK_SIZE"] = CHUNK_SIZE
            #self._inforPrintf("\033[0;36;38m[UacAudioInAndOut] 加载参数: %s\033[0m" % str(load_parame_dict))
            if output:
                output.LOG_DEBUG("[UacAudioInAndOut] 加载参数: %s" % str(load_parame_dict))
            # 加载设备
            StreamHandle = UacAudioInHandle.open(
                format=load_parame_dict['_setInputFormat'],
                #format=pyaudio.paInt16,
                channels=load_parame_dict['setInputChannels'],
                rate=load_parame_dict['setInputFramerate'],
                input=True,
                input_device_index=load_parame_dict['index'],
                start=False,
                frames_per_buffer=int(CHUNK_SIZE))
            # # 开始流获取
            # StreamHandle.start_stream()
            self.UacAudioInHandle = UacAudioInHandle
            self.StreamHandle = StreamHandle
            self.load_parame_dict = load_parame_dict
            return UacAudioInHandle, StreamHandle, load_parame_dict
        except:
            #self._inforPrintf("\033[0;36;31m[UacAudioInAndOut] Uac AudioIn 加载失败\033[0m")
            if output:
                output.LOG_ERROR("[UacAudioInAndOut] Uac AudioIn 加载失败")
            return False, False, False


    def UacAudioInRecord(self, saveWavFile, recordTime,output = None):
        """
            功能:   录制音频文件
            参数:   recordTime:         录音时长, 单位(s)
                    setInputFramerate:  采样率
                    setInputChannels:   通道数
                    setInputFormat:     位宽
                    devKeywordOrIndex:      录音设备索引
            返回值: /
        """
        if not self.UacAudioInHandle or not self.StreamHandle:
            #self._inforPrintf("\033[0;36;31m[UacAudioInAndOut] 录音失败\033[0m")
            if output:
                output.LOG_ERROR("[UacAudioInAndOut] 录音失败!")
            return False
        self.stop_record = False

        # self._inforPrintf("\033[1;36;34m[UacAudioInAndOut] 录音 -> 文件名: %s 时长: %s\
        #                                     \033[0m" % (saveWavFile, recordTime))
        if output:
            output.LOG_DEBUG("[UacAudioInAndOut] 录音 -> 文件名: %s 时长: %s" % (saveWavFile, recordTime))
        #self._inforPrintf(self.load_parame_dict["CHUNK_SIZE"])
        if output:
            output.LOG_DEBUG(self.load_parame_dict["CHUNK_SIZE"])
        data_list = []
        stop_record_count = 0
        play_flag = False
        # if not setchannels:
        #     channels = self.load_parame_dict["setInputChannels"]
        # else:
        #     channels = setchannels
        try:
            wavfb = wave.open(saveWavFile, "wb")
            print(self.load_parame_dict["setInputChannels"])
            print(self.UacAudioInHandle.get_sample_size(self.load_parame_dict["_setInputFormat"]))
            print(self.load_parame_dict["setInputFramerate"])
            wavfb.setnchannels(self.load_parame_dict["setInputChannels"])
            wavfb.setnchannels(1)
            wavfb.setsampwidth(self.UacAudioInHandle.get_sample_size(self.load_parame_dict["_setInputFormat"]))
            wavfb.setframerate(self.load_parame_dict["setInputFramerate"])
            # wavfb.setframerate(16000)
            # 开始流获取
            self.StreamHandle.start_stream()
            for recordTime_index in range(int(recordTime)*4):
                if not self.stop_record:
                    data = None
                    data = self.StreamHandle.read(int(self.load_parame_dict["CHUNK_SIZE"]/4), exception_on_overflow=False)
                    wavfb.writeframes(data)
                else:
                    #停止流获取
                    if output:
                        output.LOG_DEBUG(f"[UacAudioInAndOut] 文件名：{saveWavFile} 录音停止保存!")
                    self.StreamHandle.stop_stream()
                    wavfb.close()
                    break
        except Exception as e:
            print(f"[UacAudioInAndOut] 录音出现异常，异常信息{e}")
            if output:
                output.LOG_DEBUG(f"[UacAudioInAndOut] 录音出现异常，异常信息{e}")
            self.StreamHandle.stop_stream()

    def close_UacAudio_record(self):
        """
            功能:   关闭音频流设备
            参数:   UacAudioInHandle
            返回值: bool True/False
        """
        try:
            self.StreamHandle.stop_stream()
            # self.StreamHandle.close()
            self.CloseAudioDevice(self.UacAudioInHandle)
            return True
        except:
            return False

    def CloseAudioDevice(self, UacAudioDeviceHandle):
        """
            功能:   释放 Audio 设备
            参数:   UacAudioDeviceHandle
            返回值: bool True/False
        """
        try:
            UacAudioDeviceHandle.terminate()
            return True
        except:
            return False


if __name__ == "__main__":
    asv = UacAudioInAndOut()
    asv.GetAllDevInfor()
    flags = asv.LoadUacAudioInDevice(setInputFramerate=16000,devKeywordOrIndex=1)
    print(flags)
    if flags[0] == False:
        sys.exit(0)
    else:
        asv.UacAudioInRecord("test.wav", 10)
        # asv.UacAudioInRecord("test-2.wav", 5)
