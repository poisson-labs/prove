"""The cloud backend's test world: the fakes of Burla 1.8.4, the cloud's CLIs and SDK, set up for one
test, and the readers of what they recorded. Shared by the Remote backends tests of C1 to C4
(``test_rb_cloud_*.py``).

**No cloud, no Burla, no network.** Every process the cloud backend starts that imports the
cluster software is started through one of three seams of ``poisson_prove.executor_cloud``, each
a function returning the command to run, which a test points at ``tests/bu_fixtures/software.py``:

- ``_launcher_argv()``: the job's launcher, ``_cloud_submit.py`` (0.2.1's ``_burla_submit.py``);
- ``_head_argv()``: Prove's coordinator launcher, ``_cloud_head.py``, which also runs the readiness
  probe of the cloud extra and the SDK's credentials (§7.1's first two rows), with Prove's own
  arguments appended;
- ``_cli_argv()``: the cluster software's CLI, ``python -I -m burla``, with Prove's
  ``--head URL`` and verb appended.

There the fake ``burla`` (``tests/bu_fixtures/burla``) and the fake ``boto3`` and ``botocore``
(``tests/bu_fixtures/sdk``) come first on the path. The fake ``aws``, ``gcloud`` and ``az``
(``tests/bu_fixtures/cloud_bin``) are the only cloud CLIs on ``PATH``. The fake ``aws`` answers
``ec2 describe-instances`` and ``ec2 terminate-instances`` over the fake cluster's own nodes, one
instance each (``tests/bu_fixtures/fake_ec2.py``), so what the cluster software lists and what the
cloud holds can differ as they did in the AWS check of 2026-11-12. The ownership record lives
under the test's own ``XDG_STATE_HOME``; ``HOME``, ``AWS_CONFIG_FILE`` and
``AWS_SHARED_CREDENTIALS_FILE`` point into the test's folder, which plants a secret in the
credentials file and in ``AWS_SECRET_ACCESS_KEY`` that no output may carry (R6).

The fake's own records (management calls, heads started, signals a head received, the nodes the
cloud lists) are read back through ``CloudWorld``. Every head a test leaves alive is killed when
the test ends.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import sysconfig
import tempfile
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from poisson_prove import cli

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "bu_fixtures"
FAKE_EC2 = FIXTURES / "fake_ec2.py"
TARGETS = FIXTURES / "targets"
SOFTWARE = FIXTURES / "software.py"
LAUNCH = FIXTURES / "launch.py"
HEAD_PROCESS = FIXTURES / "burla_head.py"
WORKER = FIXTURES / "worker.py"
PROVE = FIXTURES / "prove_with_fakes.py"
CLOUD_BIN = FIXTURES / "cloud_bin"
SITE_PACKAGES = sysconfig.get_paths()["purelib"]
SRC = Path(__file__).resolve().parents[1] / "src" / "poisson_prove"

PIN = "1.8.4"
ACCOUNT = "603052864933"
MASKED = "6030…4933"
REGION = "us-east-2"
MACHINE = "m7i.2xlarge"
PRICE = 0.4687
PRICE_DATE = "2026-11-06"
TYPES = ("m7i.large", "m7i.xlarge", "m7i.2xlarge", "m7i.4xlarge", "m7i.8xlarge", "m7i.16xlarge")
VCPUS = {"m7i.large": 2, "m7i.xlarge": 4, "m7i.2xlarge": 8, "m7i.4xlarge": 16, "m7i.8xlarge": 32,
         "m7i.16xlarge": 64}
TABLE_REGIONS = ("us-east-1", "us-east-2", "us-west-2", "eu-west-1", "eu-central-1")
WATCH = ["poisson_prove", "bu_targets", "bu_version", "bu_helper", "bu_dirty"]
#: The planted secrets of R6: no output, record, ledger, store or argument list may hold one.
PLANTED = {
    "AWS_SECRET_ACCESS_KEY": "planted-env-secret-7Qx9VvT2kLmN4pR8sW1yZ3aB5cD",
    "AWS_SESSION_TOKEN": "planted-env-token-IQoJb3JpZ2luX2VjEJr",
    "file": "planted-file-secret-Hq7Kp2Lm9Nx4Rt6Vw8Yz1Ab3",
    "sdk": "planted-sdk-secret-Zm5Xc8Vb2Nq4Lw7Kj1Hg9Fd3",
}
MANAGEMENT_ROUTES = ("GET /v1/management/cluster", "POST /v1/management/cluster/start",
                     "POST /v1/management/cluster/stop", "PATCH /v1/management/settings")
FORBIDDEN_ROUTES = ("POST /v1/settings", "/v1/cluster/import_history", "/v1/cluster/restart",
                    "POST /v1/management/cluster/restart", "DELETE /v1/cluster/")
SETTINGS_FIELDS = {"region", "machine_type", "quantity", "image", "disk_gb",
                   "inactivity_timeout_seconds", "max_vcpus"}


def cloud_module() -> Any:
    """``poisson_prove.executor_cloud``, imported when a test needs it: on a branch without it,
    each test that needs it fails, and nothing else in the file does."""
    import importlib

    return importlib.import_module("poisson_prove.executor_cloud")


def this_minor() -> str:
    return f"3.{sys.version_info.minor}"


#: Ctrl-C live in the child whatever the parent ignores: a test run started as a background
#: shell job inherits SIGINT ignored, and the interrupt tests need it to reach Prove.
_LIVE_INTERRUPT = (
    "import os, signal, sys\n"
    "signal.signal(signal.SIGINT, signal.SIG_DFL)\n"
    "os.execv(sys.executable, [sys.executable, *sys.argv[1:]])\n"
)


# ---------- fake workers ----------


class Pool:
    """Fake Burla workers, each a long-lived ``python -I -S`` interpreter serving one call at a
    time on a Unix socket (``tests/bu_fixtures/worker.py``)."""

    def __init__(self, n: int = 2) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="rb", dir="/tmp"))
        self.procs: list[subprocess.Popen[bytes]] = []
        self.workers: list[dict[str, Any]] = []
        for i in range(n):
            sock = str(self.dir / f"w{i}.sock")
            cwd = tempfile.mkdtemp(prefix="rb-worker-")
            proc = subprocess.Popen(
                [sys.executable, "-I", "-S", str(WORKER), sock, SITE_PACKAGES], env={}, cwd=cwd
            )
            self.procs.append(proc)
            self.workers.append({"socket": sock, "pid": proc.pid, "cwd": cwd})
        deadline = time.time() + 60
        for worker in self.workers:
            while not os.path.exists(worker["socket"] + ".ready"):
                assert time.time() < deadline, "a fake worker did not start"
                time.sleep(0.02)

    def stop(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=30)
        shutil.rmtree(self.dir, ignore_errors=True)
        for worker in self.workers:
            shutil.rmtree(worker["cwd"], ignore_errors=True)


# ---------- results ----------


@dataclass
class Done:
    code: int
    out: str
    err: str

    @property
    def errors(self) -> list[str]:
        return [line for line in self.err.splitlines() if line.startswith("error:")]

    @property
    def notes(self) -> list[str]:
        return [line for line in self.err.splitlines() if line.startswith("note:")]

    @property
    def nexts(self) -> list[str]:
        return [line.strip() for line in (self.out + self.err).splitlines()
                if line.strip().startswith("next:")]

    def __str__(self) -> str:
        return f"exit {self.code}\n--- stdout\n{self.out}\n--- stderr\n{self.err}"


def _toml(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml(v) for v in value) + "]"
    if isinstance(value, Path):
        return json.dumps(str(value))
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value)


def cloud_table(**over: Any) -> dict[str, Any]:
    """A ``[cloud]`` table with every required key (§4.1), small and cheap, the price from
    Prove's table."""
    table: dict[str, Any] = {
        "provider": "aws", "region": REGION, "machine_type": MACHINE, "nodes": 1,
        "ledger": "ledger.jsonl", "stop_cost": 5.0, "max_cost": 5.0,
        "est_seconds_per_episode": 0.01, "packages": ["bu_targets"], "batch_size": 2,
        "boot_minutes": 0.0, "idle_minutes": 2,
    }
    for key, value in over.items():
        if value is None:
            table.pop(key, None)
        else:
            table[key] = value
    return table


