import logging, os


class output_log():
    def __init__(self, level, path, sjc):
        self.level = level
        self.path = path
        self.sjc = sjc
        # 创建logger对象
        self.logger = logging.getLogger('test_logger')
        # 追加写入文件a ，设置utf-8编码防止中文写入乱码
        test_logname = os.path.join(self.path, "output_log_" + self.sjc + ".log")
        self.test_log = logging.FileHandler(test_logname, 'a+', encoding='utf-8')
        if self.level == 1:
            # 设置日志等级
            self.logger.setLevel(logging.DEBUG)
            # 向文件输出的日志级别
            self.test_log.setLevel(logging.DEBUG)
        elif self.level == 2:
            # 设置日志等级
            self.logger.setLevel(logging.INFO)
            # 向文件输出的日志级别
            self.test_log.setLevel(logging.INFO)
        elif self.level == 3:
            # 设置日志等级
            self.logger.setLevel(logging.WARNING)
            # 向文件输出的日志级别
            self.test_log.setLevel(logging.WARNING)
        elif self.level == 4:
            # 设置日志等级
            self.logger.setLevel(logging.ERROR)
            # 向文件输出的日志级别
            self.test_log.setLevel(logging.ERROR)
        elif self.level == 5:
            # 设置日志等级
            self.logger.setLevel(logging.CRITICAL)
            # 向文件输出的日志级别
            self.test_log.setLevel(logging.CRITICAL)
        # 向文件输出的日志信息格式
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s')
        self.test_log.setFormatter(formatter)

        # 加载文件到logger对象中
        self.logger.addHandler(self.test_log)

    def LOG_DEBUG(self, log):
        # 调试级别的log
        self.logger.debug(log)
        if self.level == 1:
            print(log)

    def LOG_INFO(self, log):
        # 一般信息的log
        self.logger.info(log)
        if self.level <= 2:
            print(log)

    def LOG_WARNING(self, log):
        # 警告信息的log
        self.logger.warning(log)
        if self.level <= 3:
            print(f"\a{log}")

    def LOG_ERROR(self, log):
        # 错误信息的log
        self.logger.error(log)
        if self.level <= 4:
            print(f"\a{log}")

    def LOG_CRITICAL(self, log):
        # 严重错误信息的log
        self.logger.critical(log)
        if self.level:
            print(f"\a{log}")

    def close_file(self):
        # 关闭log文件
        print(f"关闭output_log文件")
        self.logger.removeHandler(self.test_log)
        self.test_log.close()
        logging.shutdown()

# if __name__ == "__main__":
#     shuzi = 1
#     output_log = output_log(1)
#     output_log.LOG_DEBUG(f"你好{shuzi}\n")
#     output_log.LOG_INFO("hello\n")
#     output_log.LOG_WARNING("haha\n")
#     output_log.LOG_ERROR("heihei\n")
#     output_log.LOG_CRITICAL("enen\n")
