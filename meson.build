project(
  'omniebook',
  version: '1.3.0',
  license: 'GPL-3.0-or-later',
  meson_version: '>= 0.59.0',
  default_options: ['buildtype=plain'],
)

python = import('python').find_installation('python3')

prefix = get_option('prefix')
bindir = join_paths(prefix, get_option('bindir'))
libdir = join_paths(prefix, get_option('libdir'))
datadir = join_paths(prefix, get_option('datadir'))
omniebook_libdir = join_paths(libdir, 'omniebook')

# Launcher
install_data(
  'bin/omniebook',
  install_dir: bindir,
  install_mode: 'rwxr-xr-x',
)

subdir('omniebook')
subdir('data')

docdir = join_paths(datadir, 'doc', 'omniebook')
licensedir = join_paths(datadir, 'licenses', 'omniebook')
install_data('LICENSE', install_dir: licensedir)
install_data('README.md', install_dir: docdir)

summary({
  'Prefix': prefix,
  'Python': python.path(),
  'Library dir': omniebook_libdir,
}, section: 'OmniEbook')
