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

# JFFS2 https://en.wikipedia.org/wiki/JFFS2
# JFFS2 is a file system that was used on earlier embedded Linux
# system, although it is no longer the first choice for modern systems,
# where for example UBI/UBIFS are chosen.

import lzma
import os
import pathlib
import stat
import zlib

import lzo

from bang.UnpackParser import UnpackParser, check_condition
from bang.UnpackParserException import UnpackParserException
from kaitaistruct import ValidationFailedError

from . import jffs2

# the various node types in JFFS2 are:
#
# * directory entry
# * inode (containing actual data)
# * clean marker
# * padding
# * summary
# * xattr
# * xref

DIRENT = 0xe001
INODE = 0xe002
CLEANMARKER = 0x2003
PADDING = 0x2004
SUMMARY = 0x2006
XATTR = 0xe008
XREF = 0xe009

VALID_INODES = set([DIRENT, INODE, CLEANMARKER,
                    PADDING, SUMMARY, XATTR, XREF])

# different kinds of compression
# The mtd-utils code defines more types of "compression"
# than supported by mkfs.jffs2
# LZMA compression is available as a patch from OpenWrt.
COMPR_NONE = 0x00
COMPR_ZERO = 0x01
COMPR_RTIME = 0x02
COMPR_RUBINMIPS = 0x03
COMPR_COPY = 0x04
COMPR_DYNRUBIN = 0x05
COMPR_ZLIB = 0x06
COMPR_LZO = 0x07
COMPR_LZMA = 0x08

# LZMA settings from OpenWrt's patch
LZMA_DICT_SIZE = 0x2000
LZMA_PB = 0
LZMA_LP = 0
LZMA_LC = 0


