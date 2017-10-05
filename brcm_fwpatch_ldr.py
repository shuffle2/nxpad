from fw import FwParser
import idaapi, idc, ida_auto, ida_kernwin, ida_diskio

ram_loaded = 0

def accept_file(li, n):
    # If loader does not show up, comment the following line
    if n > 0: return 0
    try:
        parser = FwParser(li)
        if len(parser.fw[0]) > 0:
            return "Broadcom PatchRAM and Firmware loader"
    except:
        pass
    return 0

def make_seg(addr_range, record_type = 0):
        seg = idaapi.segment_t()
        seg.bitness = 1 # 32bit
        seg.startEA = addr_range[0]
        seg.endEA = addr_range[1]
        seg.perm = idaapi.SEGPERM_READ | idaapi.SEGPERM_WRITE | idaapi.SEGPERM_EXEC
        seg.type = idaapi.SEG_CODE
        seg.align = idaapi.saRelByte
        # Force regions to be CODE
        if record_type == 1:
            idaapi.add_segm_ex(seg, 'ROM', 'CODE', idaapi.ADDSEG_NOSREG)
        else:
            idaapi.add_segm_ex(seg, 'RAM', 'CODE', idaapi.ADDSEG_NOSREG)

def load_bin_file(load_off = 0x0, prompt_text = "Choose binary file"):
    bin_filename = ida_kernwin.askfile_c(0, "*.*", prompt_text);
    li_bin = ida_diskio.open_linput(bin_filename, False);
    status = ida_loader.load_binary_file(bin_filename, li_bin, NEF_CODE, 0, 0, load_off, 0);
    global ram_loaded
    if status is True:
        msg("Successfully loaded %s @ 0x%08X\n" % (bin_filename, load_off));
        if load_off == 0xD0000:
            ram_loaded = 1
        elif load_off == 0x200000 and ram_loaded == 1:
            ram_loaded = 2
        elif load_off == 0x200000 and ram_loaded == 0:
            ram_loaded = 1
    else:
        msg("Failed to load file.\n");

def load_file(li, neflags, fmt):
    # Assume BCM20734 == cortex-m3
    idaapi.set_processor_type('arm:armv7-m', idaapi.SETPROC_ALL | idaapi.SETPROC_FATAL)

    parser = FwParser(li)

    fw_index = parser.active_fw
    if len(parser.fw) > 1:
        msg = ['SPI dump has more than one PatchRAM image.\n\nEnter the index of the one to load:']
        for i in range(len(parser.fw)):
            if parser.fw_present(i):
                msg.append('%i @ 0x%08x %s' % (i, parser.fw_offsets[i],
                    '[active]' if i == parser.active_fw else ''))
        fw_index = ida_kernwin.asklong(parser.active_fw, '\n'.join(msg))

    # Create known memory regions
    make_seg([0x0, 0xC8000], 1)
    make_seg([0x260000, 0x26C000], 1)
    make_seg([0xD0000, 0xE0000])
    make_seg([0x200000, 0x248000])
    load_bin_file(0x0, "Choose ROM 1 (@0x000000)")
    load_bin_file(0x260000, "Choose ROM 2 (@0x260000)")
    load_bin_file(0xD0000, "Choose RAM_LO (@0x0D0000)")
    load_bin_file(0x200000, "Choose RAM_HI (@0x200000)")

    # The PatchRAM changes will show up as patched bytes
    load_rampatch = 0
    if ram_loaded == 0:
        load_rampatch = ida_kernwin.askbuttons_c('Yes', 'No', 'Not sure', 1,'Do you want to patch ROM 1 and RAM regions with the provided PatchRAM?\n\n')
        if load_rampatch == 1:
            print('Patching ROM1, RAM_LO and RAM_HI:')
            parser.process({0x08 : lambda r: idaapi.patch_many_bytes(r.addr, r.data), 0x0a : lambda r: idaapi.patch_many_bytes(r.addr, r.data)}, fw_index)
            print('ROM 1, RAM_LO and RAM_HI regions were patched.')
    elif ram_loaded == 1:
        print('Patching ROM1:')
        parser.process({0x08 : lambda r: idaapi.patch_many_bytes(r.addr, r.data)}, fw_index)
        print('Only one RAM region loaded. ROM 1 was patched.')
    elif ram_loaded == 2:
        load_rampatch = ida_kernwin.askbuttons_c('Yes', 'No', 'Not sure', 0,'RAM_LO and RAM_HI were loaded.\n\nDo you want to patch them with the provided PatchRAM?\n\n')
        if load_rampatch == -1 or load_rampatch == 0:
            print('Patching ROM1:')
            parser.process({0x08 : lambda r: idaapi.patch_many_bytes(r.addr, r.data)}, fw_index)
            print('RAM_LO and RAM_HI loaded. ROM 1 was patched.')
        elif load_rampatch == 1:
            print('Patching ROM1, RAM_LO and RAM_HI:')
            parser.process({0x08 : lambda r: idaapi.patch_many_bytes(r.addr, r.data), 0x0a : lambda r: idaapi.patch_many_bytes(r.addr, r.data)}, fw_index)
            print('RAM_LO and RAM_HI loaded. ROM 1 and both RAM regions were patched.')

    # Code is THUMB only
    idc.SetReg(0x0, 't', 1)

    return 1
