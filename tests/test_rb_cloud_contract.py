"""C3-K of 0.3.0, Remote backends: the contract with the cluster software at the pin, and N6.

Every name, argument, CLI verb and flag, envelope field, error code, settings field, status field
and ``head.json`` key the cloud backend uses, and that the fakes stand for, is checked against the
installed ``burla==1.8.4``'s own files (Remote Backends Spec §5 and §15 C3-K). The files are read
and parsed, never imported: no Burla code runs and no process starts. A pin move turns this file
red before anything else.

Each test checks the fake beside the real file it mirrors, so a fake that drifts from the pin is
caught here too. N6 (every row of Prove's AWS price table is a machine type and region the
software's catalogue accepts) reads the catalogue the same way.

Runs where the cloud extra is installed at the pin (the gate's ``backends`` job); anywhere else
each test is skipped with the reason.
"""

from __future__ import annotations

import ast
import importlib.metadata
from pathlib import Path
from typing import Any

import pytest

from rb_cloud_support import FIXTURES, PIN, TABLE_REGIONS, TYPES

FAKE = FIXTURES / "burla"


def _installed() -> importlib.metadata.Distribution | None:
    try:
        dist = importlib.metadata.distribution("burla")
    except importlib.metadata.PackageNotFoundError:
        return None
    return dist if dist.version == PIN else None


DIST = _installed()
pytestmark = pytest.mark.skipif(
    DIST is None,
    reason=f"C3-K reads the installed burla=={PIN}, which the cloud extra installs "
    '(pip install -e ".[cloud]"); it is not installed at the pin here',
)


def source(rel: str) -> ast.Module:
    assert DIST is not None
    path = Path(str(DIST.locate_file(rel)))
    assert path.is_file(), f"burla {PIN} has no {rel}"
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def text(rel: str) -> str:
    assert DIST is not None
    return Path(str(DIST.locate_file(rel))).read_text(encoding="utf-8")


def fake(rel: str) -> ast.Module:
    return ast.parse((FAKE / rel).read_text(encoding="utf-8"))


def functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def signature(fn: ast.FunctionDef) -> list[tuple[str, Any]]:
    args = fn.args
    positional = [*args.posonlyargs, *args.args]
    defaults: list[Any] = [None] * (len(positional) - len(args.defaults)) + [
        ast.unparse(d) for d in args.defaults
    ]
    out = [(a.arg, d) for a, d in zip(positional, defaults, strict=True)]
    out += [(a.arg, None if d is None else ast.unparse(d)) for a, d in zip(args.kwonlyargs, args.kw_defaults, strict=True)]
    return out


def assigned(tree: ast.Module, name: str) -> Any:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return node.value
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return node.value
    raise AssertionError(f"{name} is not assigned at module level")


def dict_keys(node: ast.AST) -> set[str]:
    assert isinstance(node, ast.Dict), ast.dump(node)[:200]
    return {k.value for k in node.keys if isinstance(k, ast.Constant)}


def strings(tree: ast.AST) -> set[str]:
    return {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


# ---------- the coordinator: start, find, stop ----------

HEAD_FUNCTIONS = ("ensure_local_head", "start_local_head_for_job", "running_head_url", "_head_state_dir",
                  "_pid_alive", "_recorded_head_pid", "_terminate_pid", "_stop_recorded_head")


@pytest.mark.parametrize("name", HEAD_FUNCTIONS)
def test_c3k_the_coordinators_functions_exist_with_the_fakes_arguments(name: str) -> None:
    real = functions(source("burla/_local_head.py"))
    mine = functions(fake("_local_head.py"))
    assert name in real, f"burla {PIN} has no _local_head.{name}"
    assert signature(real[name]) == signature(mine[name]), (signature(real[name]), signature(mine[name]))


def test_c3k_the_preferred_port_is_5001() -> None:
    assert ast.literal_eval(assigned(source("burla/_local_head.py"), "PREFERRED_HEAD_PORT")) == 5001


def test_c3k_head_json_carries_the_keys_the_fake_writes() -> None:
    def written(tree: ast.Module) -> set[str]:
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "head_state" for t in node.targets)
                    and isinstance(node.value, ast.Dict) and node.value.keys):
                return dict_keys(node.value)
        raise AssertionError("no head_state record written")

    real = written(source("burla/_local_head.py"))
    assert real == written(fake("_local_head.py")), real
    assert {"url", "head_pid", "project_id", "private"} <= real


