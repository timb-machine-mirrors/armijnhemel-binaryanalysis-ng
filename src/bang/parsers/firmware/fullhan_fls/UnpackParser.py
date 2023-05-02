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

import pathlib

from bang.UnpackParser import UnpackParser, check_condition
from bang.UnpackParserException import UnpackParserException
from kaitaistruct import ValidationFailedError
from . import fullhan_fls


class FullhanFlsUnpackParser(UnpackParser):
    extensions = ['.fls']
    signatures = []
    pretty_name = 'fullhan_fls'

    def parse(self):
        try:
            self.data = fullhan_fls.FullhanFls.from_io(self.infile)
        except (Exception, ValidationFailedError) as e:
            print(e)
            raise UnpackParserException(e.args)

    def unpack(self, meta_directory):
        for entry in self.data.entries:
            if entry.len_data == 0:
                continue

            if entry.name == '':
                continue

            file_path = pathlib.Path(entry.name)

            with meta_directory.unpack_regular_file(file_path) as (unpacked_md, outfile):
                outfile.write(entry.data)
                yield unpacked_md

    labels = ['fullhan_fls', 'firmware']
    metadata = {}
