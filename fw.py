from construct import *
import binascii
import struct

OTA_MAGIC = binascii.unhexlify('AA55F00F68E597D2')

class FwParser:
    chunk_t = Struct('chunk',
        ULInt8('record_type'),
        ULInt16('size'),
        Bytes('data', lambda c: c.size)
    )
    def __init__(s, f):
        s.parsers = {
            0x08 : s.parse_8,
            0x0a : s.parse_a,
            0x0b : s.parse_b,
        }
        f.seek(0x3b3)
        s.fw_offsets = [struct.unpack('<L', f.read(4))[0]]
        s.active_fw = 0
        
        f.seek(0x1ff4)
        ds1_magic = f.read(8)
        if ds1_magic == OTA_MAGIC:
            s.active_fw = 1
            s.fw_offsets.append(struct.unpack('<L', f.read(4))[0])
        
        s.fw = []
        for offset in s.fw_offsets:
            f.seek(offset)
            if f.read(3) == b'\xff\xff\xff':
                s.fw.append([])
                continue
            f.seek(offset)
            s.fw.append(RepeatUntil(lambda obj, ctx: obj.record_type == 0xfe,
                s.chunk_t).parse_stream(f))
    def print_chunk(s, chunk):
        print('%02X[raw]: %s' % (chunk.record_type, binascii.hexlify(chunk.data)))
    def fw_present(s, index):
        return index < len(s.fw) and len(s.fw[index]) > 1
    def process(s, handlers, fw_index = None, verbose = 1):
        if fw_index is None:
            fw_index = s.active_fw
        for chunk in s.fw[fw_index]:
            # Only unknown
            if verbose == 1 and chunk.record_type not in handlers:
                s.print_chunk(chunk)
            # Full
            elif verbose == 2:
                s.print_chunk(chunk)
            if chunk.record_type in handlers:
                parsed = chunk.data
                if chunk.record_type in s.parsers:
                    parsed = s.parsers[chunk.record_type](chunk.data)
                handlers[chunk.record_type](parsed)
    def parse_8(s, data):
        return Struct('rec_8',
            ULInt8('index'),
            ULInt32('addr'),
            Bytes('data', 4),
            ULInt16('unk1'),
            ULInt16('unk2'),
            # Size of data after header. If 0, unk2 is 0 and data is still patched
            ULInt16('body_size')
        ).parse(data)
    def parse_a(s, data):
        return Struct('rec_a',
            ULInt32('addr'),
            Bytes('data', len(data) - 4)
        ).parse(data)
    def parse_b(s, data):
        return Struct('rec_b',
            ULInt32('addr')
        ).parse(data)