@pytest.mark.parametrize("name", ["detect_cloud", "read_saved_cluster_token"])
def test_c3k_the_account_functions_exist_with_the_fakes_arguments(name: str) -> None:
    real = functions(source("burla/_auth.py"))
    assert name in real and signature(real[name]) == signature(functions(fake("_auth.py"))[name])


def test_c3k_state_root_and_local_head_error_are_where_the_fake_puts_them() -> None:
    tree = source("burla/_auth.py")
    assigned(tree, "STATE_ROOT")
    assert "LocalHeadError" in {n.name for n in tree.body if isinstance(n, ast.ClassDef)}


# ---------- the CLI ----------


def _cli_flags(tree: ast.Module) -> set[str]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            out |= {a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)}
    return out


def test_c3k_the_cli_has_the_flags_prove_passes() -> None:
    real = _cli_flags(source("burla/_cli.py"))
    used = {"--head", "--debug", "--image", "--machine-type", "--quantity", "--region", "--disk-gb",
            "--inactivity-timeout-seconds", "--max-vcpus"}
    assert used <= real, used - real
    assert used <= _cli_flags(fake("_cli.py")), used - _cli_flags(fake("_cli.py"))


def test_c3k_the_cli_verbs_and_their_routes() -> None:
    names = strings(source("burla/_cli.py"))
    for verb in ("cluster", "status", "start", "stop", "settings", "update", "show"):
        assert verb in names, verb
    for route in ("/v1/management/cluster", "/v1/management/settings"):
        assert route in names, route
    assert "cluster.status" in names and "settings.update" in names
    lifecycle = text("burla/_cli.py")
    assert 'path=f"/v1/management/cluster/{action}"' in lifecycle and 'command_name=f"cluster.{action}"' in lifecycle
    entry = [ep for ep in DIST.entry_points if ep.name == "burla"] if DIST else []
    assert [ep.value for ep in entry] == ["burla.__main__:main"], entry


def test_c3k_the_envelope_keys_and_the_error_codes() -> None:
    tree = source("burla/_cli.py")
    success = functions(tree)["_success"]
    (returned,) = [n.value for n in ast.walk(success) if isinstance(n, ast.Return)]
    assert dict_keys(returned) == {"schema_version", "ok", "command", "request_id", "data"}
    error_doc = [n for n in ast.walk(functions(tree)["_emit_error"]) if isinstance(n, ast.Dict)]
    assert dict_keys(error_doc[0]) == {"schema_version", "ok", "command", "request_id", "error"}
    client = source("burla/_management_client.py")
    codes = ast.literal_eval(assigned(client, "ERROR_EXIT_CODES"))
    assert codes == ast.literal_eval(assigned(fake("_cli.py"), "ERROR_EXIT_CODES")), codes
    assert {"PROVIDER_ERROR", "HEAD_UNREACHABLE", "INVALID_ARGUMENT", "TIMEOUT"} <= set(codes)
    as_dict = next(n for n in ast.walk(client) if isinstance(n, ast.FunctionDef) and n.name == "as_dict")
    (returned,) = [n.value for n in ast.walk(as_dict) if isinstance(n, ast.Return)]
    assert dict_keys(returned) == {"code", "message", "retryable", "details", "remediation"}
    assert '"schema_version": 1,' in text("burla/_cli.py")


def test_c3k_the_settings_fields_and_their_ranges() -> None:
    update = functions(source("burla/_cli.py"))["_settings_update"]
    body = next(n for n in ast.walk(update) if isinstance(n, ast.Dict))
    assert dict_keys(body) == {"image", "machine_type", "quantity", "region", "disk_gb",
                               "inactivity_timeout_seconds", "max_vcpus", "max_gpus"}
    catalog = text("main_service/providers/catalog.py")
    for bound in ('"quantity": {"minimum": 1, "maximum": 1000}', '"disk_gb": {"minimum": 10, "maximum": 2000}',
                  '"inactivity_timeout_seconds": {"minimum": 0, "maximum": 86400}',
                  '"max_vcpus": {"minimum": 0, "maximum": 100_000}'):
        assert bound in catalog, bound


