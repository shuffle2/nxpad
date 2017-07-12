'''
After using script, use analyzer to force the entire region to be code...
'''
from fw import FwParser
import idaapi, idc, ida_auto

def accept_file(li, n):
    if n > 0: return 0
    try:
        parser = FwParser(li)
        if len(parser.chunks) > 0:
            return "Broadcom patchram firmware loader"
    except:
        pass
    return 0

def make_seg(addr_range):
    seg = idaapi.segment_t()
    seg.bitness = 1 # 32bit
    seg.startEA = addr_range[0]
    seg.endEA = addr_range[1]
    seg.perm = idaapi.SEGPERM_READ | idaapi.SEGPERM_WRITE | idaapi.SEGPERM_EXEC
    seg.type = idaapi.SEG_CODE
    # use bss to tell what is not patched
    idaapi.add_segm_ex(seg, 'patchram', 'BSS', idaapi.ADDSEG_NOSREG)

def load_file(li, neflags, fmt):
    # Assume BCM20734 == cortex-m3
    idaapi.set_processor_type('arm:armv7-m', idaapi.SETPROC_ALL | idaapi.SETPROC_FATAL)

    parser = FwParser(li)

    addr_range = [0xffffffff, 0]
    def update_addr_range(r):
        addr_range[0] = min(r.addr, addr_range[0])
        addr_range[1] = max(r.addr, addr_range[1])
    parser.process({0x0a : update_addr_range})
    make_seg(addr_range)
    idc.SetReg(addr_range[0], 't', 1)

    parser.process({0x0a : lambda r: idaapi.put_many_bytes(r.addr, r.data)})

    return 1
