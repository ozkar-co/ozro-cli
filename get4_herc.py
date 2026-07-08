#! /usr/bin/env python3
# coding: UTF-8
#
# Hercules Ragexe downloader (Python 3 port).
# Fetches a client .rgz from the known kRO patch mirrors, unpacks it and
# writes the contained Ragexe as <client>.exe in the current directory.
#
# Usage:
#   python3 get4_herc.py <client-name> [sha256]
#   e.g. python3 get4_herc.py 2021-11-03bRagexeRE

import gzip
import hashlib
import io
import logging
import ntpath
import os
import os.path
import struct
import sys
import urllib.request

timeout = 120
log = logging.getLogger('download')

# Patch mirrors tried in order (deobfuscated from the original script).
MIRRORS = [
    "https://nemo.romirrors.com/kro/",
    "http://ropatch.gnjoy.com/Patch/",
    "http://ropatch.gnjoy.com/Patchfile_Test/",
    "http://loot.ai4rei.net/etc/mirror/kro/Patch/",
]


def uncompress_rgz(data, file_name, dst_path, check_sum=None):
    if check_sum is not None:
        digest = hashlib.sha256(data).hexdigest()
        if digest != check_sum:
            raise Exception("Error: wrong checksum or file corrupted")

    byte_stream = io.BytesIO(data)
    rgz_file = gzip.GzipFile(fileobj=byte_stream)

    lexer = Lexer(rgz_file)
    fs = FileSystem(dst_path)

    token = lexer.next()
    while not token.is_end:
        if token.is_dir:
            if not fs.dir_exists(token.dir_name):
                log.info('Create dir: %s', token.dir_name)
                fs.create_dir(token.dir_name)
        elif token.is_file:
            out_name = file_name + ".exe"
            log.info('Create file: %s: %d', out_name, token._length)
            fs.create_file(out_name, token.file_chunks)
        token = lexer.next()

    log.info('Done')


class Lexer(object):
    def __init__(self, file):
        self._file = file

    def next(self):
        entry_type = self._file.read(1)

        if entry_type == b'd':
            token = self._read_dir()
        elif entry_type == b'f':
            token = self._read_file()
        elif entry_type == b'e':
            log.info("Archive end detected")
            token = self._read_archive_end()
        elif entry_type == b'':
            token = self._read_end()
        else:
            e = UnknownTokenError()
            e.entry_type = entry_type
            e.pos = self._file.tell() - 1
            raise e
        return token

    def _read_dir(self):
        dir_name = self._read_string()
        return DirToken(dir_name)

    def _read_file(self):
        file_name = self._read_string()
        length, = struct.unpack('<L', self._file.read(4))
        return FileToken(file_name, self._file, length)

    def _read_end(self):
        return EndToken()

    def _read_archive_end(self):
        self._read_string()
        return ArchiveEndToken()

    def _read_string(self):
        length, = struct.unpack('<B', self._file.read(1))
        raw = self._file.read(length)
        if raw and raw[-1] == 0:
            raw = raw[:-1]
        return raw.decode("euc-kr")


class UnknownTokenError(Exception):
    def __init__(self, *args):
        super(UnknownTokenError, self).__init__(*args)
        self.entry_type = None
        self.pos = None


class Token(object):
    is_dir = False
    is_end = False
    is_file = False
    is_archive_end = False


class DirToken(Token):
    is_dir = True

    def __init__(self, dir_name):
        self.dir_name = dir_name


class EndToken(Token):
    is_end = True


class ArchiveEndToken(Token):
    is_archive_end = True


class FileToken(Token):
    is_file = True
    CHUNK_LENGTH = 1024 ** 2

    def __init__(self, file_name, file, length):
        self.file_name = file_name
        self._file = file
        self._length = length

    @property
    def file_chunks(self):
        remaining = self._length
        while remaining > 0:
            chunk = min(self.CHUNK_LENGTH, remaining)
            data = self._file.read(chunk)
            if not data:
                break
            remaining -= len(data)
            yield data


