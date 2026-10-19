# Code of the .p16 section that tools/port2016.py adds to Client US/DriftCityUS.exe (VA 0xa1e000), so the 2011 client
# keeps VisualItem records for car Unique Ids up to 511 (2011: 299). Built once with GNU binutils:
#   as --32 -o p16.o p16_cars.s && ld -m elf_i386 -Ttext=0xa1e000 --oformat binary -o p16.bin p16.o
# port2016.py holds the resulting bytes (P16_CODE) and checks them against this file when binutils are there.
#
# VisualItem record (0x27c bytes instead of 0x1ac): +0 category, +4 serial, +8 id string, +0x30 / +0x54 strings,
# +0x50 item id, +0x7c + car Unique Id: the item fits that car (1), +0x1a8 float (the tire size of "T" items, set by
# 0x84c5e0) - so Unique Ids 300-303 must not be used (they would share bytes with the float).
        .intel_syntax noprefix
        .equ    MAXCOLS, 1024
        .equ    MAXUID, 0x200
        .equ    RECSIZE, 0x27c
        .text
        .globl _start
_start:

# ---- LoadVisualItemList (0x84ad00 jumps here): cdecl (file name, the VisualItem manager) -----------------------------
# As the original (DA_Init, header, the column -> Unique Id row, then per row: columns 1-6, the car columns, 0x84c5e0,
# manager->vtbl[1](category - 1, &record)), with the column map and the record in this section (1024 columns,
# 0x27c-byte record) instead of on the stack (300 columns, 0x1ac).
load_visual_items:
        push    ebp
        mov     ebp, esp
        push    ebx
        push    esi
        push    edi
        push    dword ptr [ebp+8]
        mov     eax, 0x8497e0           # DA_Init
        call    eax
        add     esp, 4
        mov     esi, eax
        test    esi, esi
        jge     1f
        push    0x8f988c                # "Init/VisualItem - Open FAILED!!!"
        push    1
        mov     eax, 0x402c30           # DbgTo
        call    eax
        add     esp, 8
1:      xor     eax, eax
        mov     ecx, MAXCOLS
        lea     edi, colmap
        rep     stosd
        mov     dword ptr rows, 0
        mov     dword ptr cols, 0
        push    offset cols
        push    offset rows
        push    0x8ccb18
        push    esi
        mov     eax, 0x848ec0           # header: row count, car column count
        call    eax
        add     esp, 16
        xor     edi, edi
2:      cmp     edi, dword ptr cols
        jge     3f
        cmp     edi, MAXCOLS
        jge     3f
        mov     dword ptr tmp, 0
        push    offset tmp
        push    0x8cb178                # "%d"
        lea     ecx, [edi+7]
        push    ecx
        push    esi
        mov     eax, 0x849080           # read a column of the current row
        call    eax
        add     esp, 16
        mov     edx, dword ptr tmp
        mov     dword ptr [colmap+edi*4], edx
        inc     edi
        jmp     2b
3:      push    4
        push    esi
        mov     eax, 0x848e50           # to the first item row
        call    eax
        add     esp, 8
        mov     dword ptr row, 0
4:      mov     eax, dword ptr row
        cmp     eax, dword ptr rows
        jge     9f
        xor     eax, eax
        mov     ecx, RECSIZE / 4
        lea     edi, rec
        rep     stosd
        mov     dword ptr [rec+0x1a8], 0xbf800000
        push    offset rec
        push    0x8cb178
        push    1
        push    esi
        mov     eax, 0x849080
        call    eax
        push    offset rec+4
        push    0x8cb178
        push    2
        push    esi
        mov     eax, 0x849080
        call    eax
        push    offset rec+0x30
        push    0x8cb428                # "%s"
        push    3
        push    esi
        mov     eax, 0x849080
        call    eax
        push    offset rec+0x50
        push    0x8d85e8
        push    4
        push    esi
        mov     eax, 0x849080
        call    eax
        add     esp, 0x40
        push    offset rec+0x54
        push    0x8cb428
        push    5
        push    esi
        mov     eax, 0x849080
        call    eax
        mov     byte ptr [rec+0x7b], 0
        push    offset rec+8
        push    0x8cb428
        push    6
        push    esi
        mov     eax, 0x849080
        call    eax
        add     esp, 0x20
        xor     edi, edi
5:      cmp     edi, dword ptr cols
        jge     6f
        cmp     edi, MAXCOLS
        jge     6f
        mov     dword ptr tmp, 0
        push    offset tmp
        push    0x8cb178
        lea     ecx, [edi+7]
        push    ecx
        push    esi
        mov     eax, 0x849080
        call    eax
        add     esp, 16
        mov     edx, dword ptr [colmap+edi*4]
        cmp     edx, MAXUID
        jae     55f
        mov     al, byte ptr tmp
        mov     byte ptr [rec+0x7c+edx], al
55:     inc     edi
        jmp     5b
6:      lea     ecx, rec
        mov     eax, 0x84c5e0           # the record's float (+0x1a8) from its id
        call    eax
        mov     ecx, dword ptr [ebp+0xc]
        mov     edx, dword ptr [ecx]
        push    offset rec
        mov     eax, dword ptr rec
        dec     eax
        push    eax
        call    dword ptr [edx+4]       # manager: add the record to its category (copies RECSIZE bytes)
        push    1
        push    esi
        mov     eax, 0x848e50           # next row
        call    eax
        add     esp, 8
        inc     dword ptr row
        jmp     4b
9:      push    esi
        mov     eax, 0x849ad0           # close
        call    eax
        add     esp, 4
        pop     edi
        pop     esi
        pop     ebx
        pop     ebp
        ret

# ---- the default part cache getter 0x769080 (thiscall (uid, category), ret 8) jumps here for its uid check ----------
# The cache (manager +0x710) holds 300 x 56 entries; Unique Ids 300-511 are looked up directly (0x7694e0).
cache_get:
        cmp     eax, 0x12c
        jge     1f
        push    0x76908f                # back to the cached path
        ret
1:      cmp     eax, MAXUID
        jge     8f
        mov     edx, dword ptr [esp+8]
        test    edx, edx
        jl      8f
        cmp     edx, 0x37
        jg      8f
        push    edx
        push    eax
        mov     eax, 0x7694e0           # FindDefaultPart(uid, category) -> record or 0
        call    eax
        test    eax, eax
        jz      8f
        mov     eax, dword ptr [eax+4]
        ret     8
8:      xor     eax, eax
        ret     8

        .balign 16, 0
rows:   .long   0
cols:   .long   0
row:    .long   0
tmp:    .long   0
        .balign 16, 0
rec:    .space  RECSIZE
        .balign 16, 0
colmap: .space  MAXCOLS * 4
