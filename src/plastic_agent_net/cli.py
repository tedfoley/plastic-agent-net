"""Click CLI entry point for PlasticAgentNet."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click

from plastic_agent_net import __version__


@click.group()
@click.version_option(version=__version__, prog_name="pan")
def cli() -> None:
    """PlasticAgentNet: dynamically rewiring graph of LLM-backed coding agents."""
    pass


@cli.command()
@click.argument("task")
@click.option("--repo", "-r", type=click.Path(exists=True), default=".", help="Path to the target repository")
@click.option("--budget-tokens", type=int, default=500_000, help="Max total tokens")
@click.option("--budget-rounds", type=int, default=20, help="Max rounds")
@click.option("--budget-time", type=float, default=600.0, help="Max wall-clock seconds")
@click.option("--log", "-l", type=click.Path(), default=None, help="JSONL log file path")
@click.option("--api-key", envvar="ANTHROPIC_API_KEY", help="Anthropic API key")
@click.option("--supabase", "use_supabase", is_flag=True, default=False, help="Persist to Supabase")
def run(task: str, repo: str, budget_tokens: int, budget_rounds: int, budget_time: float, log: str | None, api_key: str | None, use_supabase: bool) -> None:
    """Run a coding task on a repository."""
    asyncio.run(_run_episode(task, repo, budget_tokens, budget_rounds, budget_time, log, api_key, use_supabase))


async def _run_episode(
    task: str,
    repo: str,
    budget_tokens: int,
    budget_rounds: int,
    budget_time: float,
    log_path: str | None,
    api_key: str | None,
    use_supabase: bool = False,
) -> None:
    from plastic_agent_net.core.models import BudgetConfig
    from plastic_agent_net.eval.logging import EventLogger, make_event_callback
    from plastic_agent_net.llm.client import AnthropicClient
    from plastic_agent_net.runtime.episode import Episode

    budget = BudgetConfig(
        max_total_tokens=budget_tokens,
        max_rounds=budget_rounds,
        max_wall_seconds=budget_time,
    )

    llm = AnthropicClient(api_key=api_key)
    event_cb = None
    event_logger = None
    supabase_repo = None

    if log_path:
        event_logger = EventLogger(log_path)
        event_cb = make_event_callback(event_logger)

    if use_supabase:
        from plastic_agent_net.db.client import get_supabase_client
        from plastic_agent_net.db.repository import SupabaseRepository
        sb = get_supabase_client()
        supabase_repo = SupabaseRepository(sb)
        click.echo("Supabase persistence enabled")

    def _print_and_log(event: dict) -> None:
        etype = event.get("event", "")
        if etype == "round_start":
            click.echo(f"  Round {event.get('round', '?')}...")
        elif etype == "verification":
            score = event.get("score", 0)
            branch = event.get("branch", "?")
            click.echo(f"    [{branch}] score={score:.2f}")
        elif etype == "controller_step":
            actions = event.get("actions", 0)
            if actions:
                click.echo(f"    Controller: {actions} action(s)")
        elif etype == "episode_complete":
            click.echo("  Done.")

        if event_cb:
            event_cb(event)

    episode = Episode(
        llm=llm,
        repo_path=str(Path(repo).resolve()),
        budget_config=budget,
        event_callback=_print_and_log,
        supabase_repo=supabase_repo,
    )

    click.echo(f"PlasticAgentNet v{__version__}")
    click.echo(f"Task: {task}")
    click.echo(f"Repo: {Path(repo).resolve()}")
    click.echo("Running episode...")

    result = await episode.run(task)

    click.echo(f"\nCompleted in {result.rounds_completed} rounds ({result.tokens_used} tokens)")
    click.echo(f"Termination: {result.terminated_reason}")

    if result.branch_scores:
        click.echo("\nBranch scores:")
        for bid, score in sorted(result.branch_scores.items(), key=lambda x: -x[1]):
            click.echo(f"  {bid}: {score:.3f}")

    if result.final_artifacts:
        click.echo(f"\n{len(result.final_artifacts)} artifact(s) produced")
        patches = [a for a in result.final_artifacts if a["type"] == "patch"]
        if patches:
            click.echo("\nFinal patches:")
            for p in patches:
                click.echo(f"  Branch '{p['branch']}': {p['summary']}")

    if log_path:
        click.echo(f"\nLog written to: {log_path}")

    if event_logger:
        event_logger.close()
    await llm.close()


@cli.command()
@click.argument("log_file", type=click.Path(exists=True))
@click.option("--round", "-r", "target_round", type=int, default=None, help="Show state at specific round")
def replay(log_file: str, target_round: int | None) -> None:
    """Replay an episode from a JSONL log file."""
    from plastic_agent_net.eval.replay import EpisodeReplay

    ep = EpisodeReplay(log_file)

    if target_round is not None:
        state = ep.state_at_round(target_round)
        click.echo(f"State at round {target_round}:")
        click.echo(f"  Nodes run: {state.nodes_run}")
        click.echo(f"  Actions: {state.total_actions}")
        click.echo(f"  Branch scores: {state.branch_scores}")
    else:
        summary = ep.summary()
        click.echo("Episode summary:")
        for k, v in summary.items():
            click.echo(f"  {k}: {v}")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Dashboard host")
@click.option("--port", default=8420, type=int, help="Dashboard port")
def dashboard(host: str, port: int) -> None:
    """Launch the web dashboard."""
    import uvicorn

    from plastic_agent_net.dashboard.server import create_app

    app = create_app()
    click.echo(f"Dashboard at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


@cli.command()
@click.option("--limit", "-n", type=int, default=20, help="Number of episodes to show")
def episodes(limit: int) -> None:
    """List recent episodes from Supabase."""
    from plastic_agent_net.db.client import get_supabase_client
    from plastic_agent_net.db.repository import SupabaseRepository

    sb = get_supabase_client()
    repo = SupabaseRepository(sb)
    rows = repo.list_episodes(limit=limit)

    if not rows:
        click.echo("No episodes found.")
        return

    click.echo(f"{'ID':<38} {'Status':<12} {'Rounds':<8} {'Task'}")
    click.echo("-" * 90)
    for ep in rows:
        eid = ep["id"][:36]
        status = ep.get("status", "?")
        rounds = ep.get("rounds_completed", 0)
        task = ep.get("task", "")[:40]
        click.echo(f"{eid:<38} {status:<12} {rounds:<8} {task}")


if __name__ == "__main__":
    cli()