def spec_text(*, cells: Sequence[str] = ("a", "b"), replicates: int = 2,
              axes: Mapping[str, Sequence[Any]] | None = None, target: str | None = None,
              tables: str = "") -> str:
    text = (
        'target_id = "rb-cloud@v0"\nt_unit = "steps"\n'
        f"replicates = {replicates}\n"
    )
    if target is not None:
        text += f'target = "{target}"\n'
    text += f'\n[axes.cell]\ntype = "categorical"\nvalues = {_toml(list(cells))}\n'
    for name, values in (axes or {}).items():
        text += f'\n[axes.{name}]\ntype = "categorical"\nvalues = {_toml(list(values))}\n'
    return text + tables


def table_text(name: str, table: Mapping[str, Any]) -> str:
    return f"\n[{name}]\n" + "".join(f"{key} = {_toml(value)}\n" for key, value in table.items())


# ---------- the world ----------


class CloudWorld:
    """One test's fakes. ``run`` is the command line in this process; ``spawn`` is the command
    line as its own process (``prove_with_fakes.py``) for the tests that signal it."""

    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> None:
        self.root = root
        self.mp = monkeypatch
        self.pool = pool
        self.state = root / "fake-state"
        self.bin = root / "bin"
        self.xdg = root / "xdg-state"
        self.home = root / "home"
        self.store = root / "store"
        self.spec = root / "prove.toml"
        for folder in (self.state, self.bin, self.xdg, self.home):
            folder.mkdir(parents=True, exist_ok=True)
        (self.state / "workers.json").write_text(json.dumps(pool.workers), encoding="utf-8")
        self.script_job()
        self.script_cluster()
        self.sdk(credentials="ok")
        self.install_cli("aws", CLOUD_BIN / "aws.py")
        self.install_cli("gcloud", CLOUD_BIN / "refuse.py")
        self.install_cli("az", CLOUD_BIN / "refuse.py")
        self.aws_state(account=ACCOUNT, signed_in=True, quota=40,
                       ec2={"state": str(self.state), "fixtures": str(FIXTURES)})
        self.aws_config = root / "aws-config"
        self.aws_config.write_text("[default]\nregion = us-east-2\n", encoding="utf-8")
        self.aws_credentials = root / "aws-credentials"
        self.aws_credentials.write_text(
            "[default]\naws_access_key_id = AKIAPLANTEDFILEKEY00\n"
            f"aws_secret_access_key = {PLANTED['file']}\n", encoding="utf-8")
        for name in list(os.environ):
            if name.startswith(("AWS_", "BURLA_", "MODAL_")) or name == "DISABLE_BURLA_TELEMETRY":
                monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("PATH", os.pathsep.join([str(self.bin), "/usr/bin", "/bin"]))
        monkeypatch.setenv("XDG_STATE_HOME", str(self.xdg))
        monkeypatch.setenv("HOME", str(self.home))
        monkeypatch.setenv("AWS_CONFIG_FILE", str(self.aws_config))
        monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(self.aws_credentials))
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", PLANTED["AWS_SECRET_ACCESS_KEY"])
        monkeypatch.setenv("AWS_SESSION_TOKEN", PLANTED["AWS_SESSION_TOKEN"])
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAPLANTEDENVKEY000")
        monkeypatch.syspath_prepend(str(TARGETS))
        monkeypatch.chdir(root)
        self.mode = "fake"
        self.constants: dict[str, Any] = {}
        self._findable_burla()
        self.patch_seams()

    # -- setup --

    def install_cli(self, name: str, source: Path) -> None:
        target = self.bin / name
        target.write_text(f"#!{sys.executable} -I\n" + source.read_text(encoding="utf-8"),
                          encoding="utf-8")
        target.chmod(0o755)

    def remove_cli(self, name: str) -> None:
        (self.bin / name).unlink(missing_ok=True)

    def use_pool(self, pool: Pool) -> None:
        self.pool = pool
        (self.state / "workers.json").write_text(json.dumps(pool.workers), encoding="utf-8")

    def aws_state(self, **state: Any) -> None:
        path = self.bin / "aws-state.json"
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        current.update(state)
        path.write_text(json.dumps(current), encoding="utf-8")

    def sdk(self, **state: Any) -> None:
        body = {"planted": {"access_key": "AKIAPLANTEDSDKKEY000", "secret_key": PLANTED["sdk"],
                            "token": PLANTED["sdk"] + "-token"}, **state}
        (self.state / "sdk.json").write_text(json.dumps(body), encoding="utf-8")

    def script_job(self, attempts: Sequence[dict[str, Any]] = (),
                   default: dict[str, Any] | None = None, **top: Any) -> None:
        body = {"watch": WATCH, "attempts": list(attempts), "default": dict(default or {}), **top}
        (self.state / "script.json").write_text(json.dumps(body), encoding="utf-8")

    def script_cluster(self, **script: Any) -> None:
        (self.state / "cluster-script.json").write_text(json.dumps(script), encoding="utf-8")

    def watch_ledger(self, ledger: Path) -> None:
        (self.state / "ledger.path").write_text(str(ledger), encoding="utf-8")

    def _findable_burla(self) -> None:
        """The cluster software, at the pin, findable in this process but never imported here: the
        fake runs only in the processes the seams start."""
        findable = self.root / "findable-burla"
        (findable / "burla").mkdir(parents=True, exist_ok=True)
        (findable / "burla" / "__init__.py").write_text("", encoding="utf-8")
        dist = findable / f"burla-{PIN}.dist-info"
        dist.mkdir(exist_ok=True)
        (dist / "METADATA").write_text(f"Metadata-Version: 2.1\nName: burla\nVersion: {PIN}\n",
                                       encoding="utf-8")
        self.mp.syspath_prepend(str(findable))

    def software(self, *tail: str) -> list[str]:
        return [sys.executable, "-I", str(SOFTWARE), str(self.state), self.mode, *tail]

    def seams(self) -> dict[str, list[str]]:
        return {
            "_launcher_argv": self.software(str(SRC / "_cloud_submit.py")),
            "_head_argv": self.software(str(SRC / "_cloud_head.py")),
            "_cli_argv": self.software("-m", "burla"),
        }

    def patch_seams(self) -> None:
        try:
            ec = cloud_module()
        except ImportError:
            return
        for name, argv in self.seams().items():
            self.mp.setattr(ec, name, lambda argv=list(argv): list(argv))

    def set_constant(self, name: str, value: Any) -> None:
        self.constants[name] = value
        self.mp.setattr(cloud_module(), name, value)

    def write_spec(self, *, table: Mapping[str, Any] | None = None, name: str = "cloud",
                   extra: str = "", **spec: Any) -> Path:
        tables = "" if table is None else table_text(name, table)
        self.spec.write_text(spec_text(tables=tables + extra, **spec), encoding="utf-8")
        ledger = (table or {}).get("ledger")
        if isinstance(ledger, str):
            self.watch_ledger(self.root / ledger)
        return self.spec

    # -- the command line --

    def argv(self, *args: str) -> list[str]:
        return ["--store", str(self.store), *args]

    def run(self, *args: str, stdin: str = "") -> Done:
        out, err = io.StringIO(), io.StringIO()
        code = cli.main(self.argv(*args), stdout=out, stderr=err, stdin=io.StringIO(stdin))
        return Done(code, out.getvalue(), err.getvalue())

    def sweep(self, *args: str, target: str = "bu_targets.cloud:quick", yes: bool = True,
              backend: str = "cloud") -> Done:
        more = ["--yes"] if yes else []
        return self.run("sweep", self.spec.name, "--target", target, "--backend", backend,
                        "--max-mde", "1", *more, *args)

    def config(self) -> Path:
        path = self.root / "prove-with-fakes.json"
        path.write_text(json.dumps({"syspath": [str(TARGETS), str(self.root / "findable-burla")],
                                    "seams": self.seams(), "constants": self.constants}),
                        encoding="utf-8")
        return path

    def spawn(self, *args: str, target: str = "bu_targets.cloud:hold", stdout: Any = subprocess.PIPE,
              stderr: Any = subprocess.PIPE, sweep: bool = True) -> subprocess.Popen[bytes]:
        """The command line in its own process and session (so a test can signal its group as a
        terminal's Ctrl-C would), cwd the test's folder."""
        command = (["sweep", self.spec.name, "--target", target, "--backend", "cloud",
                    "--max-mde", "1", "--yes", *args] if sweep else list(args))
        return subprocess.Popen(
            [sys.executable, "-c", _LIVE_INTERRUPT, str(PROVE), str(self.config()), *self.argv(*command)],
            stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, cwd=self.root,
            env=dict(os.environ), start_new_session=True,
        )

    # -- what the fakes recorded --

    def _lines(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def management(self) -> list[dict[str, Any]]:
        """Every management call and head start or stop, in time order; answers left out."""
        return [e for e in self._lines(self.state / "management.jsonl")
                if not str(e["route"]).endswith(" answered")]

    def answers(self) -> list[dict[str, Any]]:
        return [e for e in self._lines(self.state / "management.jsonl")
                if str(e["route"]).endswith(" answered")]

    def routes(self) -> list[str]:
        return [str(e["route"]) for e in self.management()]

    def jobs(self) -> list[dict[str, Any]]:
        return [e for e in self._lines(self.state / "calls.jsonl") if e.get("event") == "start"]

    def timeline(self) -> list[str]:
        """The management calls and the job's calls, one word each, in time order: what L1 reads."""
        names = {
            "head start": "coordinator start", "head stop": "coordinator stop",
            "GET /v1/management/cluster": "status",
            "PATCH /v1/management/settings": "settings update",
            "POST /v1/management/cluster/start": "cluster start",
            "POST /v1/management/cluster/stop": "cluster stop",
        }
        events = [(e["time"], names.get(e["route"], e["route"])) for e in self.management()]
        events += [(e["time"], "job") for e in self.jobs()]
        return [name for _, name in sorted(events)]

    def software_starts(self) -> list[dict[str, Any]]:
        return self._lines(self.state / "software.jsonl")

    def aws_calls(self) -> list[dict[str, Any]]:
        return self._lines(self.bin / "aws-calls.jsonl")

    def other_cli_calls(self) -> list[dict[str, Any]]:
        return self._lines(self.bin / "gcloud-calls.jsonl") + self._lines(self.bin / "az-calls.jsonl")

    def heads(self) -> list[dict[str, Any]]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.state.glob("head-*.json"))
                if p.name != "head-signals.jsonl"]

    def head_signals(self) -> list[dict[str, Any]]:
        return self._lines(self.state / "head-signals.jsonl")

    def alive_heads(self) -> list[int]:
        return [h["pid"] for h in self.heads() if alive(h["pid"])]

    def cluster(self) -> dict[str, Any]:
        path = self.state / "cluster.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"nodes": [], "settings": {}}

    def listed_nodes(self) -> list[dict[str, Any]]:
        return [n for n in self.cluster()["nodes"] if n.get("status") in ("BOOTING", "READY", "RUNNING")]

    # -- the cloud's own view (fake_ec2.py) --

    def _ec2(self) -> Any:
        import importlib.util

        spec = importlib.util.spec_from_file_location("rb_fake_ec2", FAKE_EC2)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def instances(self) -> list[dict[str, Any]]:
        """Every instance the cloud shows now: ``{"id", "state", "launched_at", "name"}``."""
        ec2 = self._ec2()
        shutdown_s = float(ec2.script(str(self.state)).get("shutdown_s", 0) or 0)
        now = time.time()
        with ec2.locked(str(self.state)) as state:
            ec2.ensure_ids(state)
            return [{"id": n["id"], "state": ec2.cloud_state(n, now, shutdown_s),
                     "launched_at": float(n["launched_at"]), "name": n["name"]}
                    for n in state["nodes"] if ec2.cloud_state(n, now, shutdown_s) is not None]

    def not_terminated(self) -> list[dict[str, Any]]:
        return [i for i in self.instances() if i["state"] != "terminated"]

    def add_instance(self, *, launched_at: float, status: str = "ORPHAN", hidden: bool = False) -> str:
        """An instance the cloud holds and the cluster software does not list: a node launched for
        a sweep after its stop, or someone else's. Returns its id."""
        ec2 = self._ec2()
        instance = ec2.new_id()
        with ec2.locked(str(self.state)) as state:
            state["nodes"].append({"name": f"burla-node-{instance[-8:]}", "status": status,
                                   "booted_at": launched_at, "launched_at": launched_at,
                                   "id": instance, "hidden": hidden})
        return instance

    def reveal(self) -> None:
        """The instances the cloud did not show yet, shown from now on."""
        ec2 = self._ec2()
        with ec2.locked(str(self.state)) as state:
            for node in state["nodes"]:
                node["hidden"] = False

    def ec2_calls(self) -> list[list[str]]:
        return [c["argv"] for c in self.aws_calls() if c["argv"][:1] == ["ec2"]]

    def records(self) -> dict[str, dict[str, Any]]:
        folder = self.xdg / "poisson-prove" / "cloud"
        if not folder.is_dir():
            return {}
        return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))}

    def record(self) -> dict[str, Any] | None:
        found = self.records()
        return found.get(f"aws-{ACCOUNT}.json")

    def ledger(self, name: str = "ledger.jsonl") -> list[dict[str, Any]]:
        return self._lines(self.root / name)

    def runs(self) -> list[dict[str, Any]]:
        if not self.store.exists():
            return []
        done = self.run("runs", "--json")
        return list(json.loads(done.out)["runs"]) if done.code == 0 else []

    def manifest(self, run_id: str) -> dict[str, Any]:
        return json.loads((self.store / run_id / "manifest.json").read_text(encoding="utf-8"))

    def events(self, run_id: str) -> list[dict[str, Any]]:
        return self._lines(self.store / run_id / "events.jsonl")

    def start_foreign_head(self) -> int:
        """A coordinator for this account that Prove did not start: started as the software's own
        command would, recorded in the software's ``head.json``, with no record of Prove's."""
        project = f"aws-{ACCOUNT}"
        folder = self.state / "clusters" / project
        folder.mkdir(parents=True, exist_ok=True)
        proc = subprocess.Popen([sys.executable, "-I", str(HEAD_PROCESS), str(self.state), project],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        (folder / "head.json").write_text(json.dumps({
            "url": "http://127.0.0.1:5001", "head_pid": proc.pid, "subdomain": "foreign",
            "tls_port": 0, "project_id": project, "cloud": "aws", "logs_to_file": True,
            "private": False, "open_to_network": False, "cluster_name": "",
        }), encoding="utf-8")
        until = time.time() + 30
        while not (self.state / f"head-{proc.pid}.ready").exists():
            assert time.time() < until, "the foreign head did not start"
            time.sleep(0.02)
        self._foreign = proc
        return proc.pid

    def cleanup(self) -> None:
        for head in self.heads():
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(head["pid"], signal.SIGKILL)
        foreign = getattr(self, "_foreign", None)
        if foreign is not None:
            with contextlib.suppress(Exception):
                foreign.kill()
                foreign.wait(timeout=10)
        for entry in self._lines(self.state / "management.jsonl"):
            pid = entry.get("pid")
            if isinstance(pid, int) and pid != os.getpid():
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.kill(pid, signal.SIGKILL)


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return True
    return done == 0


def wait_for(predicate: Any, within: float, what: str) -> None:
    until = time.time() + within
    while not predicate():
        assert time.time() < until, f"timed out after {within} s waiting for {what}"
        time.sleep(0.05)


def secrets_in(text: str) -> list[str]:
    return [name for name, value in PLANTED.items() if value in text]


@contextlib.contextmanager
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool: Pool) -> Iterator[CloudWorld]:
    made = CloudWorld(tmp_path, monkeypatch, pool)
    try:
        yield made
    finally:
        made.cleanup()
