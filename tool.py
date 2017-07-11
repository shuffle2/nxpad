import usb.core
import usb.util
import array
import struct
import sys
import binascii
import time
from construct import *

class ProController:
    USB_BUF_LEN = 64
    # pro controller, app fw
    DEV_ID = (0x057E, 0x2009)
    # pro controller, bl fw
    DEV_ID_BL = (0x057E, 0x200f)
    def __init__(s):
        s.wait_for_device(s.DEV_ID)

    def wait_for_device(s, dev_id):
        s.dev = usb.core.find(idVendor=dev_id[0], idProduct=dev_id[1])
        while s.dev is None:
            time.sleep(1)
            s.dev = usb.core.find(idVendor=dev_id[0], idProduct=dev_id[1])

    # fw does actually seem to support sending these cmds via ep0 under some condition,
    # but using a nonzero ep makes it more simple.
    def usb_write(s, cmd): return s.dev.write(1 | usb.util.ENDPOINT_OUT, cmd)
    def usb_read_all(s):
        try:
            return s.dev.read(1 | usb.util.ENDPOINT_IN, s.USB_BUF_LEN, 200)
        except usb.core.USBError:
            return array.array('B', [0] * s.USB_BUF_LEN)
    class UsbResponse:
        def __init__(s, pkt, data_len):
            #print('pkt: %s' % (binascii.hexlify(pkt)))
            s.cmd_type = pkt[0]
            s.cmd = pkt[1]
            s.status = pkt[2]
            s.data = pkt[3 : 3 + data_len]
    def usb_cmd(s, cmd, resp_len = USB_BUF_LEN):
        s.usb_write(cmd)
        if resp_len == 0: return None
        resp = None
        while True:
            resp = s.UsbResponse(s.usb_read_all(), resp_len)
            if resp.cmd_type == cmd[0] | 1 and resp.cmd == cmd[1]:
                break
            
            # app mainloop resets usb and sends empty device_id_response in case of error...
            # need to check for that specficially and give up.
            if (resp.cmd_type, resp.cmd) == (0x81, 0x01) and resp.status != 0:
                return None
            # fw may respond with old data (e.g. if it's going through reset), so
            # we simply resend cmd until a decently-related looking response comes back.
            # fw could also be throwing us a lot of uart spew, which we want to skip.
            s.usb_write(cmd)
        if resp.status != 0:
            print('resp %02x:%02x error %x' % (resp.cmd_type, resp.cmd, resp.status))
        return resp.data

    # returns device_id_response
    def cmd_80_01(s): return s.usb_cmd([0x80, 0x01], 8)
    # returns static 4 bytes
    def cmd_80_07(s): return s.usb_cmd([0x80, 0x07], 4)
    # returns field_1B5
    def cmd_80_08(s): return s.usb_cmd([0x80, 0x08], 1)
    # set HSITRIM, returns new HSICAL
    # see STM DocID15965
    def cmd_80_a0(s, hsi_trim): return s.usb_cmd([0x80, 0xa0, hsi_trim & 0x1f], 1)

    # set or clear comms_running. returns True if change was made successfully.
    def cmd_80_02(s): return s.usb_cmd([0x80, 0x02]) is not None
    def cmd_80_03(s): return s.usb_cmd([0x80, 0x03]) is not None
    # set or clear poll_enabled. if comms_running, will start relaying uart data out usb
    def cmd_80_04(s): s.usb_cmd([0x80, 0x04], 0)
    def cmd_80_05(s): s.usb_cmd([0x80, 0x05], 0)
    # resets uart comms and usb state
    # returns True if it was stopped (else it probably wasn't running)
    def cmd_80_06(s): return s.usb_cmd([0x80, 0x06]) is not None

    # forwards the encapsulated uart cmd
    def cmd_80_91(s): return s.usb_cmd([0x80, 0x91])
    def cmd_80_92(s): return s.usb_cmd([0x80, 0x92])
    # forwards as uart cmd 92_00.
    # Note response buffer is from uart (may not match cmd_type/cmd?)
    # Note cmds are only processed if comms_running
    def cmd_01(s): return s.usb_cmd([0x01])
    def cmd_10(s): return s.usb_cmd([0x10])

    def reacquire_device(s, dev_id):
        time.sleep(1)
        s.wait_for_device(dev_id)

    # note these apply to STM only
    # erases eeprom@0 and resets
    def enter_dfu_and_reset(s):
        print('do not enter dfu unless you have a fw image to flash')
        return
        s.usb_cmd([0x82, 1], 0)
        s.reacquire_device(s.DEV_ID_BL)
    # just resets
    def reset(s):
        s.usb_cmd([0x82, 2], 0)
        s.reacquire_device(s.DEV_ID)

    def uart_forward(s, cmd, subcmd, buf):
        # fw will calculate crcs for us
        hdr = Struct('uart_crc_hdr',
            ULInt8('cmd'),
            ULInt8('subcmd'),
            ULInt16('trailing_len'),
            ULInt8('error'),
            ULInt8('crc_data'),
            ULInt8('crc_hdr')
        ).build(Container(
            cmd = cmd,
            subcmd = subcmd,
            trailing_len = len(buf),
            error = 0,
            crc_data = 0,
            crc_hdr = 0,
            )
        )
        return s.usb_cmd(struct.pack('B', 0x80) + hdr + buf)

    def brcm_cmd_01(s, subcmd, buf):
        hdr = Struct('brcm_hdr',
            ULInt8('cmd'),
            Bytes('rumble_base', 9),
            ULInt8('subcmd'),
        ).build(Container(
            cmd = 0x01,
            rumble_base = bytes([0x00, 0x00, 0x01, 0x40, 0x40, 0x00, 0x01, 0x40, 0x40]),
            subcmd = subcmd,
            )
        )
        return s.uart_forward(0x92, 0x00, hdr + buf)

    def brcm_spi_read(s, offset, size):
        buf = Struct('spi_read_cmd',
            ULInt32('offset'),
            ULInt8('size'),
            Padding(0x20)
        ).build(Container(offset = offset, size = size))
        return s.brcm_cmd_01(0x10, buf)

    def brcm_spi_dump(s, fname):
        dump = []
        SPI_FLASH_SIZE = 0x80000
        MAX_SPI_XFER = 0x1d
        offset = 0
        while offset < SPI_FLASH_SIZE:
            # +0x16 looks like it might be a spi_read_cmd, but offset is
            # always 0 and size is always 0x20...
            resp_offset = 0x16 + 4 + 1
            read_len = min(MAX_SPI_XFER, SPI_FLASH_SIZE - offset)
            data = s.brcm_spi_read(offset, read_len)[resp_offset:resp_offset+read_len]
            offset += read_len
            dump.append(data)
            print('%4x %s' % (offset, binascii.hexlify(data)))
        with open(fname, 'wb') as f:
            f.write(b''.join(dump))

