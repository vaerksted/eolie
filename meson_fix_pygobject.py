#!/usr/bin/env python3

from os import environ, path, chdir, walk, rename, mkdir
from subprocess import call
from shutil import move
import sys

def find(name, p):
    for root, dirs, files in walk(p):
        if name in dirs:
            return path.join(root, name)

extensiondir = sys.argv[1]
gidir = path.join(extensiondir, 'gi')
prefix = environ.get('MESON_INSTALL_PREFIX', '/usr/local')
datadir = path.join(prefix, 'share')
builddir = environ.get('MESON_BUILD_ROOT')
tmproot = path.join(builddir, "tmp")
sourcedir = environ.get('MESON_SOURCE_ROOT')
patch = path.join(sourcedir, 'python-gobject-fix-segfault.diff')
pyobjectdir = path.join(sourcedir, "subprojects", "python-gobject")

if not path.exists(gidir):
    print('Installing python-gobject fix')
    call(['git', 'submodule', 'init'])
    call(['git', 'submodule', 'update'])
    chdir(pyobjectdir)
    call(['patch', '-p1', '-i', patch])
    call(['./autogen.sh', '--prefix', tmproot, '--enable-cairo'])
    call(['make'])
    call(['make', 'install'])
    buildgidir = find('gi', tmproot)
    move(buildgidir, gidir)
    call(['patch', '-R', '-p1', '-i', patch])
    chdir(sourcedir)
