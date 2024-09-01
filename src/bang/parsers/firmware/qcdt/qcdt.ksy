meta:
  id: qcdt
  title: QCDT
  tags:
    - archive
    - android
  license: CC0-1.0
  endian: le
doc: |
  Format of Qualcomm DTB files. Note: the device entries can all point to
  the same entry as DTB files can be shared between devices.

doc-ref:
  - https://gitlab.com/Codeaurora/platform_system_core/-/raw/83b5d524c5/dtbtool/dtbtool.txt (v1)
  - https://raw.githubusercontent.com/omnirom/android_device_lge_g4-common/android-6.0/dtbtool/dtbtool.txt (v2)
  - https://raw.githubusercontent.com/CyanogenMod/android_device_qcom_common/cm-14.1/dtbtool/dtbtool.txt (v3)
  - https://source.codeaurora.org/quic/kernel/skales/plain/dtbTool?id=1.6.0
  - web.archive.org/web/20160402060151if_/https://developer.qualcomm.com/qfile/28821/lm80-p0436-1_little_kernel_boot_loader_overview.pdf (section 2.4.1)
  - https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/soc/qcom/socinfo.c?h=v5.19
  - https://android.googlesource.com/kernel/msm/+/android-7.1.0_r0.2/drivers/soc/qcom/socinfo.c
  - https://github.com/brinlyau/P810D02_ZTE_T792_KitKat_3.4/blob/master/P810D02_ZTE_T792_KitKat_340_kernel/arch/arm/mach-msm/socinfo.c
  - https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/include/dt-bindings/arm/qcom,ids.h?id=de7aeee0d942d2e1d85b3db3652e037af38e24d7
seq:
  - id: magic
    contents: "QCDT"
  - id: version
    type: u4
    valid:
      any-of: [1, 2, 3]
  - id: num_dtbs
    type: u4
  - id: device_entries
    type: device_entry
    repeat: expr
    repeat-expr: num_dtbs
types:
  device_entry:
    seq:
      - id: platform_id
        type: u4
        enum: soc_ids
      - id: variant_id
        type: u4
      - id: subtype_id
        type: u4
        if: _root.version > 1
      - id: soc_revision
        type: u4
      - id: pmic0
        type: u4
        if: _root.version > 2
      - id: pmic1
        type: u4
        if: _root.version > 2
      - id: pmic2
        type: u4
        if: _root.version > 2
      - id: pmic3
        type: u4
        if: _root.version > 2
      - id: ofs_dtb
        type: u4
      - id: len_dtb
        type: u4
    instances:
      data:
        pos: ofs_dtb
        size: len_dtb
