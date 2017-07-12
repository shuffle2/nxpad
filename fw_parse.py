from fw import FwParser
import binascii

def print_rec_8(rec):
    print('08: %2x %4x %4x %4x %8x %8x' % (rec.index, rec.unk1, rec.unk2,
        rec.unk3, rec.unk4, rec.addr))
def print_rec_a(rec):
    print('0a: %8x:%8x %s' % (rec.addr, rec.addr + len(rec.data),
        binascii.hexlify(rec.data)))
def print_rec_b(rec):
    print('0b: %8x' % (rec.addr))
def print_rec_fe(rec):
    print('end')

parser = FwParser('./pro_brcm_flash.bin')
parser.process({
    0x08 : print_rec_8,
    0x0a : print_rec_a,
    0x0b : print_rec_b,
    0xfe : print_rec_fe,
})
