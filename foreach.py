import os.path
import glob
from subprocess import check_call, call
import pprint
import argparse
from time import sleep
import re
from types import BooleanType

conan_scope = "bincrafters/testing"
args = None


class Commands():
    
    @staticmethod
    def __check_call__(command, args):
        if args.debug:
            print('EXEC: "' + '" "'.join(command) + '"')
        else:
            check_call(command)
    
    @staticmethod
    def __call__(command, args):
        if args.debug:
            print('EXEC: "' + '" "'.join(command) + '"')
        else:
            call(command)

    @staticmethod
    def __re_search__(p, s, default=None):
        s = re.search(p, s)
        return s.group(1) if s else default

    @staticmethod
    def __cf_get__(name, cf, default=False):
        if type(default) == type(True):
            re = '''{0} = (True|False)'''.format(name)
            return eval(Commands.__re_search__(re, cf, default=str(default)))
        if type(default) == type({}):
            re = '''{0} = [{]([^}]+)'''.format(name)
            return eval(Commands.__re_search__(re, cf, default=str(default)))
        else:
            re = '''{0} = ['"]([^'"]+)'''.format(name)
            return Commands.__re_search__(re, cf, default=default)

    @staticmethod
    def __info__(args):
        result = {}
        if os.path.isfile(os.path.join(os.getcwd(), 'conanfile.py')):
            with open(os.path.join(os.getcwd(), 'conanfile.py')) as f:
                cf = f.read()
            result['name'] = Commands.__cf_get__('name', cf, default="")
            result['version'] = Commands.__cf_get__('version', cf, default="")
            result['is_header_only'] = Commands.__cf_get__('is_header_only', cf, default=True)
            result['is_cycle_group'] = Commands.__cf_get__('is_cycle_group', cf, default=False)
            result['is_in_cycle_group'] = Commands.__cf_get__('is_in_cycle_group', cf, default=False)
        return result
    
    @staticmethod
    def __write_file__(path, content, args, create_if_absent=False):
        if os.path.exists(path) or create_if_absent:
            if args.debug:
                print("FILE: " + os.path.basename(path).upper() + "\n" + content)
            else:
                with open(os.path.join(path), 'w') as f:
                    f.write(content)

    @staticmethod
    def info(args):
        print('DIR: ' + os.getcwd())
        cf = Commands.__info__(args)
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
    
    @staticmethod
    def upload_source_only(args):
        cf = Commands.__info__(args)
        if cf['is_header_only']:
            Commands.__check_call__([
                'conan', 'upload',
                cf['name'] + '/' + cf['version'] + '@' + conan_scope,
                '--all' , '-r', 'bincrafters'
                ], args)
        elif cf['is_in_cycle_group']:
            Commands.__check_call__([
                'conan', 'upload',
                cf['name'] + '/' + cf['version'] + '@' + conan_scope,
                '-r', 'bincrafters'
                ], args)
    
    @staticmethod
    def generate(args):
        pass
    
    @staticmethod
    def travis_config(args):
        if os.path.exists(os.path.join(os.getcwd(),'.travis.yml')):
            Commands.__write_file__(os.path.join(os.path.join(os.getcwd(), '.travis.yml')), '''\
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
            Commands.__write_file__(os.path.join(os.getcwd(), '.travis', 'install.sh'), '''\
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
            Commands.__write_file__(os.path.join(os.getcwd(), '.travis', 'run.sh'), '''\
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
    
    @staticmethod
    def git_publish(args):
        Commands.__call__(['git', 'commit', '--all', '-m', args.git_publish_comment], args)
        Commands.__check_call__(['git', 'push'], args)


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(prefix_chars='+')
    # common args
    parser.add_argument('++lib', action='append')
    parser.add_argument('++debug', action='store_true')
    parser.add_argument('++command', action='append')
    parser.add_argument('++extra', action='append')
    parser.add_argument('options', nargs='*', default=[])
    # command: generate
    parser.add_argument("++generate-mode", choices=['local', 'required'], default='local')
    parser.add_argument("++generate-version")
    # command git_publish
    parser.add_argument("++git-publish-comment")
    
    args = parser.parse_args()
    if not args.command:
        args.command = ['info']
    
    package_dirs = glob.glob(os.path.join(os.getcwd(), '*', 'conanfile.py'))
    package_dirs = filter(None, map(
        lambda d: os.path.dirname(d),
        package_dirs))
    package_dirs = filter(None, map(
        lambda d: d if os.path.basename(d) not in ('generator', 'build') else "",
        package_dirs))
    if args.lib:
        package_dirs = filter(None, map(
            lambda d: d if os.path.basename(d) in args.lib else "",
            package_dirs))
    package_dirs = list(package_dirs)
    if args.extra:
        for extra in args.extra:
            package_dirs.insert(0, os.path.join(os.getcwd(), extra))
    
    failures = []
    for package_dir in package_dirs:
        if package_dir:
            print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> " + package_dir)
            try:
                os.chdir(package_dir)
                for command in args.command:
                    getattr(Commands, command, lambda a: None)(args)
                print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< " + package_dir + " << SUCCESS")
            except Exception as e:
                failures.append(package_dir)
                print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< " + package_dir + " << FAILED")
                import traceback
                traceback.print_exc()
                print("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
    for failure in failures:
        print("FAILED: " + failure)
    exit(len(failures))
