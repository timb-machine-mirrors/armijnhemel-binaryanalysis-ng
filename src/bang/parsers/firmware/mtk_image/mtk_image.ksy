meta:
  id: mtk_image
  title: Mediatek images
  file-extension: bin
  tags:
    - android
    - mediatek
  license: GPL-3.0-or-later
  encoding: UTF-8
  endian: le
doc: |
  Container format of various Mediatek files

doc-ref:
  - https://github.com/omnirom/android_device_oppo_r819/blob/android-4.4/mkmtkbootimg/bootimg.h
  - http://web.archive.org/web/20200805105219/https://www.rigacci.org/wiki/doku.php/doc/appunti/android/logo_bootanimation
  - http://web.archive.org/web/20201123215346/https://www.rigacci.org/wiki/lib/exe/fetch.php/doc/appunti/android/mtk-android-logo.txt
seq:
  - id: header
    type: header
    size: 512
  - id: payload
    size: header.len_payload
    type:
      switch-on: header.magic
      cases:
        '"logo"': images
        '"LOGO"': images
types:
  header:
    seq:
      - id: mtk_magic
        contents: [0x88, 0x16, 0x88, 0x58]
        doc: This header seems to be used in many MediaTek files
      - id: len_payload
        type: u4
      - id: magic
        size: 32
        type: strz
  images:
    seq:
      - id: num_pictures
        type: u4
      - id: total_block_size
        type: u4
        valid: _root.header.len_payload
        doc: |
          It is unclear whether or not this value is always the same as
          the one in the header. Firmware repack scripts seem to suggest
          that this is not necessarily the case, but in all observed
          firmware files it is the case.
      - id: offsets
        type: u4
        repeat: expr
        repeat-expr: num_pictures
    instances:
      data:
        type: body(_index)
        repeat: expr
        repeat-expr: num_pictures
    types:
      body:
        params:
          - id: i
            type: u4
        instances:
          body:
            pos: _parent.offsets[i]
            size: 'i == _parent.offsets.size - 1 ? _parent.total_block_size - _parent.offsets[i] : _parent.offsets[i+1] - _parent.offsets[i]'
            process: zlib
