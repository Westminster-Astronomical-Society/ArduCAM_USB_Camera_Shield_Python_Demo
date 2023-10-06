import time
import threading

import ArducamSDK
import arducam_config_parser

ErrorCode_Map = {
    0x0000: "USB_CAMERA_NO_ERROR",
    0xFF01: "USB_CAMERA_USB_CREATE_ERROR",
    0xFF02: "USB_CAMERA_USB_SET_CONTEXT_ERROR",
    0xFF03: "USB_CAMERA_VR_COMMAND_ERROR",
    0xFF04: "USB_CAMERA_USB_VERSION_ERROR",
    0xFF05: "USB_CAMERA_BUFFER_ERROR",
    0xFF06: "USB_CAMERA_NOT_FOUND_DEVICE_ERROR",
    0xFF0B: "USB_CAMERA_I2C_BIT_ERROR",
    0xFF0C: "USB_CAMERA_I2C_NACK_ERROR",
    0xFF0D: "USB_CAMERA_I2C_TIMEOUT",
    0xFF20: "USB_CAMERA_USB_TASK_ERROR",
    0xFF21: "USB_CAMERA_DATA_OVERFLOW_ERROR",
    0xFF22: "USB_CAMERA_DATA_LACK_ERROR",
    0xFF23: "USB_CAMERA_FIFO_FULL_ERROR",
    0xFF24: "USB_CAMERA_DATA_LEN_ERROR",
    0xFF25: "USB_CAMERA_FRAME_INDEX_ERROR",
    0xFF26: "USB_CAMERA_USB_TIMEOUT_ERROR",
    0xFF30: "USB_CAMERA_READ_EMPTY_ERROR",
    0xFF31: "USB_CAMERA_DEL_EMPTY_ERROR",
    0xFF51: "USB_CAMERA_SIZE_EXCEED_ERROR",
    0xFF61: "USB_USERDATA_ADDR_ERROR",
    0xFF62: "USB_USERDATA_LEN_ERROR",
    0xFF71: "USB_BOARD_FW_VERSION_NOT_SUPPORT_ERROR",
}


