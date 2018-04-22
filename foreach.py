# Copyright Rene Rivera 2017-2018

import os.path
import glob
from subprocess import check_call, call, check_output
import pprint
import argparse
from time import sleep
import re
from types import BooleanType
from functools import reduce

conan_scope = "bincrafters/testing"
args = None


class Commands():
    
    def __check_call__(self, command, args):
        if args.debug:
            print('EXEC: "' + '" "'.join(command) + '"')
        else:
            check_call(command)
    
    def __call__(self, command, args):
        if args.debug:
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
        else:
            re = '''%s = ['"]([^'"]+)''' % (name)
            return self.__re_search__(re, cf, default=default)

    def __info__(self, args):
        result = {}
        if os.path.isfile(os.path.join(os.getcwd(), 'conanfile.py')):
            with open(os.path.join(os.getcwd(), 'conanfile.py')) as f:
                cf = f.read()
            result['name'] = self.__cf_get__('name', cf, default="")
            result['key'] = result['name'].replace('boost_', '')
            result['version'] = self.__cf_get__('version', cf, default="")
            result['version_flat'] = result['version'].replace('.', '_')
            result['is_header_only'] = self.__cf_get__('is_header_only', cf, default=True)
            if type(result['is_header_only']) == type({}):
                result['is_header_only'] = reduce(lambda x, y: x and y, result['is_header_only'].viewvalues())
            result['is_cycle_group'] = self.__cf_get__('is_cycle_group', cf, default=False)
            result['level_group'] = self.__cf_get__('level_group', cf, default=None)
            result['is_in_cycle_group'] = True if result['level_group'] else False
        return result
    
    def __write_file__(self, path, content, args, create_if_absent=False):
        if os.path.exists(path) or create_if_absent:
            if args.debug:
                print("FILE: " + os.path.basename(path).upper() + "\n" + content)
            else:
                with open(os.path.join(path), 'w') as f:
                    f.write(content)

    def info(self, args):
        print('DIR: ' + os.getcwd())
        cf = self.__info__(args)
        print('NAME: ' + cf['name'])
        print('VERSION: ' + cf['version'])
        print('IS_HEADER_ONLY: ' + str(cf['is_header_only']))
        print('IS_CYCLE_GROUP: ' + str(cf['is_cycle_group']))
        print('IS_IN_CYCLE_GROUP: ' + str(cf['is_in_cycle_group']))
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
                '--all' , '-r', 'bincrafters'
                ], args)
        elif cf['is_in_cycle_group']:
            self.__check_call__([
                'conan', 'upload',
                cf['name'] + '/' + cf['version'] + '@' + conan_scope,
                '-r', 'bincrafters'
                ], args)
    
    def __read_deps__(self, deps):
        deps_info = {}
        with open(deps) as f:
            deps_txt = f.readlines()
        for l in deps_txt:
            i = l.split('->')
            lib = i[0].strip().replace('~', '_')
            lib_deps = [x.replace('~', '_') for x in i[1].split()]
            deps_info[lib] = lib_deps
        return deps_info
    
    def generate_pre(self, args):
        if args.generate_deps_header:
            self.generate_deps_header = self.__read_deps__(args.generate_deps_header)
        if args.generate_deps_source:
            self.generate_deps_source = self.__read_deps__(args.generate_deps_source)
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
                            'lib_short_names': set(),
                            'requires': set() }
                        l = None
                if l == '':
                    l = None
                    level_i = None
                if l and level_i:
                    i = l.split('->')
                    lib = i[0].strip().replace('~', '_')
                    lib_deps = [x.replace('~', '_') for x in i[1].split()]
                    for lib_dep in lib_deps:
                        lib_level = int(self.__re_search__(r'[(]([0-9]+)[)]', lib_dep))
                        if lib_level == level_i:
                            self.levelgroups[level_i]['lib_short_names'].add(self.__re_search__(r'([^(]+)', lib_dep))
            for (i, lg) in self.levelgroups.iteritems():
                for l in lg['lib_short_names']:
                    lg['requires'] |= set(self.generate_deps_header[l])
                lg['requires'] -= lg['lib_short_names']
            pprint.pprint(self.levelgroups)
    
    def generate(self, args):
        if os.path.isfile(os.path.join(os.getcwd(), 'conanfile.py')):
            cf_info = self.__info__(args)
            if args.generate_version:
                cf_info['version'] = args.generate_version
                cf_info['version_flat'] = args.generate_version.replace('.', '_')
            with open(os.path.join(os.getcwd(), 'conanfile.py')) as f:
                cf_py = f.readlines()
            vars = {}
            result_py = []
            parse_state = 'pre'
            requires_user = set()
            requires_source = set()
            requires_user_current = set()
            requires_source_current = set()
            if not cf_info['is_cycle_group'] and args.generate_deps_header:
                requires_user.update(self.generate_deps_header[cf_info['key']])
            if not cf_info['is_cycle_group'] and args.generate_deps_source:
                requires_source.update(self.generate_deps_source[cf_info['key']])
                requires_source.difference_update(requires_user)
            # print('REQUIRES_USER:')
            # pprint.pprint(requires_user)
            # print('REQUIRES_SOURCE:')
            # pprint.pprint(requires_source)
            for l in cf_py:
                if parse_state == 'pre':
                    if l and not cf_info['is_cycle_group'] and re.match(r'\s+requires\s+=', l):
                        parse_state = 'requires'
                        l = None
                    if l and not cf_info['is_cycle_group'] and re.match(r'\s+source_only_deps\s+=', l):
                        parse_state = 'source_only_deps'
                    if l and '# BEGIN' in l:
                        parse_state = 'template'
                        l = None
                    if l and args.generate_version:
                        l = re.sub(r'1[.][0-9][0-9][.][0-9]', args.generate_version, l)
                    if l and 'url = ' in l:
                        l = None
                    if parse_state == 'pre' and l:
                        result_py.append(l.rstrip() + "\n")

                if parse_state == 'requires':
                    if l and l.rstrip() == '':
                        parse_state = 'pre'
                        l = None
                        requires_user_keep = set([x for x in requires_user_current if '@' in x])
                        requires_user_current -= requires_user_keep

                        if cf_info['level_group']:
                            requires_user_level = set([
                                self.__re_search__(r'boost_(.*)', cf_info['level_group']),
                                'package_tools'])
                            requires_user_todo = requires_user - requires_user_level
                            requires_user = requires_user_level
                        else:
                            requires_user.add('package_tools')
                            requires_user_todo = requires_user_current - requires_user
                        # if cf_info['level_group']:
                        #    requires_user -= requires_user_current

                        requires_user_keep |= set(['boost_%s/%s@%s' % (x, cf_info['version'], conan_scope) for x in requires_user])
                        # print("REQUIRES_USER_CURRENT:")
                        # pprint.pprint(requires_user_current)
                        if len(requires_user_todo) > 0:
                            result_py.append('''\
    # TODO: %s
''' % (', '.join(sorted(requires_user_todo))))
                        result_py.append('''\
    requires = (
''')
                        result_py.append('''\
        "%s"
''' % ('''",
        "'''.join(sorted(requires_user_keep))))
                        result_py.append('''\
    )

''')
                    if l:
                        r = self.__re_search__(r'\s+["]([^"]+)', l)
                        b = self.__re_search__(r'\s+["]boost_([^/]+)', l)
                        if b:
                            requires_user_current.add(b)
                        elif r:
                            requires_user_current.add(r)

                if parse_state == 'source_only_deps':
                    if l and l.rstrip() == '':
                        parse_state = 'pre'
                        l = None
                        requires_source_todo = requires_source_current - requires_source
                        # print("REQUIRES_SOURCE_TODO:")
                        # pprint.pprint(requires_source_todo)
                        if len(requires_source_todo) > 0:
                            result_py.append('''\
    # TODO: %s
''' % (', '.join(sorted(requires_source_todo))))
                        result_py.append('''\
    source_only_deps = [
''')
                        result_py.append('''\
        "%s"
''' % ('''",
        "'''.join(sorted(requires_source))))
                        result_py.append('''\
    ]

''')
                    if l:
                        r = re.findall(r'["]([^"]+)["]', l)
                        if r:
                            requires_source_current.update(r)

                if parse_state == 'template':
                    if l and '# END' in l:
                        parse_state = 'post'
                        l = None
                        result_py.append('''\
    # BEGIN

    url = "https://github.com/bincrafters/conan-{name}"
    description = "Please visit http://www.boost.org/doc/libs/{version_flat}"
    license = "BSL-1.0"
    short_paths = True
'''.format(**cf_info))
                        if not cf_info['is_header_only']:
                            result_py.append('''\
    generators = "boost"
    settings = "os", "arch", "compiler", "build_type"
'''.format(**cf_info))
                        result_py.append('''\
    build_requires = "boost_generator/{version}@bincrafters/testing"

    def package_id(self):
        getattr(self, "package_id_additional", lambda:None)()

    def source(self):
        with tools.pythonpath(self):
            import boost_package_tools  # pylint: disable=F0401
            boost_package_tools.source(self)
        getattr(self, "source_additional", lambda:None)()

    def build(self):
        with tools.pythonpath(self):
            import boost_package_tools  # pylint: disable=F0401
            boost_package_tools.build(self)
        getattr(self, "build_additional", lambda:None)()

    def package(self):
        with tools.pythonpath(self):
            import boost_package_tools  # pylint: disable=F0401
            boost_package_tools.package(self)
        getattr(self, "package_additional", lambda:None)()

    def package_info(self):
        with tools.pythonpath(self):
            import boost_package_tools  # pylint: disable=F0401
            boost_package_tools.package_info(self)
        getattr(self, "package_info_additional", lambda:None)()

    # END
'''.format(**cf_info))

                if parse_state == 'post':
                    if l and args.generate_version:
                        l = re.sub(r'1[.][0-9][0-9][.][0-9]', args.generate_version, l)
                    if l:
                        result_py.append(l.rstrip() + "\n")

            if args.debug:
                print("".join(result_py))
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
        self.__call__(['git', 'commit', '--all', '-m', args.git_publish_comment], args)
        self.__check_call__(['git', 'push'], args)
    
    def git_commit(self, args):
        self.__call__(['git', 'commit', '--all', '-m', args.git_commit_comment], args)
    
    def git_checkout(self, args):
        self.__call__(['git', 'checkout', args.git_checkout_branch], args)
    
    def git_merge(self, args):
        self.__call__(['git', 'merge', args.git_merge_commit], args)
    
    def git_diff(self, args):
        self.__call__(['git', 'diff', 'HEAD', args.git_diff_commit, '--'], args)

    def gen_levels_pre(self, args):
        self.gen_levels_info = {}

    def gen_levels(self, args):
        output = check_output(['conan', 'info', '--package-filter=boost_*', '.'] + args.options)
        name = None
        deps = set()
        state = 'begin'
        for line in output.splitlines():
            if state == 'begin':
                name = self.__re_search__(r'^boost_([^/]+)', line)
                state = 'info'
            elif state == 'info' and 'Requires:' in line:
                state = 'requires'
            elif state == 'requires':
                if line.startswith('boost_'):
                    break
                else:
                    dep = self.__re_search__(r'boost_([^/]+)', line)
                    if dep:
                        deps.add(dep)
        self.gen_levels_info[name] = deps

    def gen_levels_post(self, args):
        levels = []
        while len(self.gen_levels_info):
            level = set()
            for (k, v) in self.gen_levels_info.iteritems():
                if len(v) == 0:
                    level.add(k)
            if len(level) == 0:
                break
            for l in level:
                del self.gen_levels_info[l]
                for (k, v) in self.gen_levels_info.iteritems():
                    v.discard(l)
            levels.append(level)
        pprint.pprint(levels)

    gen_test_files = ['CMakeLists.txt', 'conanfile.py']
    get_test_groups = {
        'boost_level8group': ["lexical_cast", "math"],
        'boost_level11group': ["date_time", "pool", "serialization", "spirit", "thread"],
        'boost_level14group': ["bimap", "disjoint_sets", "graph", "graph_parallel", "mpi", "property_map"]
        }

    def gen_test_pre(self, args):
        if args.generate_deps_header:
            self.generate_deps_header = self.__read_deps__(args.generate_deps_header)
        self.gen_test_file_format = {}
        for gen_test_file in self.gen_test_files:
            gen_test_file_path = os.path.join(os.getcwd(), '.template', 'test_package', gen_test_file)
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
            gen_test_deps -= set(self.get_test_groups[cf_info['level_group']])
        format_fields = {'%': '%'}
        format_fields['link_libraries'] = "\n  " + "\n  ".join([
            'CONAN_PKG::boost_' + x for x in sorted(gen_test_deps)])
        format_fields['boost_deps'] = sorted(gen_test_deps)
        for gen_test_file in self.gen_test_files:
            gen_test_file_path = os.path.join(os.getcwd(), 'test_package', gen_test_file)
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
    parser.add_argument('++command', action='append')
    parser.add_argument('++extra', action='append')
    parser.add_argument('options', nargs='*', default=[])
    parser.add_argument("++generate-deps-header", default="deps-header.txt")
    parser.add_argument("++generate-deps-source", default="deps-source.txt")
    parser.add_argument("++generate-deps-levels", default="deps-levels.txt")
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
    
    package_dirs = glob.glob(os.path.join(os.getcwd(), '*', 'conanfile.py'))
    package_dirs = filter(None, map(
        lambda d: os.path.dirname(d),
        package_dirs))
    if not args.command[0] in ('gen_levels'):
        package_dirs = filter(None, map(
            lambda d: d if os.path.basename(d) not in ('generator', 'build', 'package_tools') else "",
            package_dirs))
    if args.lib:
        package_dirs = filter(None, map(
            lambda d: d if os.path.basename(d) in args.lib else "",
            package_dirs))
    package_dirs = sorted(list(package_dirs))
    if args.extra:
        for extra in args.extra:
            package_dirs.insert(0, os.path.join(os.getcwd(), extra))
    
    cc = Commands()
    for command in args.command:
        getattr(cc, command + '_pre', lambda a: None)(args)
    
    failures = []
    for package_dir in package_dirs:
        if package_dir:
            print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> " + package_dir)
            try:
                os.chdir(package_dir)
                for command in args.command:
                    getattr(cc, command, lambda a: None)(args)
                print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< " + package_dir + " << SUCCESS")
            except Exception as e:
                failures.append(package_dir)
                print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< " + package_dir + " << FAILED")
                import traceback
                traceback.print_exc()
                print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    for failure in failures:
        print("FAILED: " + failure)
    
    for command in args.command:
        getattr(cc, command + '_post', lambda a: None)(args)

    exit(len(failures))
