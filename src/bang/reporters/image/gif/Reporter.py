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

import rich
import rich.markdown
import rich.table

from bang.Reporter import Reporter


class GifReporter(Reporter):
    tags = ['gif']
    pretty_name = 'gif'

    def create_report(self, md):
        title = rich.markdown.Markdown("## GIF")
        metadata = md.info.get('metadata')
        reports = []
        with md.open(open_file=False, info_write=False):
            meta_table = rich.table.Table('', '', title='GIF meta data', show_lines=True, show_header=False)
            meta_table.add_row('Width', str(metadata['width']))
            meta_table.add_row('Height', str(metadata['height']))
            reports.append(meta_table)

        return title, reports
