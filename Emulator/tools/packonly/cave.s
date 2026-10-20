# NiSystem20VC71.dll (2011-09-30 / 2013-08-20 builds, same code): NiFile::NiFile reads only from the .agt packs inside the
# packed folders. Code in the slack at the end of .text (0x10012da0), the folder list (pack_client.folder_table) in the
# slack at the end of .rdata (0x1001c240); linked and written by tools/pack_client.py (patch); the jump to it
# replaces `cmp eax, ebx; mov [esi+0xc], eax; jne 0x1000468e` at 0x10004650 (after CNPacker::Find 0x10009210).
# Registers there: eax = the pack entry or 0, esi = the NiFile, edi = the path, ebx = 0. Position independent: every
# Gamebryo DLL prefers 0x10000000, so this one is relocated; absolute addresses go through the load delta.
        .intel_syntax noprefix
        .code32
        .text
        .globl _start
_start:
        mov     [esi+0xc], eax
        test    eax, eax
        jnz     0x1000468e              # in a pack: read from it
        pushad
        push    edi
        call    check
        add     esp, 4
        mov     [esp+28], eax           # popad's eax
        popad
        test    eax, eax
        jnz     deny
        jmp     0x10004657              # allowed: fopen, as before
deny:   mov     dword ptr [esi+0x20], 0 # as a failed fopen: no FILE, not good
        mov     byte ptr [esi+0x28], 0
        jmp     0x1000468b

# check(path) -> eax 1: a packed folder's file that is not in its pack (refused), 0: allowed
check:  push    ebp
        mov     ebp, esp
        sub     esp, 0x108
        push    ebx
        push    esi
        push    edi
        call    1f
1:      pop     ebx
        sub     ebx, offset 1b          # ebx = load delta
        push    0x104
        push    [ebp+8]
        lea     eax, [ebp-0x108]
        push    eax
        mov     eax, 0x100131f8         # the _fullpath import (CNPacker::Find makes its key the same way)
        call    [eax+ebx]
        add     esp, 12
        test    eax, eax
        jz      allow
        lea     esi, [ebp-0x108]        # lower case, '/' -> '\'
lc:     mov     al, [esi]
        test    al, al
        jz      lcend
        cmp     al, '/'
        jne     1f
        mov     byte ptr [esi], '\\'
        jmp     2f
1:      cmp     al, 'A'
        jb      2f
        cmp     al, 'Z'
        ja      2f
        add     byte ptr [esi], 32
2:      inc     esi
        jmp     lc
lcend:  lea     eax, [ebp-0x108]
        mov     ecx, esi
        sub     ecx, eax
        cmp     ecx, 4
        jb      allow
        mov     eax, [esi-4]            # files the client keeps (and writes) loose in packed folders
        cmp     eax, 0x696e692e         # ".ini" (Data/Init/goption.ini ...)
        je      allow
        cmp     eax, 0x6d66752e         # ".ufm" (Data/World/<city>/*.ufm)
        je      allow
        cmp     eax, 0x7467612e         # ".agt" (the packs themselves)
        je      allow
        lea     edx, [ebx+denied]
tbl:    cmp     byte ptr [edx], 0
        je      allow
        lea     esi, [ebp-0x108]
outer:  cmp     byte ptr [esi], 0
        je      next
        xor     ecx, ecx
inner:  mov     al, [edx+ecx]
        test    al, al
        jz      refuse
        cmp     al, [esi+ecx]
        jne     adv
        inc     ecx
        jmp     inner
adv:    inc     esi
        jmp     outer
next:   inc     edx
        cmp     byte ptr [edx-1], 0
        jne     next
        jmp     tbl
refuse: mov     eax, 1
        jmp     out
allow:  xor     eax, eax
out:    pop     edi
        pop     esi
        pop     ebx
        leave
        ret

# the packed folders: written by tools/pack_client.py (folder_table, from PACKS) at TABLE, as "\\data\\init\\\0" ... "\0"
        .set    denied, 0x1001c240
