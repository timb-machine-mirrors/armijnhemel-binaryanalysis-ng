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


import os
from UnpackParser import WrappedUnpackParser
from bangfilesystems import unpack_iso9660

from UnpackParser import UnpackParser, check_condition
from UnpackParserException import UnpackParserException
from kaitaistruct import ValidationNotEqualError, ValidationExprError, ValidationLessThanError
from . import iso9660


class Iso9660UnpackParser(WrappedUnpackParser):
    extensions = []
    signatures = [
        (32769, b'CD001')
    ]
    pretty_name = 'iso9660'

    def unpack_function(self, fileresult, scan_environment, offset, unpack_dir):
        return unpack_iso9660(fileresult, scan_environment, offset, unpack_dir)

