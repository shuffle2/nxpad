.cpu cortex-m3
.syntax unified
.thumb

@ handle_sflash_read originally writes response back here
.equ response_buffer, 0x222a24

@ handle_sflash_erase(void* thing, u8 *pkt)
.org 0x21D4CA

push    {r4-r6, lr}
ldr     r3, =response_buffer
mov     r0, 0x90                    @ cmd
strb    r0, [r3, 13]
mov     r0, 0x10                    @ len
strb    r0, [r3, 19]
ldr     r0, [r1, 11]               @ addr
str     r0, [r3, 15]

ldr     r2, [r0]
str     r2, [r3, 20 + 0]
ldr     r2, [r0, 4]
str     r2, [r3, 20 + 4]
ldr     r2, [r0, 8]
str     r2, [r3, 20 + 8]
ldr     r2, [r0, 12]
str     r2, [r3, 20 + 12]

movs    r0, 0
pop     {r4-r6, pc}
