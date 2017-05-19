#
# Makefile
# Adrian Perez, 2015-08-25 11:58
#

webkitextensiondir = $(datadir)/eolie/webkitextension
webkitextension_DATA = extension.py

extension.py: extension.py.in Makefile
	$(AM_V_GEN)sed                                          \
		-e s!\@pythondir\@!$(pythondir)!        \
		-e s!\@pyexecdir\@!$(pyexecdir)!        \
		< $< > $@
	chmod a+x $@

libpythonloader_la_SOURCES=libpythonloader.c
libpythonloader_la_CFLAGS=$(WEBKIT2GTK_WEB_EXTENSION_CFLAGS)\
                          $(PYGOBJECT_CFLAGS)\
                          $(PYTHON_CFLAGS)
libpythonloader_la_LDFLAGS=$(PYTHON_LDFLAGS)
webkitextension_LTLIBRARIES = libpythonloader.la

EXTRA_DIST = \
    extension.py.in\
	$(webkitextension_DATA)

CLEANFILES = \
    $(lib_LTLIBRARIES)

-include $(top_srcdir)/git.mk
