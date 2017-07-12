from construct import *
import binascii
import struct

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
        ds0_offset = struct.unpack('<L', f.read(4))[0]
        f.seek(ds0_offset)
        s.chunks = RepeatUntil(lambda obj, ctx: obj.record_type == 0xfe,
            s.chunk_t).parse_stream(f)
    def print_chunk(s, chunk):
        print('%02x[raw]: %s' % (chunk.record_type, binascii.hexlify(chunk.data)))
    def process(s, handlers, verbose = False):
        for chunk in s.chunks:
            if verbose or chunk.record_type not in handlers:
                s.print_chunk(chunk)
            if chunk.record_type in handlers:
                parsed = chunk.data
                if chunk.record_type in s.parsers:
                    parsed = s.parsers[chunk.record_type](chunk.data)
                handlers[chunk.record_type](parsed)
    def parse_8(s, data):
        # maybe some sort of thunk/reloc?
        return Struct('rec_8',
            ULInt8('index'),
            ULInt16('unk1'),
            ULInt16('unk2'),
            ULInt16('unk3'),
            ULInt32('unk4'),
            ULInt32('addr')
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
