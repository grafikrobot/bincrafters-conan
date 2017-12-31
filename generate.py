import os
import os.path
import glob
from subprocess import check_call, call
import pprint
import argparse
from time import sleep
from pprint import pprint
import shutil
import re

# import conans.client.installer
# import conans.tools.pythonpath

if __name__ == "__main__":
    conan_scope = "bincrafters/testing"
    
    parser = argparse.ArgumentParser(prefix_chars='+')
    parser.add_argument('++lib')
    parser.add_argument("++debug", action='store_true')
    parser.add_argument("++require-generator", action='store_true', default=False)
    # parser.add_argument("++local", action="store_true", default=False)
    parser.add_argument("++version")
    parser.add_argument('options', nargs='*', default=[])
    args = parser.parse_args()
    # args.require_generator = not args.no_require_generator
    args.local = True
    
    package_dirs_to_generate = glob.glob(os.path.join(os.getcwd(), '*', 'conanfile.py'))
    package_dirs_to_generate = filter(None, map(
        lambda d: os.path.dirname(d),
        package_dirs_to_generate))
    package_dirs_to_generate = filter(None, map(
        lambda d: d if os.path.basename(d) not in ('generator', 'build') else "",
        package_dirs_to_generate))
    if args.lib:
        package_dirs_to_generate = filter(None, map(
            lambda d: d if os.path.basename(d) == args.lib else "",
            package_dirs_to_generate))
    package_dirs_to_generate = list(package_dirs_to_generate)
    
    for package_dir in package_dirs_to_generate:
        if package_dir:
            print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> " + package_dir)
            if not args.debug:
                if args.local:
                    shutil.copy(os.path.join('generator', 'boostgenerator.py'), os.path.join(package_dir, 'boostgenerator.py'))
                elif os.path.isfile(os.path.join(package_dir, 'boostgenerator.py')):
                    os.remove(os.path.join(package_dir, 'boostgenerator.py'))
            with open(os.path.join(package_dir, 'conanfile.py')) as f:
                conanfile_py = f.readlines()
            vars = {}
            result_py = []
            found_begin = False
            found_requires = False
            for l in conanfile_py:
                if args.version:
                    l = re.sub(r'1[.][0-9][0-9][.][0-9]', args.version, l)
                if found_begin:
                    if '# END' in l:
                        found_begin = False
                    continue
                else:
                    if '# BEGIN' in l:
                        found_begin = True
                        continue
                    elif l == 'from conans import ConanFile, tools\n':
                        result_py.append('from conans import ConanFile\n')
                    else:
                        if found_requires:
                            found_requires = False
                            if not args.require_generator and "Boost.Generator" in l:
                                continue
                            elif args.require_generator and not "Boost.Generator" in l:
                                result_py.append('        "Boost.Generator/{version}@bincrafters/testing", \\\n'.format(**vars))
                        w = l.split()
                        if len(w) == 0 or w[0] not in ('url', 'description', 'license', 'settings'):
                            result_py.append(l)
                            if len(w) >= 3:
                                if w[0] == 'name':
                                    name = w[2].split('"')[1].split('.')[1]
                                    vars['name'] = name
                                    vars['name_flat'] = name.lower().replace('.', '_')
                                elif w[0] == 'version':
                                    version = w[2].split('"')[1]
                                    vars['version'] = version
                                    vars['version_flat'] = version.replace('.', '_')
                                elif w[0] == 'is_header_only':
                                    is_header_only = w[2] == "True"
                                    vars['is_header_only'] = is_header_only
                                elif w[0] == 'is_in_cycle_group':
                                    is_in_cycle_group = w[2] == "True"
                                    vars['is_in_cycle_group'] = is_in_cycle_group
                                elif w[0] == 'is_cycle_group':
                                    is_cycle_group = w[2] == "True"
                                    vars['is_cycle_group'] = is_cycle_group
                                elif w[0] == 'requires':
                                    found_requires = True
            result_py.append('''    # BEGIN
''')
            result_py.append('''
    url = "https://github.com/bincrafters/conan-boost-{name_flat}"
    description = "Please visit http://www.boost.org/doc/libs/{version_flat}"
    license = "www.boost.org/users/license.html"
    build_requires = "Boost.Generator/{version}@bincrafters/testing"
    short_paths = True
'''.format(**vars))
            if not vars['is_header_only']:
                result_py.append('''\
    generators = "boost"
    settings = "os", "arch", "compiler", "build_type"
''')
            if args.local:
                result_py.append('''\
    exports = "boostgenerator.py"
''')
            result_py.append('''
    def package_id(self):
''')
            if vars['is_header_only']:
                result_py.append('''\
        self.info.header_only()
''')
            result_py.append('''\
        getattr(self, "package_id_after", lambda:None)()
''')
            result_py.append('''\
    def source(self):
        self.call_patch("source")
    def build(self):
        self.call_patch("build")
    def package(self):
        self.call_patch("package")
    def package_info(self):
        self.call_patch("package_info")
    def call_patch(self, method, *args):
        if not hasattr(self, '__boost_conan_file__'):
            try:
                from conans import tools
                with tools.pythonpath(self):
                    import boostgenerator  # pylint: disable=F0401
                    boostgenerator.BoostConanFile(self)
            except Exception as e:
                self.output.error("Failed to import boostgenerator for: "+str(self)+" @ "+method.upper())
                raise e
        return getattr(self, method, lambda:None)(*args)
    @property
    def env(self):
        import os.path
        result = super(self.__class__, self).env
        result['PYTHONPATH'] = [os.path.dirname(__file__)] + result.get('PYTHONPATH',[])
        return result
    @property
    def build_policy_missing(self):
        return (getattr(self, 'is_in_cycle_group', False) and not getattr(self, 'is_header_only', True)) or super(self.__class__, self).build_policy_missing
''')
            result_py.append('''
    # END
''')
            if args.debug:
                print("".join(result_py))
            else:
                with open(os.path.join(package_dir, 'conanfile.py'), 'w') as f:
                    conanfile_py = f.write("".join(result_py))

        if os.path.isfile(os.path.join(os.path.join(package_dir, '.travis.yml'))):
            with open(os.path.join(package_dir, '.travis.yml'), 'w') as f:
                f.write("".join('''
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
'''))