enums:
  soc_ids:
    1: msm7x01_1
    16: msm7x01_2
    17: msm7x01_3
    18: msm7x01_4
    19: msm7x01_5
    20: msm7x25_1
    21: msm7225
    23: msm7x01_6
    24: msm7525
    25: msm7x01_7
    26: msm7x01_8
    27: msm7625
    30: msm8x50_1
    32: msm7x01_9
    33: msm7x01_10
    34: msm7x01_11
    35: msm7x01_12
    36: msm8x50_2
    37: msm8x50_3
    38: msm8x50_4
    39: msm7x25_2
    40: msm7x25_3
    42: msm7x25_5
    43: msm7x27_1
    44: msm7x27_2
    59: msm7x30_1
    60: msm7x30_2
    61: msm7x27_3
    62: msm7625_1
    63: msm7225_1
    66: msm7225_2
    67: msm7227_1
    68: msm7627_1
    69: msm7627_2
    70: msm8260
    71: msm8660
    74: msm8x55_1
    75: msm8x55_2
    85: msm8x55_3
    86: apq8060
    87: msm8960
    88: msm7x25a_1
    89: msm7x25a_2
    90: msm7x27a_1
    91: msm7x27a_2
    92: msm7x27a_3
    94: fsm_9xxx_1
    95: fsm_9xxx_2
    96: msm7x25a_3
    97: msm7x27a_4
    98: msm7x25aa_1
    99: msm7x25aa_2
    100: msm7x25aa_3
    101: msm7x27aa_1
    102: msm7x27aa_2
    103: msm7x27aa_3
    104: msm9615_1
    105: msm9615_2
    106: msm9615_3
    107: msm9615_4
    109: apq8064
    116: msm8930
    117: msm8630
    118: msm8230
    119: apq8030
    120: msm8627
    121: msm8227
    122: msm8660a
    123: msm8260a
    124: apq8060a
    126: msm8974
    127: msm8225
    128: msm8625_2
    129: msm8625
    130: mpq8064
    131: msm7x25ab_1
    132: msm7x25ab_2
    133: msm7x25ab_3
    134: msm9625_1
    135: msm7x25ab_4
    138: msm8960ab
    139: apq8060ab
    140: msm8260ab
    141: msm8660ab
    142: msm8930aa
    143: msm8630aa
    144: msm8230aa
    145: msm8626
    147: msm8610
    148: msm9625_2
    149: msm9625_3
    150: msm9625_4
    151: msm9625_5
    152: msm9625_6
    153: apq8064ab
    154: msm8930ab
    155: msm8630ab
    156: msm8230ab
    157: apq8030ab
    158: msm8226
    159: msm8526
    160: apq8030aa
    161: msm8110
    162: msm8210
    163: msm8810
    164: msm8212
    165: msm8612
    166: msm8112
    167: msm8125
    168: msm8225q
    169: msm8625q
    170: msm8125q
    172: apq8064aa
    173: msm9625_7
    174: msm9625_8
    175: msm9625_9
    178: apq8084
    179: msm8130
    180: msm8130aa
    181: msm8130ab
    182: msm8627aa
    183: msm8227aa
    184: apq8074
    185: msm8274
    186: msm8674
    187: mdm9635
    194: msm8974_pro_ac
    198: msm8126
    199: apq8026
    200: msm8926
    201: ipq8062
    202: ipq8064
    203: ipq8066
    204: ipq8068
    205: msm8326
    206: msm8916
    207: msm8994
    208: apq8074pro_aa
    209: apq8074pro_ab
    210: apq8074pro_ac
    211: msm8274pro_aa
    212: msm8274pro_ab
    213: msm8274pro_ac
    214: msm8674pro_aa
    215: msm8674pro_ab
    216: msm8674pro_ac
    217: msm8974pro_aa
    218: msm8974pro_ab
    219: apq8028
    220: msm8128
    221: msm8228
    222: msm8528
    223: msm8628
    224: msm8928
    225: msm8510
    226: msm8512
    233: msm8936
    234: mdm9640
    239: msm8939
    240: apq8036
    241: apq8039
    242: msm8236
    243: msm8636
    244: apq8064_au
    245: msm8909
    246: msm8996
    247: apq8016
    248: msm8216
    249: msm8116
    250: msm8616
    251: msm8992
    252: apq8092
    253: apq8094
    258: msm8209
    259: msm8208
    260: mdm9209
    261: mdm9309
    262: mdm9609
    263: msm8239
    264: msm8952
    265: apq8009
    266: msm8956
    268: msm8929
    269: msm8629
    270: msm8229
    271: apq8029
    273: ipq4019
    274: apq8056
    275: msm8609
    277: apq8076
    278: msm8976
    279: mdm9650
    280: ipq8065
    281: ipq8069
    283: mdm9655
    284: mdm9250
    285: mdm9255
    286: mdm9350
    289: apq8052
    290: mdm9607
    291: apq8096
    292: msm8998
    293: msm8953
    294: msm8937
    295: apq8037
    296: mdm8207
    297: mdm9207
    298: mdm9307
    299: mdm9628
    300: msm8909w
    301: apq8009w
    302: msm8996l
    303: msm8917
    304: apq8053
    305: msm8996sg
    307: apq8017
    308: msm8217
    309: msm8617
    310: msm8996au
    311: apq8096au
    312: apq8096sg
    313: msm8940
    314: sdx201
    317: sdm660
    318: sdm630
    319: apq8098
    320: msm8920
    321: sdm845
    322: mdm9206
    324: sda660
    325: sdm658
    326: sda658
    327: sda630
    331: msm8905
    333: sdx202
    336: sdm670
    338: sdm450
    339: sm8150
    341: sda845
    345: sdm636
    346: sda636
    349: sdm632
    350: sda632
    351: sda450
    353: sdm439
    354: sdm429
    356: sm8250
    362: sa8155
    363: sda439
    364: sda429
    365: sm7150
    366: sm7150p
    375: ipq8070
    376: ipq8071
    386: qm215
    389: ipq8072a
    390: ipq8074a
    391: ipq8076a
    394: sm6125
    395: ipq8070a
    396: ipq8071a
    397: ipq8172
    398: ipq8173
    399: ipq8174
    402: ipq6018
    403: ipq6028
    416: sdm429w
    417: sm4250
    421: ipq6000
    422: ipq6010
    425: sc7180
    434: sm6350
    436: qcm2150
    437: sda429w
    439: sm8350
    441: qcm2290
    443: sm7125
    444: sm6115
    446: ipq5010
    447: ipq5018
    448: ipq5028
    449: sc8280xp
    453: ipq6005
    455: qrb5165
    457: sm8450
    459: sm7225
    460: sa8295p
    461: sa8540p
    469: qcm4290
    470: qcs4290
    480: sm8450_1
    482: sm8450_2
    487: sc7280
    495: sc7180p
    497: qcm6490
    503: ipq5000
    504: ipq0509
    505: ipq0518
    507: sm6375
    510: ipq9514
    511: ipq9550
    512: ipq9554
    513: ipq9570
    514: ipq9574
    519: sm8550
    520: ipq5016
    521: ipq9510
    523: qrb4210
    524: qrb2210
    530: sm8475
    531: sm8475p
    534: sa8775p
    539: qru1000
    540: sm8475_2
    545: qdu1000
    555: x1e80100
    557: sm8650
    568: sm4450
    569: ipq5019
    587: qdu1010
    588: qru1032
    589: qru1052
    590: qru1062
    592: ipq5332
    593: ipq5322
    594: ipq5312
    595: ipq5302
    603: qcs8550
    604: qcm8550
    624: ipq5300
    650: ipq5321
  platform_ids:
    1: cdp
    2: ffa
    3: fluid
    4: fusion
    5: oem
    6: qt
    7: mtp_mdm
    8: mtp
    9: liquid
    10: dragonboard
    11: qrd
    12: evb
    13: hrd
    14: dtv
    15: rumi
    16: virtio
    20: xpm
    21: rcm
    23: stp
    24: sbc
    25: adp
    29: cls
    30: ttp
    31: hdk
    32: iot
    34: idp
  pmic_ids:
    0: unknown
    1: pm8941
    2: pm8841
    3: pm8019
    4: pm8026
    5: pm8110
    6: pma8084
    7: pmi8962
    8: pmd9635
    9: pm8994
    10: pmi8994
    11: pm8916
    12: pm8004
    13: pm8909
    14: pm2433
    15: pmd9655
    16: pm8950
    17: pmi8950
    18: pmk8001
    19: pmi8996
    20: pm8998
    21: pmi8998
    22: pm8953
    23: smb1380
    24: pm8005
    25: pm8937
    26: pm660l
    27: pm660
    30: pm8150
    31: pm8150l
    32: pm8150b
    33: pmk8002
    36: pm8009
    37: pmi632
    38: pm8150c
    40: pm6150
    41: smb2351
    44: pm8008
    45: pm6125
    46: pm7250b
    47: pmk8350
    48: pm8350
    49: pm8350c
    50: pm8350b
    51: pmr735a
    52: pmr735b
    55: pm2250
    58: pm8450
    65: pm8010
    69: pm8550vs
    70: pm8550ve
    71: pm8550b
    72: pmr735d
    73: pm8550
    74: pmk8550