class Jffs2UnpackParser(UnpackParser):
    extensions = []
    signatures = [
        (0, b'\x85\x19'),
        (0, b'\x19\x85')
    ]
    pretty_name = 'jffs2'

    def parse(self):
        # parse the first inode to see if it is a little endian
        # or big endian file system. The first inode is *always*
        # a valid inode, not a dirty inode.
        try:
            root_inode = jffs2.Jffs2.from_io(self.infile)
        except (ValidationFailedError, EOFError) as e:
            raise UnpackParserException(e.args)

        self.bigendian = False
        if root_inode.magic == jffs2.Jffs2.Magic.be:
            self.bigendian = True

        # keep a list of inodes to file names
        # the root inode (1) always has ''
        inode_to_filename = {}
        inode_to_filename[1] = pathlib.Path('')

        data_unpacked = False

        # keep track of which nodes have already been seen. This is to
        # detect if multiple JFFS2 file systems have been concatenated.
        # Also store the version, as inodes could have been reused in the
        # case of hardlinks.
        inodes_seen_version = set()
        parent_inodes_seen = set()

        # keep a mapping of inodes to last written position in
        # the file.
        inode_to_write_offset = {}

        # a mapping of inodes to open files
        inode_to_open_files = {}
        current_inode = None

        root_seen = False

        # reset the file pointer to the start of the file system and read all
        # the inodes. It isn't necessarily known in advance how many inodes
        # there will be, so process all the files until either the end
        # of the file is reached, a new file system is started, or the file
        # system ends.
        self.infile.seek(0)

        prev_is_padding = False
        while True:
            cur_offset = self.infile.tell()

            # stop processing the end of the file is reached
            if self.infile.tell() == self.infile.size:
                break

            # read the first two bytes to see if it is a normal
            # node, a dirty node or empty space. This cannot be
            # nicely captured in Kaitai Struct.
            buf = self.infile.read(2)
            if len(buf) != 2:
                break

            # first check if the inode magic is valid
            if self.bigendian:
                if buf not in [b'\x19\x85', b'\x00\x00', b'\xff\xff']:
                    break
            else:
                if buf not in [b'\x85\x19', b'\x00\x00', b'\xff\xff']:
                    break
            if buf == b'\x00\x00':
                # dirty nodes
                node_magic_type = 'dirty'
            elif buf == b'\xff\xff':
                # empty space
                # read the next two bytes to see if they are empty as well
                buf = self.infile.read(2)
                if buf != b'\xff\xff':
                    break
                continue
            else:
                node_magic_type = 'normal'

            self.infile.seek(cur_offset)

            try:
                jffs2_inode = jffs2.Jffs2.from_io(self.infile)
            except (ValidationFailedError , EOFError) as e:
                break

            if jffs2_inode.magic != root_inode.magic and jffs2_inode.magic != jffs2.Jffs2.Magic.dirty:
                break

            # check if the inode type is actually valid
            # or perhaps contains padding.
            if type(jffs2_inode.header.inode_type) == int:
                if jffs2_inode.header.inode_type == 0:
                    if prev_is_padding:
                        break
                    # due to page alignments there might
                    # be extra NULL bytes
                    if (cur_offset + 4) % 4096 != 0:
                        ofs = self.infile.tell()
                        bytes_to_read = 4096 - ((cur_offset + 4)%4096)
                        buf = self.infile.read(bytes_to_read)
                        if buf != b'\x00' * bytes_to_read:
                            self.infile.seek(ofs)
                            break
                else:
                    break
                prev_is_padding = True
                continue

            prev_is_padding = False

            # skip dirty nodes
            if node_magic_type == 'dirty':
                unpackedsize = self.infile.tell()
                if unpackedsize % 4 != 0:
                    paddingbytes = 4 - (unpackedsize % 4)
                    self.infile.seek(paddingbytes, os.SEEK_CUR)
                    unpackedsize = self.infile.tell()
                continue

            # Verify the header CRC of the first 8 bytes in the node
            # The checksum is not the same as the CRC32 algorithm from
            # zlib, and it is explained here:
            #
            # http://www.infradead.org/pipermail/linux-mtd/2003-February/006910.html
            #
            # The checksum varies slightly from the one in the zlib modules
            # as explained here:
            #
            # http://www.infradead.org/pipermail/linux-mtd/2003-February/006910.html
            #
            # specific implementation for computing checksum grabbed from
            # MIT licensed script found at:
            #
            # https://github.com/sviehb/jefferson/blob/master/src/scripts/jefferson
            stored_offset = self.infile.tell()
            self.infile.seek(cur_offset)
            crc_bytes = self.infile.read(8)
            self.infile.seek(stored_offset)

            computedcrc = (zlib.crc32(crc_bytes, -1) ^ -1) & 0xffffffff
            if not computedcrc == jffs2_inode.data.header_crc:
                break

            # process directory entries
            if jffs2_inode.header.inode_type == jffs2.Jffs2.InodeType.dirent:
                parent_inodes_seen.add(jffs2_inode.data.parent_inode)

                # skip unlinked inodes
                if jffs2_inode.data.inode_number == 0:
                    # first go back to the old offset, then skip
                    # the entire inode
                    self.infile.seek(cur_offset + jffs2_inode.header.len_inode)
                    unpackedsize = self.infile.tell()
                    if unpackedsize % 4 != 0:
                        paddingbytes = 4 - (unpackedsize % 4)
                        self.infile.seek(paddingbytes, os.SEEK_CUR)
                        unpackedsize = self.infile.tell()
                    continue

                # cannot have duplicate inodes
                if (jffs2_inode.data.inode_number, jffs2_inode.data.inode_version) in inodes_seen_version:
                    break

                inodes_seen_version.add((jffs2_inode.data.inode_number, jffs2_inode.data.inode_version))

                # the name of the node
                try:
                    inode_name = jffs2_inode.data.name.decode()
                except UnicodeDecodeError:
                    break

                # compute the CRC of the name
                computedcrc = (zlib.crc32(jffs2_inode.data.name, -1) ^ -1) & 0xffffffff
                if jffs2_inode.data.name_crc != computedcrc:
                    break

                # now add the name to the inode to filename mapping
                if jffs2_inode.data.parent_inode in inode_to_filename:
                    inode_to_filename[jffs2_inode.data.inode_number] = inode_to_filename[jffs2_inode.data.parent_inode] / inode_name

            elif jffs2_inode.header.inode_type == jffs2.Jffs2.InodeType.inode:
                # first check if a file name for this inode is known
                if jffs2_inode.data.inode_number not in inode_to_filename:
                    break

                # skip unlinked inodes
                if jffs2_inode.data.inode_number == 0:
                    # first go back to the old offset, then skip
                    # the entire inode
                    self.infile.seek(cur_offset + jffs2_inode.header.len_inode)
                    unpackedsize = self.infile.tell()
                    if unpackedsize % 4 != 0:
                        paddingbytes = 4 - (unpackedsize % 4)
                        self.infile.seek(paddingbytes, os.SEEK_CUR)
                        unpackedsize = self.infile.tell()
                    continue

                filemode = jffs2_inode.data.file_mode

                if filemode == jffs2.Jffs2.Modes.socket:
                    # keep track of whatever is in the file and report
                    pass
                elif filemode == jffs2.Jffs2.Modes.directory:
                    # create directories, but skip them otherwise
                    self.infile.seek(cur_offset + jffs2_inode.header.len_inode)
                    data_unpacked = True
                    continue
                elif filemode == jffs2.Jffs2.Modes.link:
                    try:
                        symlink = jffs2_inode.data.body.data.decode()
                        data_unpacked = True
                    except UnicodeDecodeError:
                        break
                elif filemode == jffs2.Jffs2.Modes.regular:
                    writeoffset = jffs2_inode.data.body.ofs_write

                    if writeoffset == 0:
                        if jffs2_inode.data.inode_number in inode_to_write_offset:
                            break
                        if jffs2_inode.data.inode_number in inode_to_open_files:
                            break

                        # store a reference as if there was an open file
                        inode_to_open_files[jffs2_inode.data.inode_number] = {}
                        current_inode = jffs2_inode.data.inode_number
                    else:
                        if writeoffset != inode_to_write_offset[jffs2_inode.data.inode_number]:
                            break
                        if jffs2_inode.data.inode_number not in inode_to_open_files:
                            break

                    # Check the compression that's used as it could be that
                    # for a file compressed and uncompressed nodes are mixed
                    # in case the node cannot be compressed efficiently
                    # and the compressed data would be larger than the
                    # original data.
                    if jffs2_inode.data.body.compression == jffs2.Jffs2.Compression.no_compression:
                        # the data is not compressed, so can be written
                        # to the output file immediately
                        data_unpacked = True
                    elif jffs2_inode.data.body.compression == jffs2.Jffs2.Compression.zlib:
                        # the data is zlib compressed, so first decompress
                        # before writing
                        try:
                            zlib.decompress(buf)
                            data_unpacked = True
                        except Exception as e:
                            break
                    elif jffs2_inode.data.body.compression == jffs2.Jffs2.Compression.lzma:
                        # The data is LZMA compressed, so create a
                        # LZMA decompressor with custom filter, as the data
                        # is stored without LZMA headers.
                        jffs_filters = [{'id': lzma.FILTER_LZMA1,
                                         'dict_size': LZMA_DICT_SIZE,
                                         'lc': LZMA_LC, 'lp': LZMA_LP,
                                         'pb': LZMA_PB}]

                        decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=jffs_filters)

                        try:
                            decompressor.decompress(buf)
                            data_unpacked = True
                        except Exception as e:
                            break
                    elif jffs2_inode.data.body.compression == jffs2.Jffs2.Compression.rtime:
                        # From: https://github.com/sviehb/jefferson/blob/master/src/jefferson/rtime.py
                        # First initialize the positions, set to 0
                        positions = [0] * 256

                        # create a bytearray, set everything to 0
                        data_out = bytearray([0] * decompressed_size)

                        # create counters
                        outpos = 0
                        pos = 0

                        # process all the bytes
                        while outpos < decompressed_size:
                            value = buf[pos]
                            pos += 1
                            data_out[outpos] = value
                            outpos += 1
                            repeat = buf[pos]
                            pos += 1

                            backoffs = positions[value]
                            positions[value] = outpos
                            if repeat:
                                if backoffs + repeat >= outpos:
                                    while repeat:
                                        data_out[outpos] = data_out[backoffs]
                                        outpos += 1
                                        backoffs += 1
                                        repeat -= 1
                                else:
                                    data_out[outpos : outpos + repeat] = data_out[
                                        backoffs : backoffs + repeat
                                    ]
                                    outpos += repeat
                    elif jffs2_inode.data.body.compression == jffs2.Jffs2.Compression.lzo:
                        try:
                            lzo.decompress(buf, False, decompressed_size)
                        except:
                            raise UnpackParserException("invalid lzo compressed data")
                    else:
                        break

                    # record how much data was read and use for sanity checks
                    inode_to_write_offset[jffs2_inode.data.inode_number] = writeoffset + decompressed_size

            unpackedsize = self.infile.tell()
            if unpackedsize % 4 != 0:
                paddingbytes = 4 - (unpackedsize % 4)
                self.infile.seek(paddingbytes, os.SEEK_CUR)
                unpackedsize = self.infile.tell()

        check_condition(data_unpacked, "no data unpacked")
        check_condition(1 in parent_inodes_seen, "no valid root file node")
        self.infile.seek(cur_offset)
        self.unpacked_size = cur_offset

    # For unpacking data only the directory entry and regular inode
    # will be considered.
    def unpack(self, meta_directory):
        unpacked_files = []

        inode_to_filename = {}
        inode_to_filename[1] = pathlib.Path('')
        parent_inodes_seen = set()
        inode_to_write_offset = {}
        inode_to_open_files = {}
        current_inode = None

        # reset the file pointer to the start of the file system and read all
        # the inodes again, but now for unpacking.
        self.infile.seek(0)

        prev_is_padding = False
        while True:
            cur_offset = self.infile.tell()

            # stop processing the end of the file is reached
            if self.infile.tell() == self.unpacked_size:
                break
            buf = self.infile.read(2)
            if len(buf) != 2:
                break

            if buf == b'\x00\x00':
                # dirty nodes
                node_magic_type = 'dirty'
            elif buf == b'\xff\xff':
                # empty space
                # read the next two bytes to see if they are empty as well
                buf = self.infile.read(2)
                if buf != b'\xff\xff':
                    break
                continue
            else:
                node_magic_type = 'normal'

            # then read the node type
            buf = self.infile.read(2)
            inode_type = int.from_bytes(buf, byteorder=self.byteorder)

            # check if the inode type is actually valid
            # or perhaps contains padding.
            if inode_type not in VALID_INODES:
                if inode_type == 0:
                    if prev_is_padding:
                        break
                    # due to page alignments there might
                    # be extra NULL bytes
                    if (cur_offset + 4) % 4096 != 0:
                        ofs = self.infile.tell()
                        bytes_to_read = 4096 - ((cur_offset + 4)%4096)
                        buf = self.infile.read(bytes_to_read)
                        if buf != b'\x00' * bytes_to_read:
                            self.infile.seek(ofs)
                            break
                else:
                    break
                prev_is_padding = True
                continue

            prev_is_padding = False

            # then read the size of the inode
            buf = self.infile.read(4)
            inode_size = int.from_bytes(buf, byteorder=self.byteorder)

            # skip dirty nodes
            if node_magic_type == 'dirty':
                self.infile.seek(cur_offset + inode_size)
                unpackedsize = self.infile.tell() - self.offset
                if unpackedsize % 4 != 0:
                    paddingbytes = 4 - (unpackedsize % 4)
                    self.infile.seek(paddingbytes, os.SEEK_CUR)
                    unpackedsize = self.infile.tell() - self.offset
                continue

            # skip CRC
            self.infile.seek(4, os.SEEK_CUR)

            # process directory entries
            if inode_type == DIRENT:
                # parent inode is first
                buf = self.infile.read(4)
                parentinode = int.from_bytes(buf, byteorder=self.byteorder)

                parent_inodes_seen.add(parentinode)

                # inode version is next
                buf = self.infile.read(4)
                inodeversion = int.from_bytes(buf, byteorder=self.byteorder)

                # inode number is next
                buf = self.infile.read(4)
                inode_number = int.from_bytes(buf, byteorder=self.byteorder)

                # skip unlinked inodes
                if jffs2_inode.data.inode_number == 0:
                    # first go back to the old offset, then skip
                    # the entire inode
                    self.infile.seek(cur_offset + inode_size)
                    unpackedsize = self.infile.tell() - self.offset
                    if unpackedsize % 4 != 0:
                        paddingbytes = 4 - (unpackedsize % 4)
                        self.infile.seek(paddingbytes, os.SEEK_CUR)
                        unpackedsize = self.infile.tell() - self.offset
                    continue

                # mctime is next, not interesting so no need to process
                buf = self.infile.read(4)

                # name length is next
                buf = self.infile.read(1)

                inodenamelength = ord(buf)

                # the dirent type is next. Not sure what to do with this
                # value at the moment
                buf = self.infile.read(1)

                # skip two unused bytes
                buf = self.infile.read(2)

                # the node CRC. skip for now
                buf = self.infile.read(4)

                # the name CRC
                buf = self.infile.read(4)
                namecrc = int.from_bytes(buf, byteorder=self.byteorder)

                # finally the name of the node
                buf = self.infile.read(inodenamelength)

                inode_name = buf.decode()

                # process any possible hard links
                if inode_number in inode_to_filename:
                    # the inode number is already known, meaning
                    # that this should be a hard link
                    inode_rel = self.rel_unpack_dir / inode_to_filename[inode_number]
                    outfile_rel = self.rel_unpack_dir / inode_name
                    inode_rel.link_to(outfile_rel)
                    fr = FileResult(self.fileresult, outfile_rel, set(['hardlink']))
                    unpacked_files.append(fr)

                # now add the name to the inode to filename mapping
                if parentinode in inode_to_filename:
                    inode_to_filename[inode_number] = os.path.join(inode_to_filename[parentinode], inode_name)

            elif inode_type == INODE:
                # inode number
                buf = self.infile.read(4)
                inode_number = int.from_bytes(buf, byteorder=self.byteorder)

                # first check if a file name for this inode is known
                if inode_number not in inode_to_filename:
                    break

                outfile_rel = self.rel_unpack_dir / inode_to_filename[inode_number]
                outfile_full = self.scan_environment.unpack_path(outfile_rel)

                # skip unlinked inodes
                if inode_number == 0:
                    # first go back to the old offset, then skip
                    # the entire inode
                    self.infile.seek(cur_offset + inode_size)
                    unpackedsize = self.infile.tell() - self.offset
                    if unpackedsize % 4 != 0:
                        paddingbytes = 4 - (unpackedsize % 4)
                        self.infile.seek(paddingbytes, os.SEEK_CUR)
                        unpackedsize = self.infile.tell() - self.offset
                    continue

                # version number
                buf = self.infile.read(4)
                inodeversion = int.from_bytes(buf, byteorder=self.byteorder)

                # file mode
                buf = self.infile.read(4)
                filemode = int.from_bytes(buf, byteorder=self.byteorder)

                if stat.S_ISSOCK(filemode):
                    # keep track of whatever is in the file and report
                    pass
                elif stat.S_ISDIR(filemode):
                    # create directories, but skip them otherwise
                    os.makedirs(outfile_full, exist_ok=True)
                    self.infile.seek(cur_offset + inode_size)
                    continue

                elif stat.S_ISLNK(filemode):
                    os.makedirs(outfile_full.parent, exist_ok=True)

                    # skip ahead 24 bytes to the size of the data
                    self.infile.seek(24, os.SEEK_CUR)

                    buf = self.infile.read(4)
                    linknamelength = int.from_bytes(buf, byteorder=self.byteorder)

                    # skip ahead 16 bytes to the data containing the link name
                    self.infile.seek(16, os.SEEK_CUR)
                    buf = self.infile.read(linknamelength)
                    link_name = buf.decode()

                    outfile_rel.symlink_to(link_name)
                    fr = FileResult(self.fileresult, outfile_rel, set(['symbolic link']))
                    unpacked_files.append(fr)
                elif stat.S_ISREG(filemode):
                    os.makedirs(outfile_full.parent, exist_ok=True)

                    # skip ahead 20 bytes to the offset of where to write data
                    self.infile.seek(20, os.SEEK_CUR)

                    # the write offset is useful as a sanity check: either
                    # it is 0, or it is the previous offset, plus the
                    # previous uncompressed length.
                    buf = self.infile.read(4)
                    writeoffset = int.from_bytes(buf, byteorder=self.byteorder)

                    if writeoffset == 0:
                        if inode_number in inode_to_write_offset:
                            break
                        if inode_number in inode_to_open_files:
                            break

                        # open a file and store it as a reference
                        outfile = open(outfile_full, 'wb')
                        inode_to_open_files[inode_number] = outfile
                        fr = FileResult(self.fileresult, outfile_rel, set())
                        unpacked_files.append(fr)

                        current_inode = inode_number
                    else:
                        if writeoffset != inode_to_write_offset[inode_number]:
                            break
                        if inode_number not in inode_to_open_files:
                            break
                        outfile = inode_to_open_files[inode_number]

                    # the offset to the compressed data length
                    buf = self.infile.read(4)
                    compressedsize = int.from_bytes(buf, byteorder=self.byteorder)

                    # read the decompressed size
                    buf = self.infile.read(4)
                    decompressed_size = int.from_bytes(buf, byteorder=self.byteorder)

                    # find out which compression algorithm has been used
                    buf = self.infile.read(1)
                    compression_used = ord(buf)

                    # skip ahead 11 bytes to the actual data
                    self.infile.seek(11, os.SEEK_CUR)
                    buf = self.infile.read(compressedsize)

                    # Check the compression that's used as it could be that
                    # for a file compressed and uncompressed nodes are mixed
                    # in case the node cannot be compressed efficiently
                    # and the compressed data would be larger than the
                    # original data.
                    if compression_used == COMPR_NONE:
                        # the data is not compressed, so can be written
                        # to the output file immediately
                        outfile.write(buf)
                    elif compression_used == COMPR_ZLIB:
                        # the data is zlib compressed, so first decompress
                        # before writing
                        uncompressed_data = zlib.decompress(buf)
                        if len(uncompressed_data) > decompressed_size:
                            outfile.write(uncompressed_data[:decompressed_size])
                        else:
                            outfile.write(uncompressed_data)
                    elif compression_used == COMPR_LZMA:
                        # The data is LZMA compressed, so create a
                        # LZMA decompressor with custom filter, as the data
                        # is stored without LZMA headers.
                        jffs_filters = [{'id': lzma.FILTER_LZMA1,
                                         'dict_size': LZMA_DICT_SIZE,
                                         'lc': LZMA_LC, 'lp': LZMA_LP,
                                         'pb': LZMA_PB}]

                        decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=jffs_filters)
                        uncompressed_data = decompressor.decompress(buf)
                        if len(uncompressed_data) > decompressed_size:
                            outfile.write(uncompressed_data[:decompressed_size])
                        else:
                            outfile.write(uncompressed_data)
                    elif compression_used == COMPR_RTIME:
                        # From: https://github.com/sviehb/jefferson/blob/master/src/jefferson/rtime.py
                        # First initialize the positions, set to 0
                        positions = [0] * 256

                        # create a bytearray, set everything to 0
                        data_out = bytearray([0] * decompressed_size)

                        # create counters
                        outpos = 0
                        pos = 0

                        # process all the bytes
                        while outpos < decompressed_size:
                            value = buf[pos]
                            pos += 1
                            data_out[outpos] = value
                            outpos += 1
                            repeat = buf[pos]
                            pos += 1

                            backoffs = positions[value]
                            positions[value] = outpos
                            if repeat:
                                if backoffs + repeat >= outpos:
                                    while repeat:
                                        data_out[outpos] = data_out[backoffs]
                                        outpos += 1
                                        backoffs += 1
                                        repeat -= 1
                                else:
                                    data_out[outpos : outpos + repeat] = data_out[
                                        backoffs : backoffs + repeat
                                    ]
                                    outpos += repeat
                        outfile.write(data_out)
                    elif compression_used == COMPR_LZO:
                        outfile.write(lzo.decompress(buf, False, decompressed_size))
                    else:
                        break

                    # flush any remaining data
                    inode_to_write_offset[inode_number] = writeoffset + decompressed_size
                    outfile.flush()

                    # unsure what to do here now
                    pass

            self.infile.seek(cur_offset + inode_size)
            unpackedsize = self.infile.tell() - self.offset
            if unpackedsize % 4 != 0:
                paddingbytes = 4 - (unpackedsize % 4)
                self.infile.seek(paddingbytes, os.SEEK_CUR)

        for i in inode_to_open_files:
            inode_to_open_files[i].close()
        return unpacked_files

    labels = ['jffs2', 'filesystem']
    metadata = {}