'''
c = ProController()
print(binascii.hexlify(c.cmd_80_08()))
print(binascii.hexlify(c.cmd_80_07()))
print(binascii.hexlify(c.cmd_80_01()))
c.cmd_80_02()
#c.cmd_80_04()
#'''
'''
i = 0
while True:
    buf = c.dev.read(1|usb.util.ENDPOINT_IN, c.USB_BUF_LEN)
    print(binascii.hexlify(buf))
    if i == 100:
        break
    i += 1
#'''

buf = open('./pro_brcm_patchflash.fw0.bin', 'rb').read()
o = 0
while o < len(buf):
    chunk_type = struct.unpack('B', buf[o:o+1])[0]
    o += 1
    chunk_len = struct.unpack('<H', buf[o:o+2])[0]
    o += 2
    chunk = buf[o:o+chunk_len]
    verbose = True
    print('%5x: %02x %04x' % (o - 3, chunk_type, chunk_len), end='' if verbose else '\n')
    if verbose: print(' %s' % (binascii.hexlify(chunk)))
    
    if chunk_type == 0xfe and chunk_len == 0:
        print('end')
        break
    elif chunk_type == 0x08:
        # <u8 index?><u8[6] unknown><u32 unk><u32 addr>
        # maybe some sort of thunk/reloc?
        index, unk1, unk2, unk3, unk4, addr = struct.unpack('<B3HLL', chunk)
        print('%2x %4x %4x %4x %8x %8x' % (index, unk1, unk2, unk3, unk4, addr))
    elif chunk_type == 0x0b:
        # <u32 addr>
        addr = struct.unpack('<L', chunk)[0]
        print('%8x' % (addr))
    elif chunk_type == 0x0a:
        # <u32 addr><data...>
        addr = struct.unpack('<L', chunk[:4])[0]
        print('%8x:%8x' % (addr, addr+len(chunk[4:])))

    o += chunk_len