class ArducamCamera(object):
    def __init__(self):
        self.isOpened = False
        self.running_ = False
        self.signal_ = threading.Condition()
        pass

    def openCamera(self, fname, index=0):
        (
            self.isOpened,
            self.handle,
            self.cameraCfg,
            self.color_mode,
        ) = camera_initFromFile(fname, index)

        return self.isOpened

    def start(self):
        if not self.isOpened:
            raise RuntimeError("The camera has not been opened.")

        self.running_ = True
        ArducamSDK.Py_ArduCam_setMode(self.handle, ArducamSDK.CONTINUOUS_MODE)
        self.capture_thread_ = threading.Thread(target=self.capture_thread)
        self.capture_thread_.daemon = True
        self.capture_thread_.start()

    def read(self, timeout=1500):
        if not self.running_:
            raise RuntimeError("The camera is not running.")

        if ArducamSDK.Py_ArduCam_availableImage(self.handle) <= 0:
            with self.signal_:
                self.signal_.wait(timeout / 1000.0)

        if ArducamSDK.Py_ArduCam_availableImage(self.handle) <= 0:
            return (False, None, None)

        ret, data, cfg = ArducamSDK.Py_ArduCam_readImage(self.handle)
        ArducamSDK.Py_ArduCam_del(self.handle)
        size = cfg["u32Size"]
        if ret != 0 or size == 0:
            return (False, data, cfg)

        return (True, data, cfg)

    def stop(self):
        if not self.running_:
            raise RuntimeError("The camera is not running.")

        self.running_ = False
        self.capture_thread_.join()

    def closeCamera(self):
        if not self.isOpened:
            raise RuntimeError("The camera has not been opened.")

        if self.running_:
            self.stop()
        self.isOpened = False
        ArducamSDK.Py_ArduCam_close(self.handle)
        self.handle = None

    def capture_thread(self):
        ret = ArducamSDK.Py_ArduCam_beginCaptureImage(self.handle)

        if ret != 0:
            self.running_ = False
            raise RuntimeError(
                "Error beginning capture, Error : {}".format(GetErrorString(ret))
            )

        print("Capture began, Error : {}".format(GetErrorString(ret)))

        while self.running_:
            ret = ArducamSDK.Py_ArduCam_captureImage(self.handle)
            if ret > 255:
                print("Error capture image, Error : {}".format(GetErrorString(ret)))
                if ret == ArducamSDK.USB_CAMERA_USB_TASK_ERROR:
                    break
            elif ret > 0:
                with self.signal_:
                    self.signal_.notify()

        self.running_ = False
        ArducamSDK.Py_ArduCam_endCaptureImage(self.handle)

    def setCtrl(self, func_name, val):
        return ArducamSDK.Py_ArduCam_setCtrl(self.handle, func_name, val)

    def dumpDeviceInfo(self):
        USB_CPLD_I2C_ADDRESS = 0x46
        cpld_info = {}
        ret, version = ArducamSDK.Py_ArduCam_readReg_8_8(
            self.handle, USB_CPLD_I2C_ADDRESS, 0x00
        )
        ret, year = ArducamSDK.Py_ArduCam_readReg_8_8(
            self.handle, USB_CPLD_I2C_ADDRESS, 0x05
        )
        ret, mouth = ArducamSDK.Py_ArduCam_readReg_8_8(
            self.handle, USB_CPLD_I2C_ADDRESS, 0x06
        )
        ret, day = ArducamSDK.Py_ArduCam_readReg_8_8(
            self.handle, USB_CPLD_I2C_ADDRESS, 0x07
        )

        cpld_info["version"] = "v{}.{}".format(version >> 4, version & 0x0F)
        cpld_info["year"] = year
        cpld_info["mouth"] = mouth
        cpld_info["day"] = day

        print(cpld_info)

        ret, data = ArducamSDK.Py_ArduCam_getboardConfig(
            self.handle, 0x80, 0x00, 0x00, 2
        )

        usb_info = {}
        usb_info["fw_version"] = "v{}.{}".format((data[0] & 0xFF), (data[1] & 0xFF))
        usb_info["interface"] = 2 if self.cameraCfg["usbType"] == 4 else 3
        usb_info["device"] = (
            3 if self.cameraCfg["usbType"] == 3 or self.cameraCfg["usbType"] == 4 else 2
        )

        print(usb_info)

    def getCamInformation(self):
        self.version = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 00)[1]
        self.year = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 5)[1]
        self.mouth = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 6)[1]
        self.day = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 7)[1]
        cpldVersion = "V{:d}.{:d}\t20{:0>2d}/{:0>2d}/{:0>2d}".format(
            self.version >> 4, self.version & 0x0F, self.year, self.mouth, self.day
        )
        return cpldVersion

    def getMipiDataInfo(self):
        mipiData = {
            "mipiDataID": "",
            "mipiDataRow": "",
            "mipiDataCol": "",
            "mipiDataClk": "",
            "mipiWordCount": "",
            "mFramerateValue": "",
        }
        self.getCamInformation()
        cpld_version = self.version & 0xF0
        date = self.year * 1000 + self.mouth * 100 + self.day
        if cpld_version not in [0x20, 0x30]:
            return None
        if cpld_version == 0x20 and date < (19 * 1000 + 7 * 100 + 8):
            return None
        elif cpld_version == 0x30 and date < (19 * 1000 + 3 * 100 + 22):
            return None

        mipiDataID = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 0x1E)[1]
        mipiData["mipiDataID"] = hex(mipiDataID)

        rowMSB = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 0x21)[1]
        rowLSB = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 0x22)[1]
        mipiDataRow = ((rowMSB & 0xFF) << 8) | (rowLSB & 0xFF)
        mipiData["mipiDataRow"] = str(mipiDataRow)

        colMSB = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 0x1F)[1]
        colLSB = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 0x20)[1]
        mipiDataCol = ((colMSB & 0xFF) << 8) | (colLSB & 0xFF)
        mipiData["mipiDataCol"] = str(mipiDataCol)

        # after 2020/06/22
        if cpld_version == 0x20 and date < (20 * 1000 + 6 * 100 + 22):
            return mipiData
        elif cpld_version == 0x30 and date < (20 * 1000 + 6 * 100 + 22):
            return mipiData

        mipiDataClk = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 0x27)[1]
        mipiData["mipiDataClk"] = str(mipiDataClk)

        if (cpld_version == 0x30 and date >= (21 * 1000 + 3 * 100 + 1)) or (
            cpld_version == 0x20 and date >= (21 * 1000 + 9 * 100 + 6)
        ):
            wordCountMSB = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 0x25)[1]
            wordCountLSB = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 0x26)[1]
            mipiWordCount = ((wordCountMSB & 0xFF) << 8) | (wordCountLSB & 0xFF)
            mipiData["mipiWordCount"] = str(mipiWordCount)

        if date >= (21 * 1000 + 6 * 100 + 22):
            fpsMSB = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 0x2A)[1]
            fpsLSB = ArducamSDK.Py_ArduCam_readReg_8_8(self.handle, 0x46, 0x2B)[1]
            fps = (fpsMSB << 8 | fpsLSB) / 4.0
            fpsResult = "{:.1f}".format(fps)
            mipiData["mFramerateValue"] = fpsResult
        return mipiData


