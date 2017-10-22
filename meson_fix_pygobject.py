#!/usr/bin/env python3

from os import environ, path, chdir, walk, rename, mkdir
from subprocess import call
from shutil import move

def find(name, p):
    for root, dirs, files in walk(p):
        if name in dirs:
            return path.join(root, name)

prefix = environ.get('MESON_INSTALL_PREFIX', '/usr/local')
datadir = path.join(prefix, 'share')
libdir = path.join(prefix, 'lib')
eoliedir = path.join(libdir, 'eolie')
builddir = environ.get('MESON_BUILD_ROOT')
tmproot = path.join(builddir, "tmp")
sourcedir = environ.get('MESON_SOURCE_ROOT')
patch = path.join(sourcedir, 'python-gobject-fix-segfault.diff')
pyobjectdir = path.join(sourcedir, "subprojects", "python-gobject")

if not path.exists(eoliedir + '/gi'):
    print('Installing python-gobject fix')
    call(['git', 'submodule', 'init'])
    call(['git', 'submodule', 'update'])
    chdir(pyobjectdir)
    call(['patch', '-p1', '-i', patch])
    call(['./autogen.sh', '--prefix', tmproot, '--disable-cairo'])
    call(['make'])
    call(['make', 'install'])
    gidir = find('gi', tmproot)
    move(gidir, eoliedir)
    call(['patch', '-R', '-p1', '-i', patch])
    chdir(sourcedir)
