"""C2 of 0.3.0, Remote backends: what is checked before anything starts, and what the reader is told.

The frozen tests for R1 to R8 (Remote Backends Spec §7.1 to §7.3 and §15 C2; RB-15, RB-16, RB-26
to RB-28), on the fakes of ``rb_cloud_support.py``: a fake ``aws`` (and ``gcloud`` and ``az``) on
``PATH``, the fake SDK and the fake cluster software in the probe's interpreter, a fake Modal
client in this process. Nothing reaches a network or a cloud.

**What the tests fix that the invariants leave open:**

- The probe of §7.1's first two rows is one process started through ``_head_argv()``: it imports
  the cluster software at the pin and resolves the SDK's credentials (``boto3.Session(...)
  .get_credentials()``) in that same interpreter. A refusal starts at most that one process.
- The quota is read with ``aws service-quotas get-service-quota --service-code ec2 --quota-code
  L-1216C47A --region <region> --output json``: with the sign-in probe, the only two calls a check
  makes. A refused read is one ``note:`` line naming the quota, and the plan goes on.
- An SSO profile is the active profile (``AWS_PROFILE``, else ``default``) of the AWS config file
  (``AWS_CONFIG_FILE``, else ``~/.aws/config``) holding ``sso_session`` or ``sso_start_url``. An
  expired session reads as not signed in.
- R6's environment: Prove adds no variable holding a credential to a probe's environment (one it
  inherited stays as it was), puts none in an argument list, never opens the shared credentials
  file, and no output, record, ledger or store holds one.
- Modal's sign-in is asked of Modal's client in this process, ``modal.config.config.get
  ("token_id")``, never ``token_secret``: the ``modal`` command's own ``token info`` calls
  Modal's server (yes/no).
- An image whose tag names no Python minor (not ``python:3.N…``) is refused before start, since
  a mismatch is only found after the nodes bill (yes/no).
- On Windows ``--backend cloud`` is one ``error:`` line naming Windows and not the cluster
  software, before anything else (RB-16).
"""

from __future__ import annotations

import contextlib
import importlib.abc
import importlib.machinery
import json
import os
import pathlib
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from rb_cloud_support import (
    ACCOUNT,
    MASKED,
    PLANTED,
    REGION,
    TYPES,
    CloudWorld,
    Pool,
    cloud_table,
    secrets_in,
    this_minor,
    world,
)

STS = ["sts", "get-caller-identity", "--output", "json"]
QUOTA = ["service-quotas", "get-service-quota", "--service-code", "ec2", "--quota-code", "L-1216C47A",
         "--region", REGION, "--output", "json"]
INSTALL = '  next: pip install "poisson-prove[cloud]"'
ROWS = {
    "extra": ["error: the cloud extra is not installed", INSTALL],
    "crt": ["error: the cloud extra is incomplete: signing in with aws login needs a package it installs",
            INSTALL],
    "offered-gcp": ["error: Google Cloud is not yet supported by Prove; AWS is"],
    "offered-azure": ["error: Azure is not yet supported by Prove; AWS is"],
    "cli": ["error: the AWS CLI is not installed; Prove uses your AWS sign-in through it "
            "(https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)"],
    "signed-in": ["error: this machine is not signed in to AWS", "  next: aws login"],
    "machine": [f"error: m7i.3xlarge is not in Prove's AWS prices for {REGION}; the machine types are "
                + ", ".join(TYPES)],
    "image": [f"error: image python:3.9 runs Python 3.9 and this machine runs {this_minor()}; the rollouts "
              f'must run on the same minor version (image = "python:{this_minor()}")'],
    "ceiling": ["error: 6 × m7i.2xlarge is 48 vCPUs, over max_vcpus 32"],
    "quota": [f"error: your AWS account allows 40 vCPUs of on-demand standard instances in {REGION} and "
              "the cluster needs 48; lower nodes, or ask AWS for more"],
}


@pytest.fixture(scope="module")
def pool() -> Any:
    shared = Pool(2)
    yield shared
    shared.stop()


