#:/usr/bin/env python

from __future__ import print_function, absolute_import, division

import logging

from collections import defaultdict
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from sys import argv, exit
from time import time

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

if not hasattr(__builtins__, 'bytes'):
    bytes = str

bsize = 8

class Memory(LoggingMixIn, Operations):
    'Example memory filesystem. Supports only one level of files.'

    def __init__(self):
        self.files = {}
        self.data = defaultdict(bytes)
        self.fd = 0
        now = time()
        self.files['/'] = dict(st_mode=(S_IFDIR | 0o755), st_ctime=now,
                st_mtime=now, st_atime=now, st_nlink=2, files={})
    
    def findcur(self, path, indata = False):
        if indata:      #check if need self.data or self.files, True means need self.data
            p = self.data    #p is pointer
            for i in path.split('/') :
                p = p[i] if len(i) > 0 else p
        else:
            p = self.files['/']
            for i in path.split('/') :
                p = p['files'][i] if len(i) > 0 else p
        return p

    def findparent(self, path, indata = False):
        curfile = path[path.rfind('/')+1:]
        path = path[:path.rfind('/')]
        if indata:
            p = self.data
            for i in path.split('/') :
                p = p[i] if len(i) > 0 else p
        else:
            p = self.files['/']
            for i in path.split('/') :
                p = p['files'][i] if len(i) > 0 else p
        return p, curfile

    def chmod(self, path, mode):
        p = self.findcur(path)
        p['st_mode'] &= 0o770000
        p['st_mode'] |= mode
        return 0

    def chown(self, path, uid, gid):
        p = self.findcur(path)
        p['st_uid'] = uid
        p['st_gid'] = gid

    def create(self, path, mode):
        p, target = self.findparent(path)
        p['files'][target] = dict(st_mode=(S_IFREG | mode), st_nlink=1,
                     st_size=0, st_ctime=time(), st_mtime=time(),
                     st_atime=time())
        self.fd += 1
        return self.fd

    def getattr(self, path, fh=None):
        try:
            p = self.findcur(path)
        except KeyError:
            raise FuseOSError(ENOENT)
        return {attr:p[attr] for attr in p.keys() if attr != 'files'}

    def getxattr(self, path, name, position=0):
        p = self.findcur(path)
        attrs = p.get('attrs', {})

        try:
            return attrs[name]
        except KeyError:
            return ''       # Should return ENOATTR

    def listxattr(self, path):
        p = self.findcur(path)
        attrs = p.get('attrs', {})
        return attrs.keys()

    def mkdir(self, path, mode):
        p, dirname = self.findparent(path)
        p['files'][dirname] = dict(st_mode=(S_IFDIR | mode), st_nlink=2,
                                st_size=0, st_ctime=time(), st_mtime=time(),
                                st_atime=time(),files={})

        p['st_nlink'] += 1
        pdata, dirname = self.findparent(path,True)
        pdata[dirname] = defaultdict(bytes)

    def open(self, path, flags):
        self.fd += 1
        return self.fd

    def read(self, path, size, offset, fh):
#    	d1 = path[path.rfind('/')+1:]
    	d = self.findcur(path,True)
