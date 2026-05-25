#!/usr/bin/env python
import requests
import base64
import dataclasses
import os
import enum
import shutil
import subprocess
import sys
import typing
from typing import Type, Any, Never, Optional
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


class GitHubEntityType(enum.StrEnum):
    USER = "user"
    ORGANIZATION = "organization"


class GitHubNamespaceSource(msgspec.Struct, tag="github"):
    entity: str
    entity_type: GitHubEntityType
    prefix: typing.Optional[str] = None


class Config(msgspec.Struct):
    root: Path
    sources: list[typing.Union[GitSource, GitHubNamespaceSource]]
    github_token: typing.Optional[str] = None
    github_token_file: typing.Optional[Path] = None


dec = msgspec.json.Decoder(Config, dec_hook=dec_hook)


def validate(args: argparse.Namespace, print_ok=True):
    errors = []
    config: Config = args.config
    if config.github_token and config.github_token_file:
        errors.append(
            "both github_token and github_token_file are set, but only one should be set"
        )
    for s in config.sources:
        if isinstance(s, GitHubNamespaceSource):
            if not s.entity:
                errors.append("a github source is missing a namespace")
            if not config.github_token and not config.github_token_file:
                errors.append(
                    f"for github source {s.entity} to be fetched, there needs to be a github_token at the top level"
                )
        elif isinstance(s, GitSource):
            if not s.upstream:
                errors.append("a git source is missing an upstream")
            if not s.name:
                errors.append("a git source is missing a name")
            elif not s.name.endswith(".git"):
                errors.append(" a git source should end with .git")
        else:
            assert_unreachable(s)
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    elif print_ok:
        print("ok")


def run_raw(args: list[str], error_as_none: bool = False, env: dict[str, str] = {}):
    print(f"[debug] running command {[a for a in args if 'http.extra' not in a]}")
    process = subprocess.run(
        args,
        capture_output=True,
        env={
            "LC_ALL": "en_US.UTF-8",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "PATH": os.environ["PATH"],
            **env,
        },
    )
    if process.returncode != 0:
        if error_as_none:
            return None
        process.check_returncode()
    stdout = str(process.stdout, encoding="utf-8").strip()
    print(f"[debug] stdout: {stdout}")
    return stdout


def run_git(
    folder: Path, args: list[str], error_as_none: bool = False, env: dict[str, str] = {}
):
    return run_raw(
        ["git", "-C", str(folder), *args], error_as_none=error_as_none, env=env
    )


def mirror_repo(upstream: str, folder: Path, auth_header: Optional[str] = None):
    print(
        f"mirroring {upstream} into {folder} (has auth_header? {auth_header is not None})"
    )
    auth_env = (
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: {auth_header}",
            "GIT_TRACE": "1",
            "GIT_TRANSFER_TRACE": "1",
            "GIT_CURL_VERBOSE": "1",
        }
        if auth_header
        else {}
    )
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
        run_raw(
            [
                "git",
                "clone",
                "--mirror",
                upstream,
                str(folder),
            ],
            env=auth_env,
        )
    else:
        run_git(
            folder,
            [
                "fetch",
                "-p",
                "origin",
            ],
            env=auth_env,
        )


def gh_api(config: Config, path: str, query_params: dict[str, str]):
    assert path.startswith("/")
    print(f"[debug] requesting {path} with {query_params}")
    response = requests.get(
        f"https://api.github.com{path}",
        headers={
            "X-GitHub-Api-Version": "2026-03-10",
            "Authorization": f"Bearer {config.github_token}",
        },
        params=query_params,
    )  # todo: handle 429
    response.raise_for_status()
    return response.json()


@dataclasses.dataclass
class GitHubRepo:
    name: str
    upstream: str
    private: bool


def mirror_github(config: Config, github: GitHubNamespaceSource, folder: Path):
    repos = prepare_github_repos(config, github)
    basic_auth = "Basic " + base64.b64encode(
        f"x-access-token:{config.github_token}".encode("ascii")
    ).decode("ascii")
    for repo in repos:
        mirror_repo(
            repo.upstream, folder / (repo.name + ".git"), auth_header=basic_auth
        )


def prepare_github_repos(config: Config, github: GitHubNamespaceSource):
    print(f"preparing to fetch github repos for {github.entity}")
    path: str
    if github.entity_type == GitHubEntityType.USER:
        path = f"/users/{github.entity}/repos"
    elif github.entity_type == GitHubEntityType.ORGANIZATION:
        path = f"/orgs/{github.entity}/repos"
    else:
        assert_unreachable(github.entity_type)
    page = 1
    repos: list[GitHubRepo] = []
    while True:
        json = gh_api(config, path, {"per_page": "100", "page": str(page)})
        if len(json) == 0:
            break
        for repo in json:
            repos.append(GitHubRepo(repo["name"], repo["html_url"], repo["private"]))
        print(f"fetched {len(repos)} so far")
        page += 1
    print("done fetching repos")
    return repos


def pull(args: argparse.Namespace):
    validate(args, print_ok=False)
    config: Config = args.config
    if config.github_token_file:
        config.github_token = config.github_token_file.read_text().strip()
    root = config.root
    for s in config.sources:
        if isinstance(s, GitHubNamespaceSource):
            mirror_github(config, s, root / (s.prefix or s.entity))
        elif isinstance(s, GitSource):
            mirror_repo(s.upstream, root / s.name)
        else:
            assert_unreachable(s)


def load_config(s: str) -> Config:
    p = Path(s)
    text = p.read_text()
    config = dec.decode(text)
    return config


def main():
    parser = argparse.ArgumentParser(
        prog="git-mirror-tool",
        description="Mirror a set of git repositories from various sources to a local folder",
    )
    parser.add_argument("--config", type=load_config)
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
