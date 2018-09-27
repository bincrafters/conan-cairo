#!/usr/bin/env python
# -*- coding: utf-8 -*-

from conans import ConanFile, AutoToolsBuildEnvironment, tools, VisualStudioBuildEnvironment
import os


class CairoConan(ConanFile):
    name = "cairo"
    version = "1.15.14"
    description = "Cairo is a 2D graphics library with support for multiple output devices"
    url = "https://github.com/bincrafters/conan-cairo"
    homepage = "https://cairographics.org/"
    author = "Bincrafters <bincrafters@gmail.com>"
    license = "GNU LGPL 2.1"
    exports = ["LICENSE.md"]
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = "shared=False", "fPIC=True"

    source_subfolder = "source_subfolder"
    build_subfolder = "build_subfolder"
    requires = 'zlib/1.2.11@conan/stable', 'pixman/0.34.0@bincrafters/stable', 'libpng/1.6.34@bincrafters/stable'

    def config_options(self):
        del self.settings.compiler.libcxx
        if self.settings.os == 'Windows':
            del self.options.fPIC

    def build_requirements(self):
        if self.settings.os == 'Windows':
            self.build_requires('7z_installer/1.0@conan/stable')
            self.build_requires('msys2_installer/20161025@bincrafters/stable')

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
        os.rename('cairo-%s' % self.version, self.source_subfolder)
        os.unlink(archive_name)

    def build(self):
        if self.is_msvc:
            self.build_msvc()
        else:
            self.build_configure()

    def build_msvc(self):
        with tools.chdir(self.source_subfolder):
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

    def build_configure(self):
        raise Exception('TODO')

    def package(self):
        self.copy(pattern="LICENSE", dst="licenses", src=self.source_subfolder)
        if self.is_msvc:
            src = os.path.join(self.source_subfolder, 'src')
            self.copy(pattern="cairo-version.h", dst="include", src=self.source_subfolder)
            self.copy(pattern="cairo-features.h", dst="include", src=src)
            self.copy(pattern="cairo.h", dst="include", src=src)
            self.copy(pattern="cairo-deprecated.h", dst="include", src=src)
            self.copy(pattern="cairo-win32.h", dst="include", src=src)
            self.copy(pattern="cairo-script.h", dst="include", src=src)
            self.copy(pattern="cairo-ps.h", dst="include", src=src)
            self.copy(pattern="cairo-pdf.h", dst="include", src=src)
            self.copy(pattern="cairo-svg.h", dst="include", src=src)
            if self.options.shared:
                self.copy(pattern="*cairo.lib", dst="lib", src=src, keep_path=False)
                self.copy(pattern="*cairo.dll", dst="bin", src=src, keep_path=False)
            else:
                self.copy(pattern="*cairo-static.lib", dst="lib", src=src, keep_path=False)

    def package_info(self):
        if self.is_msvc:
            self.cpp_info.libs = ['cairo' if self.options.shared else 'cairo-static']
            if not self.options.shared:
                self.cpp_info.defines.append('CAIRO_WIN32_STATIC_BUILD=1')
        else:
            self.cpp_info.libs = ['cairo']
