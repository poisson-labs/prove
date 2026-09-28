"""The exceptions ``remote_parallel_map`` can end a call with, at 1.8.1's import path.

``_node.py:83-184`` defines them; the constructors below take what 1.8.1's take, so a message
reads the way the real one does. Each is raised by the fake only when a test's script asks.
"""

from __future__ import annotations

from typing import Any


class NoNodes(Exception):  # _node.py:83
    pass


class AllNodesBusy(Exception):  # _node.py:87-91
    def __init__(self, message: str = "All nodes are busy, please try again later.") -> None:
        super().__init__(message)


class NoCompatibleNodes(Exception):  # _node.py:94-123, the fallback branch
    def __init__(self, detail: dict[str, Any] | None = None) -> None:
        message = (
            "No compatible nodes available. Are the machines in your cluster large enough "
            "to support your `func_cpu` and `func_ram` arguments?"
        )
        super().__init__(message)


class _FakeNode:
    def __init__(self, instance_name: str) -> None:
        self.instance_name = instance_name


class NodeDisconnected(Exception):  # _node.py:136-139
    def __init__(self, node: Any, message: str | None = None) -> None:
        self.node = node
        super().__init__(message or f"Node {node.instance_name} failed during job.")


class NodesFailedToBoot(Exception):  # _node.py:142-147
    def __init__(self, nodes: list[Any]) -> None:
        node_word = "node" if len(nodes) == 1 else "nodes"
        message = f"\n\nBurla tried to boot {len(nodes)} {node_word} to complete this request, "
        message += "but all of them failed to boot.\n"
        super().__init__(message)


class JobCanceled(Exception):  # _node.py:161
    pass


class JobStalled(Exception):  # _node.py:165
    pass


class ClusterRestarted(Exception):  # _node.py:169-175
    def __init__(self) -> None:
        super().__init__(
            "\n\nThe cluster was restarted. Your job was ended because the nodes it was running "
            "on were destroyed.\n"
        )


class ClusterShutdown(Exception):  # _node.py:178-184
    def __init__(self) -> None:
        super().__init__(
            "\n\nThe cluster was shut down. Your job was ended because the nodes it was running "
            "on were destroyed.\n"
        )


class DetachRequiresDeployedCluster(Exception):  # _node.py:192-201
    def __init__(self) -> None:
        super().__init__("\n\nBackground jobs (detach=True) require a deployed Burla cluster.\n")