def GetErrorString(ErrorCode):
    return ErrorCode_Map[ErrorCode]


def configBoard(handle, config):
    ArducamSDK.Py_ArduCam_setboardConfig(
        handle,
        config.params[0],
        config.params[1],
        config.params[2],
        config.params[3],
        config.params[4 : config.params_length],
    )


def camera_initFromFile(fileName, index):
    # load config file
    config = arducam_config_parser.LoadConfigFile(fileName)

    camera_parameter = config.camera_param.getdict()
    width = camera_parameter["WIDTH"]
    height = camera_parameter["HEIGHT"]

    BitWidth = camera_parameter["BIT_WIDTH"]
    ByteLength = 1
    if BitWidth > 8 and BitWidth <= 16:
        ByteLength = 2

    FmtMode = camera_parameter["FORMAT"][0]
    color_mode = camera_parameter["FORMAT"][1]

    print("color mode", color_mode)

    I2CMode = camera_parameter["I2C_MODE"]
    I2cAddr = camera_parameter["I2C_ADDR"]
    TransLvl = camera_parameter["TRANS_LVL"]

    cfg = {
        "u32CameraType": 0x00,
        "u32Width": width,
        "u32Height": height,
        "usbType": 0,
        "u8PixelBytes": ByteLength,
        "u16Vid": 0,
        "u32Size": 0,
        "u8PixelBits": BitWidth,
        "u32I2cAddr": I2cAddr,
        "emI2cMode": I2CMode,
        "emImageFmtMode": FmtMode,
        "u32TransLvl": TransLvl,
    }

    ret, handle, rtn_cfg = ArducamSDK.Py_ArduCam_open(cfg, index)
    # ret, handle, rtn_cfg = ArducamSDK.Py_ArduCam_autoopen(cfg)
    if ret == 0:
        # ArducamSDK.Py_ArduCam_writeReg_8_8(handle,0x46,3,0x00)
        usb_version = rtn_cfg["usbType"]
        configs = config.configs
        configs_length = config.configs_length
        for i in range(configs_length):
            type = configs[i].type
            if ((type >> 16) & 0xFF) != 0 and ((type >> 16) & 0xFF) != usb_version:
                continue
            if type & 0xFFFF == arducam_config_parser.CONFIG_TYPE_REG:
                ArducamSDK.Py_ArduCam_writeSensorReg(
                    handle, configs[i].params[0], configs[i].params[1]
                )
            elif type & 0xFFFF == arducam_config_parser.CONFIG_TYPE_DELAY:
                time.sleep(float(configs[i].params[0]) / 1000)
            elif type & 0xFFFF == arducam_config_parser.CONFIG_TYPE_VRCMD:
                configBoard(handle, configs[i])

        ArducamSDK.Py_ArduCam_registerCtrls(
            handle, config.controls, config.controls_length
        )

        rtn_val, datas = ArducamSDK.Py_ArduCam_readUserData(handle, 0x400 - 16, 16)
        print(
            "Serial: %c%c%c%c-%c%c%c%c-%c%c%c%c"
            % (
                datas[0],
                datas[1],
                datas[2],
                datas[3],
                datas[4],
                datas[5],
                datas[6],
                datas[7],
                datas[8],
                datas[9],
                datas[10],
                datas[11],
            )
        )

        return (True, handle, rtn_cfg, color_mode)

    print("open fail, Error : {}".format(GetErrorString(ret)))
    return (False, handle, rtn_cfg, color_mode)
