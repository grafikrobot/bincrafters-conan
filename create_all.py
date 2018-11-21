import os.path
import glob
from subprocess import check_call, call
import pprint
import argparse
from time import sleep

if __name__ == "__main__":
    conan_scope = "bincrafters/testing"

    parser = argparse.ArgumentParser(prefix_chars="+")
    parser.add_argument("++lib", action="append")
    parser.add_argument("++clean-each", action="store_true")
    parser.add_argument("options", nargs="*", default=[])
    args = parser.parse_args()

    package_dirs_to_export = glob.glob(
        os.path.join(os.getcwd(), "*", "conanfile.py")
    )
    package_dirs_to_export = filter(
        None, map(lambda d: os.path.dirname(d), package_dirs_to_export)
    )
    package_dirs_to_export = filter(
        None,
        map(
            lambda d: d
            if os.path.basename(d)
            not in (
                "base",
                "generator",
                "package_tools",
            )
            else "",
            package_dirs_to_export,
        ),
    )
    package_dirs_to_export = list(package_dirs_to_export)
    package_dirs_to_export.insert(0, os.path.join(os.getcwd(), "base"))
    package_dirs_to_export.insert(0, os.path.join(os.getcwd(), "generator"))
    package_dirs_to_export.insert(
        0, os.path.join(os.getcwd(), "package_tools")
    )

    package_dirs_to_build = glob.glob(
        os.path.join(os.getcwd(), "*", "conanfile.py")
    )
    package_dirs_to_build = filter(
        None, map(lambda d: os.path.dirname(d), package_dirs_to_build)
    )
    package_dirs_to_build = filter(
        None,
        map(
            lambda d: d
            if os.path.basename(d)
            not in (
                "base",
                "generator",
                "package_tools",
                "mpi",
                "graph_parallel",
            )
            else "",
            package_dirs_to_build,
        ),
    )
    if args.lib:
        package_dirs_to_build = filter(
            None,
            map(
                lambda d: d if os.path.basename(d) in args.lib else "",
                package_dirs_to_build,
            ),
        )
    package_dirs_to_build = sorted(list(package_dirs_to_build))
    if not args.clean_each:
        package_dirs_to_build.insert(0, os.path.join(os.getcwd(), "base"))
        package_dirs_to_build.insert(0, os.path.join(os.getcwd(), "generator"))
        package_dirs_to_build.insert(
            0, os.path.join(os.getcwd(), "package_tools")
        )

    call(["conan", "remove", "--force", "boost_*"])
    call(
        [
            "conan",
            "remote",
            "add",
            "bincrafters",
            "https://api.bintray.com/conan/bincrafters/public-conan",
        ]
    )
    if not args.clean_each:
        for package_dir in package_dirs_to_export:
            if package_dir:
                print(">>>>>>>>>> " + package_dir)
                os.chdir(package_dir)
                command = ["conan", "export", ".", conan_scope]
                check_call(command)
    failures = []
    for package_dir in package_dirs_to_build:
        if package_dir:
            print(">>>>>>>>>> " + package_dir)
            try:
                if args.clean_each:
                    call(["conan", "remove", "--force", "boost_*"])
                    for export_dir in package_dirs_to_export:
                        if export_dir:
                            print("----->>>>> " + export_dir)
                            os.chdir(export_dir)
                            check_call(["conan", "export", ".", conan_scope])
                os.chdir(package_dir)
                check_call(
                    ["conan", "create", ".", conan_scope, "--build=missing"]
                    + args.options
                )
                print(">>>>>>>>>> " + package_dir + " << SUCCESS")
            except Exception as e:
                failures.append(package_dir)
                print(">>>>>>>>>> " + package_dir + " << FAILED")
            sleep(5)
    for failure in failures:
        print("FAILED: " + failure)
    exit(len(failures))