@pytest.fixture
def w(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Any:
    with world(tmp_path, monkeypatch, pool) as made:
        yield made


class _Hidden(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        if fullname.partition(".")[0] == "burla":
            raise ModuleNotFoundError(f"No module named {fullname!r}", name=fullname)
        return None


def hide_the_extra(w: CloudWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    """The cloud extra not installed: in this process and in the probe's interpreter alike."""
    w.mode = "absent"
    w.patch_seams()
    monkeypatch.setattr(sys, "meta_path", [_Hidden(), *sys.meta_path])
    for name in [n for n in sys.modules if n.partition(".")[0] == "burla"]:
        monkeypatch.delitem(sys.modules, name)


def refused_cleanly(w: CloudWorld, sweeps: int = 1) -> list[str]:
    """R1's "nothing is started, written or spent", over ``sweeps`` refused or dry sweeps: at most
    the one probe and the two read-only CLI calls each."""
    problems = []
    if w.ledger():
        problems.append("a ledger line was written")
    if w.records():
        problems.append(f"an ownership record was written: {w.records()}")
    if w.routes():
        problems.append(f"the cluster software was asked for something: {w.routes()}")
    if w.alive_heads() or w.heads():
        problems.append("a coordinator was started")
    if len(w.software_starts()) > sweeps:
        problems.append(f"more than the probe was started: {w.software_starts()}")
    if w.store.exists() and any(p.is_dir() and not p.name.startswith(".") for p in w.store.iterdir()):
        problems.append("a run was stored")
    calls = [c["argv"] for c in w.aws_calls()]
    if any(argv not in (STS, QUOTA) for argv in calls) or calls.count(STS) > sweeps or calls.count(QUOTA) > sweeps:
        problems.append(f"the AWS CLI was asked for more than the probes: {calls}")
    if w.other_cli_calls():
        problems.append(f"gcloud or az was run: {w.other_cli_calls()}")
    return problems


def break_row(w: CloudWorld, monkeypatch: pytest.MonkeyPatch, row: str, table: dict[str, Any]) -> None:
    if row == "extra":
        hide_the_extra(w, monkeypatch)
    elif row == "crt":
        w.sdk(credentials="crt")
    elif row == "offered-gcp":
        table["provider"] = "gcp"
    elif row == "offered-azure":
        table["provider"] = "azure"
    elif row == "cli":
        w.remove_cli("aws")
    elif row == "signed-in":
        w.aws_state(signed_in=False)
    elif row == "machine":
        table["machine_type"] = "m7i.3xlarge"
    elif row == "image":
        table["image"] = "python:3.9"
    elif row == "ceiling":
        table.update(nodes=6, max_vcpus=32)
    elif row == "quota":
        table.update(nodes=6)
        w.aws_state(quota=40)


# ---------- R1: each row, its line, nothing started ----------


@pytest.mark.parametrize("row", list(ROWS))
def test_r1_each_row_refuses_with_its_line_and_exit_1_and_nothing_starts(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch, row: str
) -> None:
    table = cloud_table()
    break_row(w, monkeypatch, row, table)
    w.write_spec(table=table)
    done = w.sweep()
    assert done.code == 1, done
    lines = [line for line in done.err.splitlines() if line.startswith(("error:", "  next:"))]
    assert lines == ROWS[row], done
    assert refused_cleanly(w) == [], done


def test_r1_the_extra_is_checked_in_the_probes_interpreter_not_only_here(w: CloudWorld) -> None:
    """Findable in this process, not importable where the launcher runs: still the extra's line."""
    w.mode = "absent"
    w.patch_seams()
    w.write_spec(table=cloud_table())
    done = w.sweep("--dry-run")
    assert done.code == 1, done
    lines = [line for line in done.err.splitlines() if line.startswith(("error:", "  next:"))]
    assert lines == ROWS["extra"], done
    assert refused_cleanly(w) == [], done


@pytest.mark.parametrize("version", ["1.8.2", "1.8.5", "1.9.0"])
def test_r1_the_software_at_another_version_is_refused_before_anything_starts(w: CloudWorld, version: str) -> None:
    """§5 and §7.1: the pin is exact and checked where the launcher runs, before anything starts."""
    w.script_job(version=version)
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert len(done.errors) == 1 and version in done.errors[0] and "1.8.4" in done.errors[0], done
    assert "burla" not in done.err.lower(), done
    assert done.nexts == ['next: pip install "poisson-prove[cloud]"'], done
    assert refused_cleanly(w) == [], done


def test_r1_the_rows_are_checked_in_the_tables_order(w: CloudWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    """Everything missing at once; each fix in turn uncovers the next row, never a later one."""
    order = ["extra", "crt", "cli", "machine", "image", "ceiling", "quota", "cap"]
    table = cloud_table(machine_type="m7i.3xlarge", image="python:3.9", nodes=6, max_vcpus=32,
                        stop_cost=0.001, max_cost=0.001)
    with monkeypatch.context() as hidden:
        hide_the_extra(w, hidden)
        w.sdk(credentials="crt")
        w.remove_cli("aws")
        w.aws_state(quota=40)
        w.write_spec(table=table)
        assert w.sweep().errors[:1] == ROWS["extra"][:1]
    w.mode = "fake"
    w.patch_seams()
    named = []
    fixes = {
        "crt": lambda: w.sdk(credentials="ok"),
        "cli": lambda: w.install_cli("aws", Path(__file__).parent / "bu_fixtures" / "cloud_bin" / "aws.py"),
        "machine": lambda: table.update(machine_type="m7i.2xlarge"),
        "image": lambda: table.update(image=f"python:{this_minor()}"),
        "ceiling": lambda: table.update(max_vcpus=48),
        "quota": lambda: w.aws_state(quota=64),
        "cap": lambda: table.update(stop_cost=5.0, max_cost=5.0),
    }
    for row in order[1:]:
        w.write_spec(table=table)
        done = w.sweep("--dry-run")
        assert done.code == 1, (row, done)
        named.append(done.errors[0])
        expected = ROWS[row][0] if row != "cap" else None
        if expected is not None:
            assert done.errors[0] == expected, (row, done)
        else:
            assert "over the cap" in done.errors[0], (row, done)
            assert done.out.startswith("plan  "), done
        fixes[row]()
    w.write_spec(table=table)
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    assert refused_cleanly(w, sweeps=len(order) + 1) == [], done


def test_r1_a_refusal_is_the_same_under_dry_run(w: CloudWorld) -> None:
    table = cloud_table(nodes=6, max_vcpus=32)
    w.write_spec(table=table)
    done = w.sweep("--dry-run")
    assert (done.code, done.errors) == (1, ROWS["ceiling"][:1]), done
    assert refused_cleanly(w) == [], done


def test_r1_google_cloud_and_azure_run_none_of_their_tools(w: CloudWorld) -> None:
    for provider in ("gcp", "azure"):
        w.write_spec(table=cloud_table(provider=provider))
        done = w.sweep()
        assert done.code == 1, done
    assert w.other_cli_calls() == []
    assert [c["argv"] for c in w.aws_calls()] == []


# ---------- R2: the sign-in probe ----------


def test_r2_the_sign_in_probe_and_the_quota_read_are_the_only_cli_calls(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    assert [c["argv"] for c in w.aws_calls()] == [STS, QUOTA]
    assert w.other_cli_calls() == []


def test_r2_the_account_is_the_one_the_probe_reports_masked(w: CloudWorld) -> None:
    w.aws_state(account="111122223333")
    w.write_spec(table=cloud_table())
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    assert "Account: AWS 1111…3333, signed in with the AWS CLI" in done.out, done
    assert "111122223333" not in done.out + done.err


# ---------- R3: which sign-in command ----------


@pytest.mark.parametrize(
    ("config", "profile", "command"),
    [
        ("[default]\nregion = us-east-2\n", None, "aws login"),
        ("[profile work]\nregion = us-east-2\n", "work", "aws login"),
        ("[profile work]\nsso_session = lab\nsso_account_id = 603052864933\n\n[sso-session lab]\n"
         "sso_start_url = https://lab.awsapps.com/start\nsso_region = us-east-1\n", "work", "aws sso login"),
        ("[default]\nsso_start_url = https://lab.awsapps.com/start\nsso_region = us-east-1\n", None,
         "aws sso login"),
    ],
    ids=["default", "named", "sso-session", "legacy-sso-default"],
)
def test_r3_an_sso_profile_gets_aws_sso_login_and_any_other_aws_login(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch, config: str, profile: str | None, command: str
) -> None:
    w.aws_config.write_text(config, encoding="utf-8")
    if profile is not None:
        monkeypatch.setenv("AWS_PROFILE", profile)
    w.aws_state(signed_in=False)
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert done.errors == ["error: this machine is not signed in to AWS"], done
    assert done.nexts == [f"next: {command}"], done


def test_r3_an_expired_session_reads_as_not_signed_in(w: CloudWorld) -> None:
    w.aws_state(signed_in="expired")
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert [line for line in done.err.splitlines() if line.startswith(("error:", "  next:"))] == ROWS["signed-in"], done


# ---------- R4: botocore[crt] ----------


def test_r4_a_missing_crt_is_named_and_not_the_sign_in_even_when_signed_out(w: CloudWorld) -> None:
    w.sdk(credentials="crt")
    w.aws_state(signed_in=False)
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert done.code == 1, done
    assert [line for line in done.err.splitlines() if line.startswith(("error:", "  next:"))] == ROWS["crt"], done
    assert "next: aws login" not in done.err and "not signed in" not in done.err, done
    assert "MissingDependency" not in done.err, done


def test_r4_no_credentials_at_all_is_left_to_the_sign_in_probe(w: CloudWorld) -> None:
    w.sdk(credentials="none")
    w.aws_state(signed_in=False)
    w.write_spec(table=cloud_table())
    done = w.sweep()
    assert [line for line in done.err.splitlines() if line.startswith(("error:", "  next:"))] == ROWS["signed-in"], done


# ---------- R5: the quota ----------


def test_r5_a_quota_read_refused_is_one_note_and_the_plan_goes_on(w: CloudWorld) -> None:
    w.aws_state(quota="denied")
    w.write_spec(table=cloud_table(nodes=6))
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    assert done.out.startswith("plan  "), done
    quota_notes = [note for note in done.notes if "quota" in note]
    assert len(quota_notes) == 1, done
    assert "AccessDenied" not in done.err, done


def test_r5_a_quota_that_fits_passes_quietly(w: CloudWorld) -> None:
    w.aws_state(quota=48)
    w.write_spec(table=cloud_table(nodes=6))
    done = w.sweep("--dry-run")
    assert done.code == 0 and [note for note in done.notes if "quota" in note] == [], done


def test_r5_a_quota_below_the_need_is_refused_with_the_numbers(w: CloudWorld) -> None:
    w.aws_state(quota=40)
    w.write_spec(table=cloud_table(nodes=6))
    done = w.sweep("--dry-run")
    assert (done.code, done.errors) == (1, ROWS["quota"]), done


# ---------- R6: no secret anywhere ----------


@contextlib.contextmanager
def opened_files() -> Iterator[list[str]]:
    seen: list[str] = []
    on = [True]

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if on[0] and event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            seen.append(os.fsdecode(args[0]))

    sys.addaudithook(hook)
    try:
        yield seen
    finally:
        on[0] = False


def _everything_written(w: CloudWorld) -> str:
    parts = []
    for folder in (w.store, w.xdg, w.state):
        if folder.exists():
            parts += [p.read_text(encoding="utf-8", errors="replace") for p in folder.rglob("*")
                      if p.is_file() and p.name not in ("sdk.json",)]
    parts += [p.read_text(encoding="utf-8") for p in w.root.glob("*.jsonl")]
    return "\n".join(parts)


@pytest.mark.parametrize("ending", ["dry-run", "refused", "signed-out", "run"])
def test_r6_no_probe_output_argument_or_added_variable_and_no_record_holds_a_secret(
    w: CloudWorld, ending: str
) -> None:
    table = cloud_table(nodes=6, max_vcpus=32) if ending == "refused" else cloud_table()
    if ending == "signed-out":
        w.aws_state(signed_in=False)
        ending = "refused"
    w.write_spec(table=table)
    inherited = dict(os.environ)
    with opened_files() as seen:
        done = w.sweep(*(["--dry-run"] if ending == "dry-run" else []), "--json") if ending != "refused" else w.sweep()
    assert done.code == (1 if ending == "refused" else 0), done
    assert secrets_in(done.out + done.err) == [], done
    for call in w.aws_calls():
        assert secrets_in(" ".join(call["argv"])) == [], call["argv"]
        added = {k: v for k, v in call["env"].items() if inherited.get(k) != v}
        assert secrets_in(json.dumps(added)) == [], sorted(added)
    probe_out = w.state / "software-out.txt"
    assert secrets_in(probe_out.read_text(encoding="utf-8") if probe_out.exists() else "") == []
    assert secrets_in(_everything_written(w)) == []
    assert str(w.aws_credentials) not in seen, "Prove opened the shared credentials file"
    if ending == "run":
        assert json.dumps(PLANTED["sdk"]) not in json.dumps(w.manifest(w.runs()[0]["run_id"]))


# ---------- R7: Modal's sign-in ----------


class _Config:
    """Modal's configuration as its client reads it; records every key asked for."""

    def __init__(self, token: str | None) -> None:
        self.values = {"token_id": token, "token_secret": None if token is None else PLANTED["sdk"] + "-modal"}
        self.asked: list[str] = []

    def get(self, key: str, *args: Any, **kwargs: Any) -> Any:
        self.asked.append(key)
        return self.values.get(key)

    def __getitem__(self, key: str) -> Any:
        return self.get(key)


class _Image:
    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: self


def install_modal(monkeypatch: pytest.MonkeyPatch, token: str | None) -> _Config:
    fake = types.ModuleType("modal")
    fake.__path__ = []  # type: ignore[attr-defined]
    fake.__spec__ = importlib.machinery.ModuleSpec("modal", None, is_package=True)
    fake.__version__ = "1.6.3"  # type: ignore[attr-defined]
    config_module = types.ModuleType("modal.config")
    config = _Config(token)
    config_module.config = config  # type: ignore[attr-defined]
    fake.config = config_module  # type: ignore[attr-defined]

    class App:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def function(self, **kwargs: Any) -> Any:
            return lambda fn: fn

        @contextlib.contextmanager
        def run(self) -> Iterator[Any]:
            raise AssertionError("a dry run must not start Modal")
            yield self

    fake.App = App  # type: ignore[attr-defined]
    fake.Image = types.SimpleNamespace(debian_slim=lambda *a, **k: _Image(),  # type: ignore[attr-defined]
                                       from_dockerfile=lambda *a, **k: _Image())
    fake.Secret = types.SimpleNamespace(from_name=lambda *a, **k: object())  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "modal", fake)
    monkeypatch.setitem(sys.modules, "modal.config", config_module)
    return config


MODAL_TABLE = '\n[modal]\nconcurrency = 1\nbatch_size = 8\n\n[modal.image]\npython = "3.11"\n'


def test_r7_no_modal_token_is_refused_before_the_plan(w: CloudWorld, monkeypatch: pytest.MonkeyPatch) -> None:
    config = install_modal(monkeypatch, None)
    w.write_spec(extra=MODAL_TABLE)
    done = w.sweep(backend="modal")
    assert done.code == 1, done
    assert done.out == "", done
    assert [line for line in done.err.splitlines() if line.startswith(("error:", "  next:"))] == [
        "error: this machine is not signed in to Modal", "  next: modal setup"], done
    assert "token_secret" not in config.asked, config.asked


def test_r7_a_configured_token_lets_the_plan_through_and_is_never_shown(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = install_modal(monkeypatch, "ak-planted-modal-token-id-0000")
    w.write_spec(extra=MODAL_TABLE)
    for args in (("--dry-run",), ("--dry-run", "--json")):
        done = w.sweep(*args, backend="modal")
        assert done.code == 0, done
        shown = done.out + done.err
        assert "ak-planted-modal-token-id-0000" not in shown and PLANTED["sdk"] not in shown, done
    assert "token_id" in config.asked and "token_secret" not in config.asked, config.asked


# ---------- R8: the dry run ----------


def test_r8_dry_run_runs_the_probes_starts_nothing_and_prints_the_plan(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    done = w.sweep("--dry-run")
    assert done.code == 0, done
    assert done.out.startswith("plan  "), done
    assert [c["argv"] for c in w.aws_calls()] == [STS, QUOTA]
    assert len(w.software_starts()) == 1, w.software_starts()
    assert refused_cleanly(w) == [], done
    assert f"Account: AWS {MASKED}, signed in with the AWS CLI" in done.out, done
    assert ACCOUNT not in done.out + done.err


def test_r8_a_no_at_the_question_starts_nothing_either(w: CloudWorld) -> None:
    w.write_spec(table=cloud_table())
    done = w.run("sweep", "prove.toml", "--target", "bu_targets.cloud:quick", "--backend", "cloud",
                 "--max-mde", "1", stdin="n\n")
    assert done.code == 1, done
    assert refused_cleanly(w) == [], done


# ---------- RB-16: Windows ----------


def simulate_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """``os.name == "nt"`` as PF9.3 simulates it; the module defining ``pathlib.Path`` keeps the
    real name."""
    defining = sys.modules[pathlib.Path.__module__]
    proxy = types.ModuleType("os")
    proxy.__getattr__ = lambda attr: getattr(os, attr)  # type: ignore[method-assign]
    proxy.name = os.name
    monkeypatch.setattr(defining, "os", proxy)
    monkeypatch.setattr(os, "name", "nt")


def test_rb16_the_cloud_backend_on_windows_is_refused_first_naming_windows(
    w: CloudWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    w.write_spec(table=cloud_table())
    with monkeypatch.context() as inner:
        simulate_windows(inner)
        done = w.sweep("--dry-run")
    assert done.code == 1 and done.out == "", done
    assert len(done.errors) == 1 and "Windows" in done.errors[0], done
    assert "burla" not in done.err.lower(), done
    assert w.aws_calls() == [] and w.software_starts() == [], (w.aws_calls(), w.software_starts())
