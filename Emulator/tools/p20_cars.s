# Code of the .p20 section that tools/carlimit2016.py adds to the 2016 client (DriftCity Dev Ed/DriftCity.exe, VA
# 0xaf9000), so the client accepts car Unique Ids up to 1999 (2016: 449). Built with GNU binutils:
#   as --32 -o p20.o p20_cars.s && ld -m elf_i386 -Ttext=0xaf9000 --oformat binary -o p20.bin p20.o
# carlimit2016.py holds the resulting bytes (P20_CODE) and checks them against this file when binutils are there.
#
# The 2016 VisualItem record (0x248 bytes, LoadVisualItemList 0x8b6570): +0 category, +4 serial, +8 id string, +0x30 /
# +0x54 strings, +0x50 item id, +0x7c + car Unique Id: the item fits that car (1) for Ids 0-449, +0x240 float (the tire
# size of "T" items, set by 0x8b9670). The client copies these records by value (0x92 dwords) into other objects, so
# the record keeps its size. Bytes +0x23e / +0x23f were never read (Ids 450 / 451 fail every Id check): they now hold
# the record's row number + 1 (u16), and the fit flags of Ids 450-1999 are one bit each in `ext` (200 bytes per row).
        .intel_syntax noprefix
        .equ    MAXCOLS, 2048           # car columns of VisualItem.xlt
        .equ    OLDUID, 450             # Ids below this keep their byte in the record
        .equ    MAXUID, 2000
        .equ    EXTBITS, MAXUID - OLDUID
        .equ    EXTROW, 200             # bytes of ext per row (1600 bits)
        .equ    MAXROWS, 16384          # VisualItem rows that can have ext bits
        .equ    RECSIZE, 0x248
        .equ    ROWIDX, 0x23e
        .text
        .globl _start
_start:

# ---- LoadVisualItemList (0x8b6570 jumps here): cdecl (file name, the VisualItem manager) -----------------------------
# As the original (DA_Init, header, the column -> Unique Id row, then per row: columns 1-6, the car columns, 0x8b9670,
# manager->vtbl[1](category - 1, &record)), with the column map and the record in this section instead of on the
# stack (450 columns), a bound on the Unique Id (the original wrote record +0x7c + Id unchecked) and the ext bits.
load_visual_items:
        push    ebp
        mov     ebp, esp
        push    ebx
        push    esi
        push    edi
        push    dword ptr [ebp+8]
        mov     eax, 0x8b4fb0           # DA_Init
        call    eax
        add     esp, 4
        mov     esi, eax
        test    esi, esi
        jge     1f
        push    0x97c5b8                # "Init/VisualItem - Open FAILED!!!"
        push    1
        mov     eax, 0x402b70           # DbgTo
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
        push    0x948464
        push    esi
        mov     eax, 0x8b4690           # header: row count, car column count
        call    eax
        add     esp, 16
        xor     edi, edi
2:      cmp     edi, dword ptr cols
        jge     3f
        cmp     edi, MAXCOLS
        jge     3f
        mov     dword ptr tmp, 0
        push    offset tmp
        push    0x9469b0                # "%d"
        lea     ecx, [edi+7]
        push    ecx
        push    esi
        mov     eax, 0x8b4850           # read a column of the current row
        call    eax
        add     esp, 16
        mov     edx, dword ptr tmp
        mov     dword ptr [colmap+edi*4], edx
        inc     edi
        jmp     2b
3:      push    4
        push    esi
        mov     eax, 0x8b4520           # to the first item row
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
        mov     dword ptr [rec+0x240], 0xbf800000
        push    offset rec
        push    0x9469b0
        push    1
        push    esi
        mov     eax, 0x8b4850
        call    eax
        push    offset rec+4
        push    0x9469b0
        push    2
        push    esi
        mov     eax, 0x8b4850
        call    eax
        push    offset rec+0x30
        push    0x946cd4                # "%s"
        push    3
        push    esi
        mov     eax, 0x8b4850
        call    eax
        push    offset rec+0x50
        push    0x955270
        push    4
        push    esi
        mov     eax, 0x8b4850
        call    eax
        add     esp, 0x40
        push    offset rec+0x54
        push    0x946cd4
        push    5
        push    esi
        mov     eax, 0x8b4850
        call    eax
        mov     byte ptr [rec+0x7b], 0
        push    offset rec+8
        push    0x946cd4
        push    6
        push    esi
        mov     eax, 0x8b4850
        call    eax
        add     esp, 0x20
        mov     ebx, dword ptr row      # ebx: this row's ext bits, or 0 (too many rows)
        cmp     ebx, MAXROWS
        jb      41f
        xor     ebx, ebx
        jmp     42f