def test_c3k_the_status_fields_and_values() -> None:
    management = source("main_service/endpoints/management.py")
    dto = next(n for n in management.body if isinstance(n, ast.FunctionDef) and n.name == "_cluster_dto")
    result = next(n.value for n in ast.walk(dto) if isinstance(n, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "result" for t in n.targets))
    assert dict_keys(result) == {"status", "head_mode", "desired_node_count", "node_counts", "vcpu_count",
                                 "memory_bytes", "active_job_count", "active_function_count"}
    assert {"off", "booting", "ready", "running"} <= strings(dto)
    fake_dto = functions(fake("_cluster.py"))["status_document"]
    returned = next(n.value for n in ast.walk(fake_dto) if isinstance(n, ast.Return))
    assert dict_keys(returned) == dict_keys(result)


def test_c3k_cluster_stop_deletes_booting_nodes_too() -> None:
    """§19: what "active" covers in the stop. The fake deletes booting nodes as the pin does."""
    management = source("main_service/endpoints/management.py")
    stop = next(n for n in management.body if isinstance(n, ast.FunctionDef) and n.name == "stop_cluster")
    assert {"BOOTING", "READY", "RUNNING"} <= strings(stop)
    lifecycle = source("main_service/endpoints/cluster_lifecycle.py")
    shutdown = next(n for n in lifecycle.body if isinstance(n, ast.FunctionDef) and n.name == "_shutdown_cluster")
    assert {"BOOTING", "READY", "RUNNING"} <= strings(shutdown)
    assert ast.literal_eval(assigned(fake("_cluster.py"), "LISTED")) == ("BOOTING", "READY", "RUNNING")


def test_c3k_the_routes_prove_never_calls_still_exist_where_it_avoids_them() -> None:
    """``POST /v1/settings`` (which removes authorised users outside private mode) is still the
    dashboard's; Prove's settings go through ``PATCH /v1/management/settings``."""
    assert '@router.post("/v1/settings")' in text("main_service/endpoints/settings.py")
    assert '"PATCH",\n        "/v1/management/settings"' in text("burla/_cli.py")


# ---------- the provider messages §7.4 maps ----------


def test_c3k_the_provider_texts_prove_reads() -> None:
    lifecycle = text("main_service/endpoints/cluster_lifecycle.py")
    assert 'f"Not signed in to {cloud_name}"' in lifecycle
    assert "Nodes cannot reach the head" in lifecycle
    assert "INSUFFICIENT_INSTANCE_CAPACITY" in text("main_service/providers/aws.py")
    node = {n.name for n in source("burla/_node.py").body if isinstance(n, ast.ClassDef)}
    assert {"NoNodes", "NoCompatibleNodes", "JobStalled"} <= node


def test_c3k_the_environment_switches() -> None:
    init = text("burla/__init__.py")
    assert 'os.environ.get("BURLA_PRIVATE") == "True"' in init
    assert '"DISABLE_BURLA_TELEMETRY"' in init and '"BURLA_CLOUD"' in init
    assert 'os.environ.get("BURLA_CLUSTER_DASHBOARD_URL")' in init


def test_c3k_the_job_call_keeps_its_arguments() -> None:
    real = functions(source("burla/_remote_parallel_map.py"))["remote_parallel_map"]
    mine = functions(fake("_remote_parallel_map.py"))["remote_parallel_map"]
    used = {"function_", "inputs", "func_cpu", "func_ram", "grow", "max_parallelism", "generator"}
    names = {a for a, _ in signature(real)}
    assert used <= names, used - names
    assert used <= {a for a, _ in signature(mine)}


# ---------- N6: the price table against the catalogue ----------


def test_n6_every_row_of_the_aws_table_is_in_the_softwares_catalogue() -> None:
    from poisson_prove import _prices_cloud

    catalog = source("main_service/providers/catalog.py")
    types = set(ast.literal_eval(assigned(catalog, "SETTINGS_MACHINE_TYPES"))["aws"])
    regions = set(ast.literal_eval(assigned(catalog, "SETTINGS_REGIONS"))["aws"])
    rows = _prices_cloud.rows("aws")
    assert rows, "Prove's AWS table is empty"
    for region, kind in rows:
        assert kind in types, kind
        assert region in regions, region
    assert set(TYPES) <= types and set(TABLE_REGIONS) <= regions
