extension_dir = join_paths(get_option('libdir'), 'eolie', 'webkitextension')

webkitextension = dependency('webkit2gtk-web-extension-4.0')
pyobject = dependency('pygobject-3.0')
python3 = dependency('python3')

shared_library('pythonloader',
               'pythonloader.c',
               dependencies: [webkitextension, pyobject, python3],
               install: true,
               install_dir: extension_dir)

configure_file(
  input: 'extension.py.in',
  output: 'extension.py',
  configuration: conf,
  install_dir: extension_dir
)