41:     lea     eax, [ebx+1]
        mov     word ptr [rec+ROWIDX], ax
        imul    ebx, ebx, EXTROW
        add     ebx, offset ext
        push    edi
        xor     eax, eax
        mov     ecx, EXTROW / 4
        mov     edi, ebx
        rep     stosd
        pop     edi
42:     xor     edi, edi
5:      cmp     edi, dword ptr cols
        jge     6f
        cmp     edi, MAXCOLS
        jge     6f
        mov     dword ptr tmp, 0
        push    offset tmp
        push    0x9469b0
        lea     ecx, [edi+7]
        push    ecx
        push    esi
        mov     eax, 0x8b4850
        call    eax
        add     esp, 16
        mov     edx, dword ptr [colmap+edi*4]
        cmp     edx, OLDUID
        jae     51f
        mov     al, byte ptr tmp
        mov     byte ptr [rec+0x7c+edx], al
        jmp     55f
51:     cmp     edx, MAXUID
        jae     55f
        test    ebx, ebx
        jz      55f
        cmp     byte ptr tmp, 1
        jne     55f
        sub     edx, OLDUID
        bts     dword ptr [ebx], edx
55:     inc     edi
        jmp     5b
6:      lea     ecx, rec
        mov     eax, 0x8b9670           # the record's float (+0x240) from its id
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
        mov     eax, 0x8b4520           # next row
        call    eax
        add     esp, 8
        inc     dword ptr row
        jmp     4b
9:      push    esi
        mov     eax, 0x8b52a0           # close
        call    eax
        add     esp, 4
        pop     edi
        pop     esi
        pop     ebx
        pop     ebp
        ret

# ---- ext_fit: eax = a VisualItem record, ecx = a car Unique Id. ZF set when the item fits the car (Ids 450-1999). ----
# Keeps every register.
        .balign 16, 0x90
ext_fit:
        push    edx
        push    ecx
        movzx   edx, word ptr [eax+ROWIDX]
        test    edx, edx
        jz      8f
        cmp     edx, MAXROWS
        ja      8f
        sub     ecx, OLDUID
        jb      8f
        cmp     ecx, EXTBITS
        jae     8f
        dec     edx
        imul    edx, edx, EXTROW
        bt      dword ptr [ext+edx], ecx
        jnc     8f
        xor     edx, edx                # ZF = 1
        pop     ecx
        pop     edx
        ret
8:      or      edx, -1                 # ZF = 0
        pop     ecx
        pop     edx
        ret

# ---- the default part cache getter 0x7c68a0 (thiscall (uid, category), ret 8) jumps here for its uid check -----------
# The cache (manager +0x770) holds 450 x 59 entries; Ids 450-1999 are looked up directly (FindDefaultPart 0x7c6d00).
        .balign 16, 0x90
cache_get:
        cmp     eax, OLDUID
        jge     1f
        push    0x7c68af                # back to the cached path
        ret
1:      cmp     eax, MAXUID
        jge     8f
        mov     edx, dword ptr [esp+8]
        test    edx, edx
        jl      8f
        cmp     edx, 0x3a
        jg      8f
        push    edx
        push    eax
        mov     eax, 0x7c6d00           # FindDefaultPart(uid, category) -> record or 0 (ecx is still the manager)
        call    eax
        test    eax, eax
        jz      8f
        mov     eax, dword ptr [eax+4]
        ret     8
8:      xor     eax, eax
        ret     8

# ---- IsCompatible 0x7c6cc8: eax = record, ecx = uid (> 0), edx for the log. Returns al, ret 0xc ----------------------
        .balign 16, 0x90
d_compat:
        cmp     ecx, OLDUID
        jge     1f
        push    0x7c6cd0                # the original byte test
        ret
1:      cmp     ecx, MAXUID
        jl      2f
        push    0x7c6cdb                # the original "wrong id" log
        ret
2:      call    ext_fit
        sete    al
        ret     0xc

