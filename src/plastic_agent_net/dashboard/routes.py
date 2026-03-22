"""REST API routes for the dashboard."""

from __future__ import annotations

from fastapi import APIRouter

from plastic_agent_net.dashboard.server import get_current_episode

router = APIRouter()


@router.get("/graph")
async def get_graph():
    """Get current graph state."""
    episode = get_current_episode()
    if episode is None:
        return {"nodes": [], "edges": [], "message": "No active episode"}

    graph = episode.graph
    nodes = [
        {
            "id": n.node_id,
            "template": n.template.value,
            "branch": n.branch_id,
            "status": n.status.value,
            "model_tier": n.model_tier.value,
            "tokens_used": n.tokens_used,
            "contribution": n.contribution_score,
            "rounds_active": n.rounds_active,
        }
        for n in graph.all_nodes()
    ]
    edges = [
        {
            "source": e.source,
            "target": e.target,
            "weight": e.weight,
            "active": e.active,
        }
        for e in graph.all_edges()
    ]
    return {"nodes": nodes, "edges": edges}


@router.get("/artifacts")
async def get_artifacts():
    """Get all artifacts."""
    episode = get_current_episode()
    if episode is None:
        return {"artifacts": []}

    artifacts = episode.artifact_store.list_all()
    return {
        "artifacts": [
            {
                "id": a.artifact_id,
                "type": a.artifact_type.value,
                "producer": a.producer_node,
                "branch": a.branch_id,
                "round": a.round_produced,
                "summary": a.summary,
            }
            for a in artifacts
        ]
    }


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str):
    """Get a specific artifact with full content."""
    episode = get_current_episode()
    if episode is None:
        return {"error": "No active episode"}

    artifact = episode.artifact_store.get(artifact_id)
    if artifact is None:
        return {"error": "Artifact not found"}

    return {
        "id": artifact.artifact_id,
        "type": artifact.artifact_type.value,
        "producer": artifact.producer_node,
        "branch": artifact.branch_id,
        "round": artifact.round_produced,
        "summary": artifact.summary,
        "content": artifact.content,
    }


@router.get("/budget")
async def get_budget():
    """Get current budget usage."""
    episode = get_current_episode()
    if episode is None:
        return {"usage": {}, "config": {}}

    b = episode.budget
    return {
        "usage": {
            "total_tokens": b.usage.total_tokens,
            "rounds_completed": b.usage.rounds_completed,
            "active_nodes": b.usage.active_nodes,
            "active_edges": b.usage.active_edges,
            "active_branches": b.usage.active_branches,
        },
        "config": {
            "max_total_tokens": b.config.max_total_tokens,
            "max_rounds": b.config.max_rounds,
            "max_nodes": b.config.max_nodes,
        },
        "pressure": b.pressure(),
    }


@router.get("/status")
async def get_status():
    """Get overall episode status."""
    episode = get_current_episode()
    if episode is None:
        return {"status": "idle", "message": "No active episode"}
    return {
        "status": "running",
        "round": episode.budget.usage.rounds_completed,
        "nodes": episode.graph.node_count(),
        "branches": len(episode.graph.branch_ids()),
    }