class FileSystem(object):
    def __init__(self, root_path):
        self._root_path = os.path.abspath(root_path)
        self.existingFiles = {}

    def fixFileName(self, file_name):
        if file_name not in self.existingFiles:
            self.existingFiles[file_name] = 1
            return file_name
        cnt = self.existingFiles[file_name] + 1
        name, ext = os.path.splitext(file_name)
        log.error("Found duplicate for file "
                  "'{0}'. Renaming.".format(file_name))
        file_name = "{0}_{1}{2}".format(name, cnt, ext)
        self.existingFiles[file_name] = cnt
        return file_name

    def dir_exists(self, dir_name):
        dir_name = self._adopt_path(dir_name)
        return os.path.exists(dir_name)

    def create_dir(self, dir_name):
        dir_name = self._adopt_path(dir_name)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

    def create_file(self, file_name, file):
        file_name = self._adopt_path(file_name)
        dir_name = os.path.dirname(file_name)
        file_name = self.fixFileName(file_name)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)
        with io.open(file_name, 'wb') as dst_file:
            for chunk in file:
                dst_file.write(chunk)

    def _adopt_path(self, pathname):
        pathname = pathname.replace(ntpath.sep, os.path.sep)
        pathname = os.path.abspath(os.path.join(self._root_path, pathname))

        pref = os.path.commonprefix([self._root_path, pathname])
        err = 'Access out of root directory is forbidden: %s' % pathname
        assert pref == self._root_path, err

        pathname = os.path.relpath(pathname, self._root_path)

        target_path = []
        while pathname:
            head, tail = os.path.split(pathname)
            if tail:
                target_path.insert(0, tail)
            pathname = head

        host_path = []
        while len(host_path) < len(target_path):
            pathname = os.path.join(self._root_path, *host_path)
            name = target_path[len(host_path)]
            if os.path.isdir(pathname):
                for existent_name in sorted(os.listdir(pathname)):
                    if existent_name.lower() == name.lower():
                        name = existent_name
                        break
            host_path.append(name)
        return os.path.join(self._root_path, *host_path)


def errorExit():
    if os.name == 'nt':
        print("Press any key...")
        import msvcrt
        msvcrt.getch()
    sys.exit(1)


def getClientName(argv):
    if len(sys.argv) == 2:
        return (sys.argv[1], None)
    elif len(sys.argv) == 3:
        return (sys.argv[1], sys.argv[2])
    name = os.path.basename(argv[0])
    idx = name.find("(")
    if idx >= 0:
        idx2 = name.find(")")
        if idx2 > idx:
            name = name[:idx].strip() + name[idx2 + 1:]
    if name.find("get_") != 0:
        print("Error: missing client name")
        errorExit()
    name = name[4:-3]
    if name and name[-1] == ".":
        name = name[:-1]
    if len(name) <= 62:
        return (name, None)
    idx = name.rfind("_")
    if idx <= 0:
        print("Error: corrupted client name")
        errorExit()
    checkSum = name[idx + 1:]
    name = name[:idx]
    return (name, checkSum)


def download(archive_name, client, check_sum):
    for base_url in MIRRORS:
        url = base_url + archive_name
        try:
            log.info("Trying mirror: %s", url)
            req = urllib.request.Request(
                url, headers={'User-Agent': 'Mozilla/5.0 (get4_herc)'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            uncompress_rgz(data, client, ".", check_sum)
            return True
        except Exception as e:
            print("Error from mirror {0}: {1}".format(base_url, e))
    return False


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    client, checkSum = getClientName(sys.argv)
    print("Please wait...")
    archiveName = client + ".rgz"
    if archiveName == "2020-07-09_sakaRagexeRE.rgz":
        archiveName = "RO_" + archiveName
    if not download(archiveName, client, checkSum):
        print("Error: could not download '{0}' from any mirror".format(
            archiveName))
        errorExit()
    if os.name == 'nt':
        print("Press any key...")
        import msvcrt
        msvcrt.getch()