# ---- FindDefaultPart loop 0x7c6d69: edx = [edi+8] (the category's records), esi = the record's offset, uid at
# [esp+0x14]. Flags for the `je 0x7c6d8d` at 0x7c6d74 ------------------------------------------------------------------
        .balign 16, 0x90
d_default:
        mov     eax, dword ptr [esp+0x14]
        add     edx, esi
        cmp     eax, OLDUID
        jge     1f
        cmp     byte ptr [edx+eax+0x7c], 1
        push    0x7c6d74
        ret
1:      push    ecx
        mov     ecx, eax
        mov     eax, edx
        call    ext_fit
        pop     ecx
        push    0x7c6d74
        ret

# ---- IsCompatible(carId, uid) 0x7c73df: eax = record, esi = uid (1-1999). al, then 0x7c73e7 (pop esi; ret 8) ---------
        .balign 16, 0x90
d_compat2:
        cmp     esi, OLDUID
        jge     1f
        cmp     byte ptr [eax+esi+0x7c], 1
        jmp     2f
1:      mov     ecx, esi
        call    ext_fit
2:      sete    al
        push    0x7c73e7
        ret

# ---- 0x63b06c (garage / shop: the item against the current car): eax = record, ecx = uid -----------------------------
        .balign 16, 0x90
d_shop:
        cmp     ecx, MAXUID
        jae     8f
        cmp     ecx, OLDUID
        jae     1f
        cmp     byte ptr [ecx+eax+0x7c], 1
        jmp     2f
1:      call    ext_fit
2:      jne     8f
        push    0x63b083
        ret
8:      push    0x63b49e
        ret

# ---- 0x6cd07d (two items that fit one car): esi, edx = the records, ecx = the next Id, eax = 1 -----------------------
        .balign 16, 0x90
d_pair:
        cmp     ecx, OLDUID
        jge     1f
        push    0x6cd070                # the original loop over the bytes
        ret
1:      push    ebx
        push    edi
        movzx   ebx, word ptr [esi+ROWIDX]
        movzx   edi, word ptr [edx+ROWIDX]
        test    ebx, ebx
        jz      8f
        test    edi, edi
        jz      8f
        cmp     ebx, MAXROWS
        ja      8f
        cmp     edi, MAXROWS
        ja      8f
        dec     ebx
        imul    ebx, ebx, EXTROW
        dec     edi
        imul    edi, edi, EXTROW
        xor     ecx, ecx
2:      mov     eax, dword ptr [ext+ebx+ecx*4]
        test    eax, dword ptr [ext+edi+ecx*4]
        jnz     7f
        inc     ecx
        cmp     ecx, EXTROW / 4
        jl      2b
8:      pop     edi
        pop     ebx
        push    0x6cd085                # xor eax, eax; pop esi; ret 8
        ret
7:      pop     edi
        pop     ebx
        mov     eax, 1
        push    0x6cd087                # pop esi; ret 8
        ret

# ---- 0x6d153e: eax = an object with the car's Unique Id at +4, edi = record. Flags for the je at 0x6d1546 -----------
        .balign 16, 0x90
d_obj1:
        mov     eax, dword ptr [eax+4]
        cmp     eax, OLDUID
        jae     1f
        cmp     byte ptr [eax+edi+0x7c], 1
        push    0x6d1546
        ret
1:      push    ecx
        push    eax
        mov     ecx, eax
        mov     eax, edi
        call    ext_fit
        pop     eax
        pop     ecx
        push    0x6d1546
        ret

# ---- 0x6e32ab: the same with ecx for the Id. Flags for the je at 0x6e32b3 ---------------------------------------------
        .balign 16, 0x90
d_obj2:
        mov     ecx, dword ptr [eax+4]
        cmp     ecx, OLDUID
        jae     1f
        cmp     byte ptr [ecx+edi+0x7c], 1
        push    0x6e32b3
        ret
1:      push    eax
        mov     eax, edi
        call    ext_fit
        pop     eax
        push    0x6e32b3
        ret

        .balign 16, 0
rows:   .long   0
cols:   .long   0
row:    .long   0
tmp:    .long   0
        .balign 16, 0
raw_end:                                # the file holds the section up to here; the rest is zero-filled by the loader
rec:    .space  RECSIZE
        .balign 16, 0
colmap: .space  MAXCOLS * 4
        .balign 16, 0
ext:    .space  MAXROWS * EXTROW
image_end:
