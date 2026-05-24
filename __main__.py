#!/usr/bin/env python
import sys
import typing
from typing import Union, Type, Any
import msgspec
from pathlib import Path
import argparse


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
    for source in config.sources:
        if isinstance(s, GithubNamespaceSource):
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

    if errors:
        print("\n".join(errors))
        sys.exit(1)
    elif print_ok:
        print("ok")


def update(args: argparse.Namespace):
    validate(args, print_ok=False)
    errors = []
    config = args.config
    root = config.root
    for source in config.sources:



def main():
    parser = argparse.ArgumentParser(
        prog="git-mirror-tool",
        description="Mirror a set of git repositories from various sources to a local folder",
    )
    parser.add_argument("--config", type=lambda s: dec.decode(Path(s).read_text()))
    subparsers = parser.add_subparsers()
    subparsers.add_parser("validate").set_defaults(func=validate)
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
