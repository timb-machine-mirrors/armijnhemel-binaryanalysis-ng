import sys, os
from test.util import *
from test.mock_metadirectory import *

from UnpackParserException import UnpackParserException
from .UnpackParser import WavUnpackParser

def test_load_standard_wav_file(scan_environment):
    testfile = testdir_base / 'testdata' / 'unpackers' / 'wav' / 'test.wav'
    sz = testfile.stat().st_size
    with testfile.open('rb') as f:
        p = WavUnpackParser(f, 0, sz)
        p.parse_from_offset()
        md = MockMetaDirectory()
        p.write_info(md)
        for _ in p.unpack(md): pass
        assert md.unpacked_files == {}

