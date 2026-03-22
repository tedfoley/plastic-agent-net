"""Tests for ArtifactStore."""

from plastic_agent_net.core.models import Artifact, ArtifactType
from plastic_agent_net.memory.artifact_store import ArtifactStore


def test_put_and_get():
    store = ArtifactStore()
    a = Artifact(artifact_type=ArtifactType.PATCH, producer_node="n1", branch_id="main")
    aid = store.put(a)
    assert store.get(aid) is a


def test_get_nonexistent():
    store = ArtifactStore()
    assert store.get("nonexistent") is None


def test_list_by_branch():
    store = ArtifactStore()
    store.put(Artifact(artifact_type=ArtifactType.PATCH, branch_id="main"))
    store.put(Artifact(artifact_type=ArtifactType.PATCH, branch_id="feat"))
    store.put(Artifact(artifact_type=ArtifactType.PLAN, branch_id="main"))

    main = store.list_by_branch("main")
    assert len(main) == 2
    feat = store.list_by_branch("feat")
    assert len(feat) == 1


def test_list_by_type():
    store = ArtifactStore()
    store.put(Artifact(artifact_type=ArtifactType.PATCH))
    store.put(Artifact(artifact_type=ArtifactType.PATCH))
    store.put(Artifact(artifact_type=ArtifactType.PLAN))

    patches = store.list_by_type(ArtifactType.PATCH)
    assert len(patches) == 2


def test_list_by_producer():
    store = ArtifactStore()
    store.put(Artifact(producer_node="n1"))
    store.put(Artifact(producer_node="n2"))
    store.put(Artifact(producer_node="n1"))

    n1_arts = store.list_by_producer("n1")
    assert len(n1_arts) == 2


def test_summarize_for_node():
    store = ArtifactStore()
    store.put(Artifact(
        artifact_type=ArtifactType.PATCH,
        producer_node="n1",
        branch_id="main",
        summary="Fixed bug",
    ))
    store.put(Artifact(
        artifact_type=ArtifactType.PLAN,
        producer_node="n2",
        branch_id="main",
        summary="Task plan",
    ))

    summaries = store.summarize_for_node("n1", "main")
    assert len(summaries) == 2
    assert all("summary" in s for s in summaries)


def test_list_all():
    store = ArtifactStore()
    store.put(Artifact())
    store.put(Artifact())
    assert len(store.list_all()) == 2
