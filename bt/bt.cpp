#include <cstdint>
#include <cstdio>
#include <functional>
#include <memory>
#define NOMINMAX
#include <Windows.h>
#include "hidapi.h"

//#pragma comment(lib, "hid")
#pragma comment(lib, "SetupAPI")

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int8_t s8;
typedef int16_t s16;
typedef int32_t s32;
typedef int64_t s64;

#pragma pack(push, 1)

struct brcm_hdr {
	u8 cmd;
	u8 unknown[9];
};

struct brcm_cmd_01 {
	u8 cmd;
	union {
		// cmd 0x10
		struct {
			u32 offset;
			u8 size;
		} spi_read;
		// cmd 0x12, overwritten spi_erase
		struct {
			u32 address;
		} hax_read;
	};
};

#pragma pack(pop)

void dump_flash(hid_device *handle) {
	int res;
	u8 buf[0x100];
	const u16 read_len = 0x1d;
	u32 offset = 0;
	while (offset < 0x80000) {
		memset(buf, 0, sizeof(buf));
		auto hdr = (brcm_hdr *)buf;
		auto pkt = (brcm_cmd_01 *)(hdr + 1);
		hdr->cmd = 1;
		pkt->cmd = 0x10;
		pkt->spi_read.offset = offset;
		pkt->spi_read.size = read_len;
		res = hid_write(handle, buf, sizeof(*hdr) + sizeof(*pkt));
		//printf("write %d\n", res);
		res = hid_read(handle, buf, sizeof(buf));
		//printf("read %8x: %d %02x\n", pkt->spi_read.offset, res, buf[0]);
		if (res >= 0x14 + read_len) {
			for (int i = 0; i < read_len; i++) {
				printf("%02x ", buf[0x14 + i]);
			}
			puts("");
		}
		offset += read_len;
	}
}

void dump_rom(hid_device *handle) {
	FILE *f = fopen("./rom.bin", "wb");
	int res;
	u8 buf[0x100];
	const u16 read_len = 0x10;
	u32 offset = 0;
	while (offset < 0xc8000) {
		memset(buf, 0, sizeof(buf));
		auto hdr = (brcm_hdr *)buf;
		auto pkt = (brcm_cmd_01 *)(hdr + 1);
		hdr->cmd = 1;
		pkt->cmd = 0x12;
		pkt->hax_read.address = offset;
		res = hid_write(handle, buf, sizeof(*hdr) + sizeof(*pkt));
		if (res < 0) {
			printf("write %d\n", res);
			break;
		}
		res = hid_read(handle, buf, sizeof(buf));
		if (res < 0) {
			printf("read %8x: %d %02x\n", pkt->spi_read.offset, res, buf[0]);
			break;
		}
		if (res >= 0x14 + read_len) {
			for (int i = 0; i < read_len; i++) {
				printf("%02x ", buf[0x14 + i]);
			}
			puts("");
		}
		fwrite(&buf[0x14], read_len, 1, f);
		offset += read_len;
	}
	fclose(f);
}

int main() {
	// pro controller, bt app fw
	//return attr.VendorID == 0x57e && attr.ProductID == 0x2009;
	// joycon(L) controller, bt app fw
	//return attr.VendorID == 0x57e && attr.ProductID == 0x2006;
	hid_device *handle = hid_open(0x57e, 0x2006, nullptr);
	if (!handle) {
		return 1;
	}

	//dump_flash(handle);
	// !!DO NOT USE THIS UNLESS YOU HAVE PATCHED FLASH. OTHERWISE CMD 0x12 ERASES FLASH!!
	//dump_rom(handle);

	return 0;
}
