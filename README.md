# PlasticAgentNet

Dynamically rewiring, persona-conditioned graph of LLM-backed coding agents. The system treats graph structure as adaptive computation: nodes spawn, prune, merge, and escalate based on execution feedback and budget constraints.

## Architecture

- **Agent Graph**: Directed graph of specialized LLM agents (planner, coder, reviewer, debugger, etc.) connected by typed message edges
- **Plasticity Controller**: Heuristic rules that dynamically restructure the graph — spawning agents on uncertainty, pruning low-contribution nodes, merging converged branches, and escalating to stronger models on failure
- **Real Verification**: Patches are applied to isolated workspaces and verified via build, test, lint, and security scan
- **Budget Enforcement**: Hard limits on tokens, rounds, nodes, edges, branches, and wall-clock time
- **Persona Conditioning**: Each agent has a persona vector (caution, verbosity, creativity, skepticism) that shapes its prompts
- **Model Tiers**: Haiku for cheap work, Sonnet for coding/planning, Opus for final synthesis and escalation

## Install

```bash
pip install -e ".[dev]"
```

## Usage

### Run a coding task
```bash
pan run "Fix the typo in utils.py" --repo /path/to/repo
pan run "Add input validation to the login handler" --repo . --log trace.jsonl
```

### Replay a logged episode
```bash
pan replay trace.jsonl
pan replay trace.jsonl --round 5
```

### Launch the dashboard
```bash
pan dashboard
# Open http://localhost:8420
```

## Configuration

Set `ANTHROPIC_API_KEY` in your environment or pass `--api-key`.

Budget defaults:
- 500K tokens, 20 rounds, 10 min wall-clock
- Max 15 nodes, 40 edges, 4 branches

Override via CLI flags: `--budget-tokens`, `--budget-rounds`, `--budget-time`.

## Project Structure

```
src/plastic_agent_net/
├── cli.py              # Click CLI
├── config/             # Budget defaults, model configs, agent templates
├── core/               # Data models, graph, message bus, budgets
├── memory/             # Artifact store, scoped memory manager
├── agents/             # Agent implementations (planner, coder, reviewer, etc.)
├── prompts/            # Prompt renderer and output JSON schemas
├── control/            # Plasticity controller, spawn/prune/merge rules, scoring
├── tools/              # Workspace, repo search, patch, build, test, lint, security
├── runtime/            # Dispatcher, episode lifecycle, verifier, task encoder
├── eval/               # JSONL logging and episode replay
├── llm/                # Async Anthropic client wrapper
└── dashboard/          # FastAPI + SSE + D3.js web UI
```

## Testing

```bash
python -m pytest tests/ -v
```

## Agent Types

| Agent | Role | Default Model |
|-------|------|--------------|
| Planner | Task decomposition and strategy | Sonnet |
| RepoMapper | Repository structure analysis | Haiku |
| Coder | Patch generation | Sonnet |
| VerifierCoordinator | Build/test/lint orchestration | Haiku |
| Debugger | Root-cause analysis | Sonnet |
| TestWriter | Test generation | Haiku |
| SkepticReviewer | Adversarial code review | Haiku |
| SecurityReviewer | Security vulnerability analysis | Haiku |
| RegressionReviewer | Regression risk assessment | Haiku |
| Synthesizer | Final patch synthesis | Sonnet |
