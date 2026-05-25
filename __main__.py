#!/usr/bin/env python
import os
import shutil
import subprocess
import sys
import typing
from typing import Type, Any, Never
import msgspec
from pathlib import Path
import argparse


def assert_unreachable(arg: Never) -> Never:
    raise AssertionError(f"Expected code to be unreachable, but got {arg}")


def dec_hook(type: Type, obj: Any) -> Any:
    if type == Path:
        return Path(obj)
    raise NotImplementedError("Unknown type during decryption " + str(type))


class GitSource(msgspec.Struct, tag="git"):
    upstream: str
    name: str


class GitHubNamespaceSource(msgspec.Struct, tag="github"):
    namespace: str
    prefix: typing.Optional[str] = None


class Config(msgspec.Struct):
    root: Path
    sources: list[typing.Union[GitSource, GitHubNamespaceSource]]
    github_token: typing.Optional[str] = None


dec = msgspec.json.Decoder(Config, dec_hook=dec_hook)


def validate(args: argparse.Namespace, print_ok=True):
    errors = []
    config = args.config
    for s in config.sources:
        if isinstance(s, GitHubNamespaceSource):
            if not s.namespace:
                errors.append("a github source is missing a namespace")
            if not config.github_token:
                errors.append(
                    f"for github source {s.namespace} to be fetched, there needs to be a github_token at the top level"
                )
        elif isinstance(s, GitSource):
            if not s.upstream:
                errors.append("a git source is missing an upstream")
            if not s.name:
                errors.append("a git source is missing a name")
        else:
            assert_unreachable(s)
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    elif print_ok:
        print("ok")


def run_raw(args: list[str], error_as_none: bool = False):
    print(f"[debug] running command {args}")
    process = subprocess.run(
        args,
        capture_output=True,
        env={
            "LC_ALL": "en_US.UTF-8",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "PATH": os.environ["PATH"],
        },
    )
    if process.returncode != 0:
        if error_as_none:
            return None
        process.check_returncode()
    stdout = str(process.stdout, encoding="utf-8").strip()
    print(f"[debug] stdout: {stdout}")
    return stdout


def run_git(folder: Path, args: list[str], error_as_none: bool = False):
    return run_raw(["git", "-C", str(folder), *args], error_as_none=error_as_none)


def mirror_repo(upstream: str, folder: Path):
    print(f"mirroring {upstream} into {folder}")
    if (
        run_git(folder, ["remote", "get-url", "origin"], error_as_none=True) != upstream
        or run_git(
            folder, ["config", "--get", "remote.origin.mirror"], error_as_none=True
        )
        != "true"
    ):
        try:
            print("invalid mirror configuration set-up; deleting folder")
            shutil.rmtree(folder)
            print("deletion completed")
        except FileNotFoundError:
            print("folder not found.")

        run_raw(["git", "clone", "--mirror", upstream, folder])
    else:
        run_git(folder, ["fetch", "-p", "origin"])


def pull(args: argparse.Namespace):
    validate(args, print_ok=False)
    config = args.config
    root = config.root
    for s in config.sources:
        if isinstance(s, GitHubNamespaceSource):
            print("todo: skipping gh namespace source")
        elif isinstance(s, GitSource):
            mirror_repo(s.upstream, root / s.name)
        else:
            assert_unreachable(s)


def main():
    parser = argparse.ArgumentParser(
        prog="git-mirror-tool",
        description="Mirror a set of git repositories from various sources to a local folder",
    )
    parser.add_argument("--config", type=lambda s: dec.decode(Path(s).read_text()))
    subparsers = parser.add_subparsers()
    subparsers.add_parser("validate").set_defaults(func=validate)
    subparsers.add_parser("pull").set_defaults(func=pull)
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
