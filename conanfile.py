#!/usr/bin/env python
# -*- coding: utf-8 -*-

from conans import ConanFile, AutoToolsBuildEnvironment, tools, VisualStudioBuildEnvironment
import os
import glob
import shutil


class CairoConan(ConanFile):
    name = "cairo"
    version = "1.17.2"
    description = "Cairo is a 2D graphics library with support for multiple output devices"
    topics = ("conan", "cairo", "graphics")
    url = "https://github.com/bincrafters/conan-cairo"
    homepage = "https://cairographics.org/"
    author = "Bincrafters <bincrafters@gmail.com>"
    license = ("LGPL-2.1-only", "MPL-1.1")
    exports = ["LICENSE.md"]
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "fPIC": [True, False], "enable_ft": [True, False], "enable_fc": [True, False]}
    default_options = {'shared': False, 'fPIC': True, "enable_ft": True, "enable_fc": True}
    generators = "pkg_config"

    _source_subfolder = "source_subfolder"
    _build_subfolder = "build_subfolder"

    def config_options(self):
        del self.settings.compiler.libcxx
        if self.settings.os == 'Windows':
            del self.options.fPIC

    def requirements(self):
        if self.options.enable_ft:
            self.requires("freetype/2.10.0@bincrafters/stable")
        if self.options.enable_fc:
            self.requires("fontconfig/2.13.91@conan/stable")
        self.requires("zlib/1.2.11@conan/stable")
        self.requires("pixman/0.38.0@bincrafters/stable")
        self.requires("libpng/1.6.37@bincrafters/stable")

    def build_requirements(self):
        if self.settings.os == 'Windows':
            self.build_requires('7z_installer/1.0@conan/stable')
            if "CONAN_BASH_PATH" not in os.environ:
                self.build_requires('msys2_installer/20161025@bincrafters/stable')
        if not tools.which("pkg-config"):
            self.build_requires("pkg-config_installer/0.29.2@bincrafters/stable")

    @property
    def is_msvc(self):
        return self.settings.compiler == 'Visual Studio'

    def source(self):
        tarball_name = 'cairo-%s.tar' % self.version
        archive_name = '%s.xz' % tarball_name
        tools.download('https://www.cairographics.org/snapshots/%s' % archive_name, archive_name)

        if self.settings.os == 'Windows':
            self.run('7z x %s' % archive_name)
            self.run('7z x %s' % tarball_name)
            os.unlink(tarball_name)
        else:
            self.run('tar -xJf %s' % archive_name)
        os.rename('cairo-%s' % self.version, self._source_subfolder)
        os.unlink(archive_name)

    def build(self):
        if self.is_msvc:
            self.build_msvc()
        else:
            self.build_configure()

    def build_msvc(self):
        with tools.chdir(self._source_subfolder):
            # https://cairographics.org/end_to_end_build_for_win32/
            win32_common = os.path.join('build', 'Makefile.win32.common')
            tools.replace_in_file(win32_common, '-MD ', '-%s ' % self.settings.compiler.runtime)
            tools.replace_in_file(win32_common, '-MDd ', '-%s ' % self.settings.compiler.runtime)
            tools.replace_in_file(win32_common, '$(ZLIB_PATH)/zdll.lib', self.deps_cpp_info['zlib'].libs[0] + '.lib')
            tools.replace_in_file(win32_common, '$(LIBPNG_PATH)/libpng.lib',
                                  self.deps_cpp_info['libpng'].libs[0] + '.lib')
            tools.replace_in_file(win32_common, '$(PIXMAN_PATH)/pixman/$(CFG)/pixman-1.lib',
                                  self.deps_cpp_info['pixman'].libs[0] + '.lib')
            with tools.vcvars(self.settings):
                env_msvc = VisualStudioBuildEnvironment(self)
                env_msvc.flags.append('/FS')  # C1041 if multiple CL.EXE write to the same .PDB file, please use /FS
                with tools.environment_append(env_msvc.vars):
                    env_build = AutoToolsBuildEnvironment(self)
                    env_build.make(args=['-f', 'Makefile.win32', 'CFG=%s' % str(self.settings.build_type).lower()])

    def copy_pkg_config(self, name):
        root = self.deps_cpp_info[name].rootpath
        pc_dir = os.path.join(root, 'lib', 'pkgconfig')
        pc_files = glob.glob('%s/*.pc' % pc_dir)
        if not pc_files:  # zlib store .pc in root
            pc_files = glob.glob('%s/*.pc' % root)
        for pc_name in pc_files:
            new_pc = os.path.join('pkgconfig', os.path.basename(pc_name))
            self.output.warn('copy .pc file %s' % os.path.basename(pc_name))
            shutil.copy(pc_name, new_pc)
            prefix = tools.unix_path(root) if self.settings.os == 'Windows' else root
            tools.replace_prefix_in_pc_file(new_pc, prefix)

    def build_configure(self):
        with tools.chdir(self._source_subfolder):
            # disable build of test suite
            tools.replace_in_file(os.path.join('test', 'Makefile.am'), 'noinst_PROGRAMS = cairo-test-suite$(EXEEXT)',
                                  '')
            os.makedirs('pkgconfig')
            # FIXME : should be replaced by pkg_config generator once components feature is out
            for lib in ['libpng', 'zlib', 'pixman', 'freetype', 'fontconfig', 'Expat']:
                self.copy_pkg_config(lib)
            shutil.copy(os.path.join(self.build_folder, "bzip2.pc"), os.path.join("pkgconfig", "bzip2.pc"))

            if self.options.enable_ft:
                self.copy_pkg_config('freetype')
                tools.replace_in_file(os.path.join(self.source_folder, self._source_subfolder, "src", "cairo-ft-font.c"),
                                      '#if HAVE_UNISTD_H', '#ifdef HAVE_UNISTD_H')

            pkg_config_path = os.path.abspath('pkgconfig')
            pkg_config_path = tools.unix_path(pkg_config_path) if self.settings.os == 'Windows' else pkg_config_path

            configure_args = ['--enable-ft' if self.options.enable_ft else '--disable-ft',
                              '--enable-fc' if self.options.enable_fc else '--disable-fc']
            if self.options.shared:
                configure_args.extend(['--disable-static', '--enable-shared'])
            else:
                configure_args.extend(['--enable-static', '--disable-shared'])

            env_build = AutoToolsBuildEnvironment(self)
            if self.settings.os == 'Macos':
                env_build.link_flags.extend(['-framework CoreGraphics',
                                             '-framework CoreFoundation'])
            if str(self.settings.compiler) in ['gcc', 'clang', 'apple-clang']:
                env_build.flags.append('-Wno-enum-conversion')
            with tools.environment_append(env_build.vars):
                self.run('PKG_CONFIG_PATH=%s NOCONFIGURE=1 ./autogen.sh' % pkg_config_path)
                env_build.pic = self.options.fPIC
                env_build.configure(args=configure_args, pkg_config_paths=[pkg_config_path])
                env_build.make()
                env_build.install()

    def package(self):
        self.copy(pattern="LICENSE", dst="licenses", src=self._source_subfolder)
        if self.is_msvc:
            src = os.path.join(self._source_subfolder, 'src')
            inc = os.path.join('include', 'cairo')
            self.copy(pattern="cairo-version.h", dst=inc, src=self._source_subfolder)
            self.copy(pattern="cairo-features.h", dst=inc, src=src)
            self.copy(pattern="cairo.h", dst=inc, src=src)
            self.copy(pattern="cairo-deprecated.h", dst=inc, src=src)
            self.copy(pattern="cairo-win32.h", dst=inc, src=src)
            self.copy(pattern="cairo-script.h", dst=inc, src=src)
            self.copy(pattern="cairo-ft.h", dst=inc, src=src)
            self.copy(pattern="cairo-ps.h", dst=inc, src=src)
            self.copy(pattern="cairo-pdf.h", dst=inc, src=src)
            self.copy(pattern="cairo-svg.h", dst=inc, src=src)
            if self.options.shared:
                self.copy(pattern="*cairo.lib", dst="lib", src=src, keep_path=False)
                self.copy(pattern="*cairo.dll", dst="bin", src=src, keep_path=False)
            else:
                self.copy(pattern="*cairo-static.lib", dst="lib", src=src, keep_path=False)
                shutil.move(os.path.join(self.package_folder, 'lib', "cairo-static.lib"),
                            os.path.join(self.package_folder, 'lib', "cairo.lib"))

    def package_info(self):
        self.cpp_info.libs = ['cairo']
        if self.is_msvc and not self.options.shared:
            self.cpp_info.defines.append('CAIRO_WIN32_STATIC_BUILD=1')
        self.cpp_info.includedirs.append(os.path.join('include', 'cairo'))