#    	p = self.files[path]
    	p = self.findcur(path)
    	if offset + size > p['st_size']:
            size = p['st_size'] - offset
        dd = ''.join(d[offset//bsize : (offset + size - 1)//bsize + 1])
        dd = dd[offset % bsize:offset % bsize + size]
        return dd

    def readdir(self, path, fh):
        p = self.findcur(path)['files']
        return ['.', '..'] + [x for x in p ]

    def readlink(self, path):
#        return ''.join(self.data[path])
        return self.findcur(path, True)

    def removexattr(self, path, name):
        p = self.findcur(path)
        attrs = p.get('attrs', {})

        try:
            del attrs[name]
        except KeyError:
            pass        # Should return ENOATTR

    def rename(self, old, new): #if it's a dir, need to modify the st_nlink for both old and new
#        self.files[new] = self.files.pop(old)
        pold, pold1 = self.findparent(old)
        pnew, pnew1 = self.findparent(new)
        if pold['files'][pold1]['st_mode'] & 0o770000 == S_IFDIR:
            pold['st_nlink'] -= 1
            pnew['st_nlink'] += 1

        pnew['files'][pnew1] = pold['files'].pop(pold1)
        dold, dold1 = self.findparent(old, True)
        dnew, dnew1 = self.findparent(new, True)
        dnew[dnew1] = dold.pop(dold1)

    def rmdir(self, path):
#        self.files.pop(path)
#        self.files['/']['st_nlink'] -= 1
        p, tar = self.findparent(path)
        p['files'].pop(tar)
        p['st_nlink'] -= 1



    def setxattr(self, path, name, value, options, position=0):
        # Ignore options
        p = self.findcur(path)
        attrs = p.setdefault('attrs', {})
        attrs[name] = value

    def statfs(self, path):
        return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)

    def symlink(self, target, source):
	p, tar = self.findparent(target)
	p['files'][tar] = dict(st_mode=(S_IFLNK | 0o777), st_nlink=1,
                                  st_size=len(source))
#        d1 =target[target.rfind('/')+1:]
        d, d1 = self.findparent(target, True)
        d[d1] = [source[i:i+bsize] for i in range(0, len(source), bsize)]

    def truncate(self, path, length, fh=None):
        d,d1 = self.findparent(path,True)
#        d1 = path[path.rfind('/')+1:]
#    	d = self.data

        d[d1] = [(d[d1][i] if i < len(d[d1]) else '').ljust(bsize, '\x00') for i in range(length//bsize)] \
                + [(d[d1][length//bsize][:length % bsize] if length//bsize < len(d[d1]) else '').ljust(length % bsize, '\x00')]
#        p = self.files[path]
	p = self.findcur(path)
        p['st_size'] = length

    def unlink(self, path):
        p, tar = self.findparent(path)
        p['files'].pop(tar)

    def utimens(self, path, times=None):
        now = time()
        atime, mtime = times if times else (now, now)
        p = self.findcur(path)
        p['st_atime'] = atime
        p['st_mtime'] = mtime

    def write(self, path, data, offset, fh):
        p = self.findcur(path)
#    	p = self.files[path]
#        d1 = path[path.rfind('/')+1:]
        d,d1 = self.findparent(path,True)
#    	d = self.data
        if offset > p['st_size']:
            d[d1] = [(d[d1][i] if i < len(d[d1]) else '').ljust(bsize, '\x00') for i in range(offset//bsize)] \
                    + [(d[d1][offset//bsize][:offset % bsize] if offset//bsize < len(d[d1]) else '').ljust(offset % bsize, '\x00')]
        size = len(data)
        sdata = [data[:bsize - (offset % bsize)]] + [data[i:i+bsize] for i in range(bsize - (offset % bsize), size, bsize)]
        blks = range(offset//bsize, (offset + size - 1)//bsize + 1)
        mod = blks[:]
        mod[0] = (d[d1][blks[0]][:offset % bsize] if blks[0] < len(d[d1]) else '').ljust(offset % bsize, '\x00') + sdata[0]
        if len(mod[0]) != bsize and blks[0] < len(d[d1]):
            mod[0] = mod[0] + d[d1][blks[0]][len(mod[0]):]
        mod[1:-1] = sdata[1:-1]
        if len(blks) > 1:
            mod[-1] = sdata[-1] + (d[d1][blks[-1]][len(sdata[-1]):] if blks[-1] < len(d[d1]) else '')
        d[d1] = mod
        p['st_size']= offset + size if offset + size > p['st_size'] else p['st_size']
        return size


if __name__ == '__main__':
    if len(argv) != 2:
        print('usage: %s <mountpoint>' % argv[0])
        exit(1)

    logging.basicConfig(level=logging.DEBUG)
    fuse = FUSE(Memory(), argv[1], foreground=True)
