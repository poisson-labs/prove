"""Where a sweep runs: what is checked before anything starts, and what the reader is told.

Each check refuses with one ``error:`` line and at most one ``next:``, in the order a reader would
fix them, so the first missing piece is the one named. A check never asks for, reads out, stores,
prints or logs a secret; never writes cloud configuration; never signs in; never creates anything
in the account. The cloud is reached only through its own CLI's sign-in on this machine.
"""

from __future__ import annotations

import configparser
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from poisson_prove import _prices_cloud

INSTALL = 'pip install "poisson-prove[cloud]"'
_AWS_CLI_DOCS = "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
_QUOTA_CODE = "L-1216C47A"
#: How long one call of the cloud's CLI may take.
_CLI_S = 120.0


@dataclass(frozen=True)
class CloudReady:
    provider: str
    account: str
    masked: str
    notes: tuple[str, ...] = field(default_factory=tuple)


def _refuse(message: str, nexts: tuple[str, ...] = ()) -> Exception:
    from poisson_prove.executor_cloud import CloudRefusal

    return CloudRefusal(message, nexts)


def _probe(provider: str, region: str) -> dict[str, Any]:
    from poisson_prove import executor_cloud

    try:
        done = subprocess.run(
            [*executor_cloud._head_argv(), "probe", provider, region],  # noqa: SLF001
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=300,
            start_new_session=True,
        )
    except (OSError, subprocess.SubprocessError):
        return {"missing": True}
    for line in reversed(done.stdout.splitlines()):
        if line.strip().startswith("{"):
            try:
                loaded = json.loads(line)
            except ValueError:
                continue
            if isinstance(loaded, dict):
                return loaded
    return {"missing": True}


def _sso_profile() -> bool:
    """Whether the active AWS profile signs in through IAM Identity Center (``aws sso login``)."""
    path = os.environ.get("AWS_CONFIG_FILE") or str(Path.home() / ".aws" / "config")
    profile = os.environ.get("AWS_PROFILE") or os.environ.get("AWS_DEFAULT_PROFILE") or "default"
    parser = configparser.RawConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return False
    section = "default" if profile == "default" else f"profile {profile}"
    if not parser.has_section(section):
        return False
    return parser.has_option(section, "sso_session") or parser.has_option(section, "sso_start_url")


def mask(account: str) -> str:
    from poisson_prove.executor_cloud import mask as masked

    return masked(account)


def _aws(aws: str, *args: str) -> str | None:
    """What one read-only call of the AWS CLI printed, or None when it failed or did not answer.
    Like every process Prove starts for the cloud backend, it runs in a session of its own."""
    try:
        done = subprocess.run(
            [aws, *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=_CLI_S,
            start_new_session=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _quota(aws: str, region: str) -> float | None:
    """The account's vCPU quota for on-demand standard instances in ``region``, read-only, or None
    when it could not be read."""
    quota = _aws(
        aws,
        *("service-quotas", "get-service-quota", "--service-code", "ec2"),
        *("--quota-code", _QUOTA_CODE, "--region", region, "--output", "json"),
    )
    if quota is None:
        return None
    try:
        return float(json.loads(quota)["Quota"]["Value"])
    except (ValueError, KeyError, TypeError):
        return None


def aws_quota(region: str) -> float | None:
    """The same, read again after the check: for a start AWS refused on the quota."""
    aws = shutil.which("aws")
    return None if aws is None else _quota(aws, region)


def check_cloud(options: Any) -> CloudReady:
    """The checks before a cloud sweep, in order. Returns who is signed in, masked, and the
    notes to print."""
    from poisson_prove.executor_cloud import _PIN, resolve

    provider = options.provider
    name = _prices_cloud.NAMES.get(provider, provider)
    notes: list[str] = []
    probe = _probe(provider, options.region)
    if probe.get("missing"):
        raise _refuse("the cloud extra is not installed", (INSTALL,))
    if probe.get("software") != _PIN:
        raise _refuse(
            f"the cloud extra installed the cluster software at {probe.get('software')}, and Prove "
            f"runs it at {_PIN} only",
            (INSTALL,),
        )
    if provider == "aws" and probe.get("credentials") == "crt":
        raise _refuse(
            "the cloud extra is incomplete: signing in with aws login needs a package it installs",
            (INSTALL,),
        )
    if provider not in _prices_cloud.OFFERED:
        offered = ", ".join(_prices_cloud.NAMES[p] for p in _prices_cloud.OFFERED)
        raise _refuse(f"{name} is not yet supported by Prove; {offered} is")
    aws = shutil.which("aws")
    if aws is None:
        raise _refuse(
            "the AWS CLI is not installed; Prove uses your AWS sign-in through it "
            f"({_AWS_CLI_DOCS})"
        )
    signed = _aws(aws, "sts", "get-caller-identity", "--output", "json")
    account = None
    if signed is not None:
        try:
            account = str(json.loads(signed)["Account"])
        except (ValueError, KeyError, TypeError):
            account = None
    if account is None:
        raise _refuse(
            "this machine is not signed in to AWS",
            ("aws sso login" if _sso_profile() else "aws login",),
        )
    resolved = resolve(options)
    minor = f"3.{sys.version_info.minor}"
    match = re.fullmatch(r"python:3\.(\d+)(?:[.\-].*)?", resolved.image)
    if match is None:
        raise _refuse(
            f"image {resolved.image} does not name the Python it runs; the rollouts must run on "
            f'this machine\'s {minor} (image = "python:{minor}")'
        )
    if f"3.{match[1]}" != minor:
        raise _refuse(
            f"image {resolved.image} runs Python 3.{match[1]} and this machine runs {minor}; the "
            f'rollouts must run on the same minor version (image = "python:{minor}")'
        )
    need = options.nodes * resolved.vcpus
    if need > resolved.max_vcpus:
        raise _refuse(
            f"{options.nodes} × {options.machine_type} is {need} vCPUs, over max_vcpus "
            f"{resolved.max_vcpus}"
        )
    allowed = _quota(aws, options.region)
    if allowed is None:
        notes.append(
            f"your AWS account's vCPU quota in {options.region} could not be read, so it was not "
            f"checked; the cluster needs {need} vCPUs"
        )
    elif allowed < need:
        raise _refuse(
            f"your AWS account allows {int(allowed)} vCPUs of on-demand standard instances in "
            f"{options.region} and the cluster needs {need}; lower nodes, or ask AWS for more"
        )
    return CloudReady(provider, account, mask(account), tuple(notes))


def check_modal() -> None:
    """Modal's sign-in, asked of Modal's own client: a token configured on this machine. The
    token is never read into anything Prove prints, logs or stores."""
    try:
        from modal.config import config
    except Exception:  # noqa: BLE001 - a client with no configuration to ask cannot be asked
        return
    try:
        token = config.get("token_id")
    except Exception:  # noqa: BLE001
        token = None
    if not token:
        raise _refuse("this machine is not signed in to Modal", ("modal setup",))
