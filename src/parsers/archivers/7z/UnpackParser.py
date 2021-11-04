# Binary Analysis Next Generation (BANG!)
#
# This file is part of BANG.
#
# BANG is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License, version 3,
# as published by the Free Software Foundation.
#
# BANG is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License, version 3, along with BANG.  If not, see
# <http://www.gnu.org/licenses/>
#
# Copyright Armijn Hemel
# Licensed under the terms of the GNU Affero General Public License
# version 3
# SPDX-License-Identifier: AGPL-3.0-only


import binascii
import os
import shutil
import stat
import subprocess

from UnpackParser import WrappedUnpackParser
from bangunpack import unpack_7z

from FileResult import FileResult

from UnpackParser import UnpackParser, check_condition
from UnpackParserException import UnpackParserException
from kaitaistruct import ValidationFailedError
from . import sevenzip


class SevenzipUnpackParser(WrappedUnpackParser):
#class SevenzipUnpackParser(UnpackParser):
    extensions = []
    signatures = [
        (0, b'7z\xbc\xaf\x27\x1c')
    ]
    pretty_name = '7z'

    def unpack_function(self, fileresult, scan_environment, offset, unpack_dir):
        return unpack_7z(fileresult, scan_environment, offset, unpack_dir)

    def parse(self):
        check_condition(shutil.which('7z') is not None, '7z program not found')
        try:
            self.data = sevenzip.Sevenzip.from_io(self.infile)
            computed_crc = binascii.crc32(self.data.header.start_header.next_header)
        except (Exception, ValidationFailedError) as e:
            raise UnpackParserException(e.args)
        check_condition(self.data.header.start_header.next_header_crc == computed_crc,
                        "invalid next header CRC")

        computed_crc = binascii.crc32(self.data.header._raw_start_header)
        check_condition(self.data.header.start_header_crc == computed_crc,
                        "invalid start header CRC")

        # header is 32 bytes
        self.unpacked_size = 32

        # then add the next header offset and length
        self.unpacked_size += self.data.header.start_header.ofs_next_header
        self.unpacked_size += self.data.header.start_header.len_next_header

    # no need to carve from the file
    def carve(self):
        pass

    # make sure that self.unpacked_size is not overwritten
    def calculate_unpacked_size(self):
        pass

    def unpack(self):
        unpacked_files = []
        unpackdir_full = self.scan_environment.unpack_path(self.rel_unpack_dir)

        # check if the file starts at offset 0. If not, carve the
        # file first, as 7z tries to be smart and unpack
        # all data in a file
        havetmpfile = False
        if not (self.offset == 0 and self.fileresult.filesize == self.unpacked_size):
            temporary_file = tempfile.mkstemp(dir=self.scan_environment.temporarydirectory)
            havetmpfile = True
            os.sendfile(temporary_file[0], self.infile.fileno(), self.offset, self.unpacked_size)
            os.fdopen(temporary_file[0]).close()

        if havetmpfile:
            p = subprocess.Popen(['7z', '-o%s' % unpackdir_full, '-y', 'x', temporaryfile[1]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            p = subprocess.Popen(['7z', '-o%s' % unpackdir_full, '-y', 'x', self.fileresult.filename], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        (outputmsg, errormsg) = p.communicate()

        if havetmpfile:
            os.unlink(temporary_file[1])

        if p.returncode != 0:
            return unpacked_files

        # walk the results directory
        for result in unpackdir_full.iterdir():
            # first change the permissions
            result.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

            # then add the file to the result set
            file_path = result.relative_to(unpackdir_full)
            fr = FileResult(self.fileresult, self.rel_unpack_dir / file_path, set())
            unpacked_files.append(fr)

        return unpacked_files

    def set_metadata_and_labels(self):
        """sets metadata and labels for the unpackresults"""
        labels = ['7z', 'compressed', 'archive']
        metadata = {}

        self.unpack_results.set_metadata(metadata)
        self.unpack_results.set_labels(labels)
