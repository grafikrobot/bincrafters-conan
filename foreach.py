# Copyright Rene Rivera 2017-2018

import os.path
import glob
from subprocess import check_call, call, check_output
import pprint
import argparse
from time import sleep
import re
from types import BooleanType
import difflib

conan_scope = "bincrafters/testing"
args = None


class Commands():

    def __init__(self, args):
        self.args = args

    def __check_call__(self, command, args):
        if args.trace:
            print('EXEC: "' + '" "'.join(command) + '"')
        else:
            check_call(command)

    def __call__(self, command, args):
        if args.trace:
            print('EXEC: "' + '" "'.join(command) + '"')
        else:
            call(command)

    def __re_search__(self, p, s, default=None):
        s = re.search(p, s)
        return s.group(1) if s else default

    def __cf_get__(self, name, cf, default=False):
        if type(default) == type(True):
            re = '''%s = (True|False|[{][^}]+[}])''' % (name)
            return eval(self.__re_search__(re, cf, default=str(default)))
        if type(default) == type({}):
            re = '''%s = ([{][^}]+[}])''' % (name)
            return eval(self.__re_search__(re, cf, default=str(default)))
        if type(default) == type([]):
            re = '''%s = ([\[][^\]]+[\]])''' % (name)
            return eval(self.__re_search__(re, cf, default=str(default)))
        if type(default) == type(tuple()):
            re = '''%s = ([^\n]+)''' % (name)
            return eval('tuple(['+self.__re_search__(re, cf, default=str(default))+'])')
        else:
            re = '''%s = ['"]([^'"]+)''' % (name)
            return self.__re_search__(re, cf, default=default)

    def __info__(self, args):
        result = {}
        if os.path.isfile(os.path.join(os.getcwd(), 'conanfile.py')):
            with open(os.path.join(os.getcwd(), 'conanfile.py')) as f:
                cf = f.read()
            result['name'] = self.__cf_get__('name', cf, default="")
            result['url'] = self.__cf_get__(
                'url', cf, default="https://github.com/bincrafters/conan-"+result['name'])
            result['lib_short_names'] = self.__cf_get__(
                'lib_short_names', cf, default=[])
            result['source_only_deps'] = self.__cf_get__(
                'source_only_deps', cf, default=[])
            result['header_only_libs'] = self.__cf_get__(
                'header_only_libs', cf, default=[])
            result['cycle_group'] = self.__cf_get__(
                'cycle_group', cf, default=None)
            result['options'] = self.__cf_get__('options', cf, default={})
            result['default_options'] = self.__cf_get__(
                'default_options', cf, default=tuple())
            result['b2_requires'] = self.__cf_get__(
                'b2_requires', cf, default=[])
            result['b2_build_requires'] = self.__cf_get__(
                'b2_build_requires', cf, default=[])
            result['b2_defines'] = self.__cf_get__(
                'b2_defines', cf, default=[])
            result['b2_options'] = self.__cf_get__(
                'b2_options', cf, default={})

            result['key'] = result['name'].replace('boost_', '')
            result['is_cycle_group'] = result['key'].startswith('cycle_group')
            result['is_in_cycle_group'] = True if result['cycle_group'] else False
            result['is_header_only'] = result['key'] in result['header_only_libs']
        return result

    def __write_file__(self, path, content, args, create_if_absent=False):
        if os.path.exists(path) or create_if_absent:
            if args.trace:
                print("FILE: " + os.path.basename(path).upper() + "\n" + content)
            else:
                with open(os.path.join(path), 'w') as f:
                    f.write(content)

    def __lines__(self, lines):
        return [x.rstrip()+'\n' for x in lines]

    def info(self, args):
        print('DIR: ' + os.getcwd())
        cf = self.__info__(args)
        print('NAME: ' + cf['name'])
        print('URL: ' + cf['url'])
        print('LIB_SHORT_NAMES: ' + str(cf['lib_short_names']))
        print('SOURCE_ONLY_DEPS: ' + str(cf['source_only_deps']))
        print('HEADER_ONLY_LIBS: ' + str(cf['header_only_libs']))
        print('CYCLE_GROUP: ' + str(cf['cycle_group']))
        print('OPTIONS: ' + str(cf['options']))
        print('DEFAULT_OPTIONS: ' + str(cf['default_options']))
        print('B2_REQUIRES: ' + str(cf['b2_requires']))
        print('B2_RBUILD_EQUIRES: ' + str(cf['b2_build_requires']))
        print('B2_DEFINES: ' + str(cf['b2_defines']))
        print('B2_OPTIONS: ' + str(cf['b2_options']))
        print('KEY: ' + str(cf['key']))
        print('IS_CYCLE_GROUP: ' + str(cf['is_cycle_group']))
        print('IS_IN_CYCLE_GROUP: ' + str(cf['is_in_cycle_group']))
        print('IS_HEADER_ONLY: ' + str(cf['is_header_only']))
        ci = []
        if os.path.isfile(os.path.join(os.getcwd(), '.travis.yml')):
            ci.append('Travis')
        if os.path.isfile(os.path.join(os.getcwd(), 'appveyor.yml')):
            ci.append('Appveyor')
        print('CI: ' + ', '.join(ci))
        if os.path.exists(os.path.join(os.getcwd(), ".git")):
            call(["git", "status", "-bsu", "--ignored"])

    def upload_source_only(self, args):
        cf = self.__info__(args)
        if cf['is_header_only']:
            self.__check_call__([
                'conan', 'upload',
                cf['name'] + '/' + cf['version'] + '@' + conan_scope,
                '--all', '-r', 'bincrafters'
            ], args)
        elif cf['is_in_cycle_group']:
            self.__check_call__([
                'conan', 'upload',
                cf['name'] + '/' + cf['version'] + '@' + conan_scope,
                '-r', 'bincrafters'
            ], args)

    __ignore_libs__ = set([
        'mpi', 'graph_parallel', 'numeric_odeint'
    ])

    @property
    def ignore_libs(self):
        if self.args.no_ignore_libs:
            return set()
        else:
            return self.__ignore_libs__

    header_only_libs = set([
        'function_types', 'system'
    ])

    short_names = {
        'numeric_interval': 'interval',
        'numeric_odeint': 'odeint',
        'numeric_ublas': 'ublas'
    }

    def get_lib_name(self, lib):
        if lib in self.short_names:
            return self.short_names[lib]
        else:
            return lib

    def __read_deps__(self, deps):
        deps_info = {}
        with open(deps) as f:
            deps_txt = f.readlines()
        for l in deps_txt:
            i = l.split('->')
            lib = i[0].strip().replace('~', '_')
            lib_deps = [x.replace('~', '_') for x in i[1].split()]
            lib_deps = list(set(lib_deps) - self.ignore_libs)
            if not lib in self.ignore_libs:
                deps_info[lib] = lib_deps
        return deps_info

    def generate_pre(self, args):
        if args.generate_deps_build:
            self.generate_deps_build = set()
            with open(args.generate_deps_build) as f:
                build_txt = f.readlines()
            for l in build_txt:
                self.generate_deps_build.add(
                    self.__re_search__('''libs/([^/]+)''', l))
            self.generate_deps_build -= self.header_only_libs
        if args.generate_deps_header:
            self.generate_deps_header = self.__read_deps__(
                args.generate_deps_header)
        if args.generate_deps_source:
            self.generate_deps_source = self.__read_deps__(
                args.generate_deps_source)
            for header_only_lib in self.header_only_libs:
                self.generate_deps_source[header_only_lib] = list()
        for dep_build in self.generate_deps_build:
            for dep_source in self.generate_deps_source.keys():
                if dep_build in self.generate_deps_source[dep_source]:
                    self.generate_deps_source[dep_source].remove(dep_build)
                    self.generate_deps_header[dep_source].append(dep_build)
                    self.generate_deps_header[dep_source].sort()
        if args.generate_deps_levels:
            deps_info = {}
            with open(args.generate_deps_levels) as f:
                deps_txt = f.readlines()
            level_i = None
            self.levelgroups = {}
            for l in deps_txt:
                l = l.strip()
                if l and not level_i:
                    if l.startswith('Level '):
                        level_i = int(l[6:-1])
                        self.levelgroups[level_i] = {
                            'index': level_i,
                            'lib_short_names': set(),
                            'requires': set()}
                        l = None
                if l == '':
                    l = None
                    level_i = None
                if l and level_i:
                    i = l.split('->')
                    lib = i[0].strip().replace('~', '_')
                    lib_deps = [x.replace('~', '_') for x in i[1].split()]
                    for lib_dep in lib_deps:
                        lib_level = int(self.__re_search__(
                            r'[(]([0-9]+)[)]', lib_dep))
                        lib_name = self.__re_search__(r'([^(]+)', lib_dep)
                        if lib_level == level_i and lib_name not in self.ignore_libs:
                            self.levelgroups[level_i]['lib_short_names'].add(
                                lib_name)
            for (i, lg) in self.levelgroups.iteritems():
                for l in lg['lib_short_names']:
                    if l in self.generate_deps_header:
                        lg['requires'] |= set(self.generate_deps_header[l])
                lg['requires'] -= lg['lib_short_names']
            # pprint.pprint(self.levelgroups)
            self.cycle_group = {}
            cycle_group_i = 0
            cycle_group_k = 'abcd'
            for level_i in sorted(self.levelgroups.keys()):
                if len(self.levelgroups[level_i]['lib_short_names']) > 0:
                    cycle_group_name = 'cycle_group_' + \
                        (cycle_group_k[cycle_group_i])
                    self.cycle_group[cycle_group_name] = self.levelgroups[level_i]
                    cycle_group_i += 1
            pprint.pprint(self.cycle_group)

    def __find_lib_cycle_group__(self, key):
        for ck, cv in self.cycle_group.items():
            if key in cv['lib_short_names']:
                return ck
        return None

    def generate(self, args):
        if os.path.isfile(os.path.join(os.getcwd(), 'conanfile.py')):
            cf_info = self.__info__(args)
            if args.generate_version:
                cf_info['version'] = args.generate_version
                cf_info['version_flat'] = args.generate_version.replace(
                    '.', '_')
            with open(os.path.join(os.getcwd(), 'conanfile.py')) as f:
                cf_py = f.readlines()
            result_py = []
            parse_state = 'pre'
            parse_states = set()
            requires_user = set()
            requires_source = set()
            requires_user_current = set()
            requires_source_current = set()
            did_name_field = False
            # Set the grouped libs from the boostdep data..
            cf_info['is_in_cycle_group'] = False
            for cg in self.cycle_group.keys():
                if cf_info['key'] in self.cycle_group[cg]['lib_short_names']:
                    cf_info['is_in_cycle_group'] = True
                    cf_info['cycle_group'] = 'boost_'+cg
                    cf_info['b2_requires'] = [cf_info['cycle_group']]
                    cf_info['cycle_group_index'] = self.cycle_group[cg]['index']
                    break
            #
            if not cf_info['is_cycle_group']:
                cf_info['lib_short_names'] = [
                    self.get_lib_name(cf_info['key'])]
                cf_info['header_only_libs'] = [
                ] if cf_info['key'] in self.generate_deps_build else [self.get_lib_name(cf_info['key'])]
            if not cf_info['is_cycle_group'] and not cf_info['is_in_cycle_group']:
                if args.generate_deps_header:
                    requires_user.update(
                        self.generate_deps_header[cf_info['key']])
                    cf_info['b2_requires'] = ['boost_%s' %
                                              (x) for x in list(requires_user)]
                if args.generate_deps_source:
                    requires_source.update(
                        self.generate_deps_source[cf_info['key']])
                    requires_source.difference_update(requires_user)
                    cf_info['source_only_deps'] = list(requires_source)
            if cf_info['is_cycle_group']:
                requires_user.update(
                    self.cycle_group[cf_info['key']]['requires'])
                cf_info['b2_requires'] = ['boost_%s' %
                                          (x) for x in list(requires_user)]
                cf_info['lib_short_names'] = self.cycle_group[cf_info['key']
                                                              ]['lib_short_names']
                cf_info['header_only_libs'] = list(
                    set(cf_info['lib_short_names'])-self.generate_deps_build)

            if args.trace:
                print('REQUIRES_USER:')
                pprint.pprint(requires_user)
                print('REQUIRES_SOURCE:')
                pprint.pprint(requires_source)

            def add_array_var(info_var):
                if len(cf_info[info_var]) == 1:
                    result_py.extend(self.__lines__([]
                                                    + ['''    %s = ["%s"]''' %
                                                        (info_var, cf_info[info_var][0])]
                                                    ))
                elif len(cf_info[info_var]) > 1:
                    sorted_var = sorted(cf_info[info_var])
                    result_py.extend(self.__lines__([]
                                                    + ['''    %s = [''' %
                                                        (info_var)]
                                                    + ['''        "%s",''' %
                                                        (x) for x in sorted_var[:-1]]
                                                    + ['''        "%s"''' %
                                                        (sorted_var[-1])]
                                                    + ['''    ]''']
                                                    ))

            def format_value(val):
                if type(val) == type(""):
                    return '"%s"' % (val)
                else:
                    return val

            def add_dict_var(info_var):
                sorted_keys = sorted(cf_info[info_var].keys())
                if len(sorted_keys) == 1:
                    result_py.append('''    %s = {"%s": %s}\n''' % (
                        info_var, sorted_keys[0], format_value(cf_info[info_var][sorted_keys[0]])))
                else:
                    result_py.append('''    %s = {\n''' % (info_var))
                    for k in sorted_keys[:-1]:
                        result_py.append('''        "%s": %s,\n''' %
                                         (k, format_value(cf_info[info_var][k])))
                    result_py.append('''        "%s": %s\n''' % (
                        sorted_keys[-1], format_value(cf_info[info_var][sorted_keys[-1]])))
                    result_py.append('''    }\n''')

            source_py = self.__lines__(cf_py)
            while len(cf_py) > 0:
                l = cf_py.pop(0)
                # Forward through header to class def.
                if re.match(r'class\sBoost', l):
                    # The class definition..
                    result_py.extend(self.__lines__([
                        l.rstrip()
                    ]))
                    # The class variables..
                    cycle_group_level = ""
                    if cf_info['is_cycle_group']:
                        cycle_group_level = ''' # Level %s''' % (
                            self.cycle_group[cf_info['key']]['index'])
                    result_py.extend(self.__lines__([
                        '    name = "%s"' % (
                            cf_info['name'])+cycle_group_level,
                        '    url = "%s"' % (cf_info['url']),
                    ]))
                    add_array_var('lib_short_names')
                    add_array_var('header_only_libs')
                    if cf_info['is_in_cycle_group']:
                        result_py.extend(self.__lines__([
                            '    cycle_group = "%s"' % (cf_info['cycle_group'])
                        ]))
                    if cf_info['options'] and cf_info['default_options']:
                        add_dict_var('options')
                        result_py.extend(self.__lines__([
                            '    default_options = "%s"' % (
                                '", "'.join(sorted(cf_info['default_options']))),
                        ]))
                    if cf_info['b2_options']:
                        add_dict_var('b2_options')
                    add_array_var('b2_defines')
                    if not cf_info['is_in_cycle_group']:
                        add_array_var('source_only_deps')
                    add_array_var('b2_requires')
                    add_array_var('b2_build_requires')
                    # Forward past vars and echo functions..
                    while len(cf_py) > 0:
                        l = cf_py.pop(0)
                        prop_or_def = self.__re_search__(
                            r'\s+(@[a-z]|def )', l)
                        if prop_or_def:
                            # Eat any trailing empty lines..
                            while len(cf_py) > 0:
                                if cf_py[-1].rstrip() != '':
                                    break
                                cf_py.pop()
                            # Copy the rest out..
                            result_py.extend(self.__lines__(["", l]+cf_py))
                            cf_py = []
                            break
                    break
                else:
                    # Headers lines..
                    if l and args.generate_version:
                        # Version replacements.
                        l = re.sub(r'1[.][0-9][0-9][.][0-9]',
                                   args.generate_version, l)
                    result_py.append(l.rstrip() + "\n")

            if args.debug:
                # if args.trace:
                #     pprint.pprint(result_py)
                # print("".join(result_py))
                print("".join(difflib.unified_diff(source_py, result_py,
                                                   fromfile=cf_info['key']+"/before", tofile=cf_info['key']+"/after")))
            else:
                with open(os.path.join(package_dir, 'conanfile.py'), 'w') as f:
                    conanfile_py = f.write("".join(result_py))

    def travis_config(self, args):
        if os.path.exists(os.path.join(os.getcwd(), '.travis.yml')):
            self.__write_file__(os.path.join(os.path.join(os.getcwd(), '.travis.yml')), '''\
linux: &linux
   os: linux
   sudo: required
   language: python
   python: "3.6"
   services:
     - docker
osx: &osx
   os: osx
   language: generic
matrix:
   include:

      - <<: *linux
        env: CONAN_GCC_VERSIONS=4.9 CONAN_DOCKER_IMAGE=lasote/conangcc49
      - <<: *linux
        env: CONAN_GCC_VERSIONS=5 CONAN_DOCKER_IMAGE=lasote/conangcc5
      - <<: *linux
        env: CONAN_GCC_VERSIONS=6 CONAN_DOCKER_IMAGE=lasote/conangcc6
      - <<: *linux
        env: CONAN_GCC_VERSIONS=7 CONAN_DOCKER_IMAGE=lasote/conangcc7
      - <<: *linux
        env: CONAN_CLANG_VERSIONS=3.9 CONAN_DOCKER_IMAGE=lasote/conanclang39
      - <<: *linux
        env: CONAN_CLANG_VERSIONS=4.0 CONAN_DOCKER_IMAGE=lasote/conanclang40
      - <<: *osx
        osx_image: xcode7.3
        env: CONAN_APPLE_CLANG_VERSIONS=7.3
      - <<: *osx
        osx_image: xcode8.3
        env: CONAN_APPLE_CLANG_VERSIONS=8.1
      - <<: *osx
        osx_image: xcode9
        env: CONAN_APPLE_CLANG_VERSIONS=9.0

install:
  - chmod +x .travis/install.sh
  - ./.travis/install.sh

script:
  - chmod +x .travis/run.sh
  - ./.travis/run.sh
''', args)
            self.__write_file__(os.path.join(os.getcwd(), '.travis', 'install.sh'), '''\
#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    brew update || brew update
    brew outdated pyenv || brew upgrade pyenv
    brew install pyenv-virtualenv
    brew install cmake || true

    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi

    pyenv install 2.7.10
    pyenv virtualenv 2.7.10 conan
    pyenv rehash
    pyenv activate conan
fi

pip install conan --upgrade
pip install conan_package_tools

conan user
''', args, create_if_absent=True)
            self.__write_file__(os.path.join(os.getcwd(), '.travis', 'run.sh'), '''\
#!/bin/bash

set -e
set -x

if [[ "$(uname -s)" == 'Darwin' ]]; then
    if which pyenv > /dev/null; then
        eval "$(pyenv init -)"
    fi
    pyenv activate conan
fi

python build.py
''', args, create_if_absent=True)

    def git_publish(self, args):
        self.__call__(['git', 'commit', '--all', '-m',
                       args.git_publish_comment], args)
        self.__check_call__(['git', 'push'], args)

    def git_commit(self, args):
        self.__call__(['git', 'commit', '--all', '-m',
                       args.git_commit_comment], args)

    def git_checkout(self, args):
        self.__call__(['git', 'checkout', args.git_checkout_branch], args)

    def git_merge(self, args):
        self.__call__(['git', 'merge', args.git_merge_commit], args)

    def git_diff(self, args):
        self.__call__(
            ['git', 'diff', 'HEAD', args.git_diff_commit, '--'], args)

    def export_pre(self, args):
        self.__call__(['conan', 'remove', '--force', 'boost_*'], args)
        self.__call__(['conan', 'remote', 'add', 'bincrafters',
                       'https://api.bintray.com/conan/bincrafters/public-conan'], args)

    def export(self, args):
        self.__call__(['conan', 'export', '.', conan_scope], args)

    def gen_levels_pre(self, args):
        self.gen_levels_info = {}

    def gen_levels(self, args):
        cf_info = self.__info__(args)
        output = check_output([
            'conan', 'info',
            '%s/%s@%s' % (cf_info['name'], args.version, conan_scope),
            '--build-order=ALL',
        ]
            + args.options)
        deps = set(re.findall(r'boost[-_]([^/]+)', output))
        deps.remove(cf_info['key'])
        if not cf_info['key'] in ['base', 'build', 'generator']:
            deps.add('base')
        if args.debug:
            print("GEN_LEVELS_INFO[%s]:" % (cf_info['key']))
            pprint.pprint(deps)
        self.gen_levels_info[cf_info['key']] = deps

    def gen_levels_post(self, args):
        if args.debug:
            print("GEN_LEVELS_INFO:")
            pprint.pprint(self.gen_levels_info)
        levels = []
        while 0 < len(self.gen_levels_info) and len(levels) < 200:
            if args.trace:
                print("GEN_LEVELS_POST.. level #%s:" % (len(levels)))
            level = set()
            for (k, v) in self.gen_levels_info.iteritems():
                if len(v) == 0:
                    level.add(k)
            # if len(level) == 0:
            #    break
            for l in level:
                del self.gen_levels_info[l]
                for (k, v) in self.gen_levels_info.iteritems():
                    v.discard(l)
            if args.trace:
                pprint.pprint(level)
            levels.append(level)
        pprint.pprint(levels)

    gen_test_files = ['CMakeLists.txt', 'conanfile.py']
    gen_test_groups = {
    }

    def gen_test_pre(self, args):
        if args.generate_deps_header:
            self.generate_deps_header = self.__read_deps__(
                args.generate_deps_header)
        self.gen_test_file_format = {}
        for gen_test_file in self.gen_test_files:
            gen_test_file_path = os.path.join(
                os.getcwd(), '.template', 'test_package', gen_test_file)
            if os.path.exists(gen_test_file_path):
                with open(gen_test_file_path) as f:
                    self.gen_test_file_format[gen_test_file] = f.read()

    def gen_test(self, args):
        if not os.path.exists(os.path.join(os.getcwd(), 'test_package')):
            return
        if not os.path.isfile(os.path.join(os.getcwd(), 'conanfile.py')):
            return
        if not self.generate_deps_header:
            return
        cf_info = self.__info__(args)
        boost_lib = cf_info['name'].replace('boost_', '')
        if not boost_lib in self.generate_deps_header:
            return
        gen_test_deps = set(self.generate_deps_header[boost_lib] + [boost_lib])
        if cf_info['level_group']:
            gen_test_deps -= set(self.gen_test_groups[cf_info['level_group']])
            # As soon as we override the "requires" we need to add ourselves
            # as conan wont do that for us.
            gen_test_deps.add(boost_lib)
        format_fields = {'%': '%'}
        format_fields['link_libraries'] = "\n  " + "\n  ".join([
            'CONAN_PKG::boost_' + x for x in sorted(gen_test_deps)])
        format_fields['boost_deps'] = sorted(gen_test_deps)
        if boost_lib in ['mpi']:
            format_fields['require_mpi'] = True
        else:
            format_fields['require_mpi'] = False
        for gen_test_file in self.gen_test_files:
            gen_test_file_path = os.path.join(
                os.getcwd(), 'test_package', gen_test_file)
            if gen_test_file in self.gen_test_file_format:
                gen_test_file_content = self.gen_test_file_format[gen_test_file] % format_fields
                if args.debug:
                    print(gen_test_file_path + ":")
                    print(gen_test_file_content)
                else:
                    with open(gen_test_file_path, "w") as f:
                        f.write(gen_test_file_content)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(prefix_chars='+')
    # common args
    parser.add_argument('++lib', action='append')
    parser.add_argument('++debug', action='store_true')
    parser.add_argument('++trace', action='store_true')
    parser.add_argument('++command', action='append')
    parser.add_argument('++extra', action='append')
    parser.add_argument('++version')
    parser.add_argument('++no-ignore-libs', action='store_true')
    parser.add_argument('options', nargs='*', default=[])
    parser.add_argument("++generate-deps-header", default="deps-header.txt")
    parser.add_argument("++generate-deps-source", default="deps-source.txt")
    parser.add_argument("++generate-deps-levels", default="deps-levels.txt")
    parser.add_argument("++generate-deps-build", default="deps-build.txt")
    # command: generate
    # parser.add_argument("++generate-mode", choices=['local', 'required'], default='local')
    parser.add_argument("++generate-version")
    # command git_publish
    parser.add_argument("++git-publish-comment")
    # command git_commit
    parser.add_argument("++git-commit-comment")
    # command git_checkout
    parser.add_argument("++git-checkout-branch")
    # command git_merge
    parser.add_argument("++git-merge-commit")
    # command git_diff
    parser.add_argument("++git-diff-commit")
    #

    args = parser.parse_args()
    if not args.command:
        args.command = ['info']

    #
    core_libs = set([
        'base', 'build', 'generator'
    ])

    package_dirs = glob.glob(os.path.join(os.getcwd(), '*', 'conanfile.py'))
    package_dirs = filter(None, map(
        lambda d: os.path.dirname(d),
        package_dirs))
    if not args.command[0] in ('gen_levels'):
        package_dirs = filter(None, map(
            lambda d: d if os.path.basename(d) not in core_libs else "",
            package_dirs))
    if args.lib:
        package_dirs = filter(None, map(
            lambda d: d if os.path.basename(d) in args.lib else "",
            package_dirs))
    package_dirs = sorted(list(package_dirs))
    if args.extra:
        for extra in args.extra:
            package_dirs.insert(0, os.path.join(os.getcwd(), extra))
    if args.command[0] in ('export'):
        package_dirs = [os.path.join(os.getcwd(), x)
                        for x in core_libs]+package_dirs

    cc = Commands(args)
    for command in args.command:
        getattr(cc, command + '_pre', lambda a: None)(args)

    failures = []
    for package_dir in package_dirs:
        if os.path.basename(package_dir) in cc.ignore_libs:
            continue
        if package_dir:
            print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> " + package_dir)
            try:
                os.chdir(package_dir)
                for command in args.command:
                    getattr(cc, command, lambda a: None)(args)
                print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< " +
                      package_dir + " << SUCCESS")
            except Exception as e:
                failures.append(package_dir)
                print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< " +
                      package_dir + " << FAILED")
                import traceback
                traceback.print_exc()
                print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    for failure in failures:
        print("FAILED: " + failure)

    for command in args.command:
        getattr(cc, command + '_post', lambda a: None)(args)

    exit(len(failures))
