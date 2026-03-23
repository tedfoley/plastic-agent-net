/**
 * Supabase Edge Function: run-episode
 *
 * Receives an episode_id, builds seed graph, runs the main loop
 * (dispatch waves → LLM-only verify → controller step), writes
 * state to Postgres each round.
 */

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import Anthropic from "https://esm.sh/@anthropic-ai/sdk@0.39.0";

import { AGENT_SCHEMAS } from "./schemas.ts";
import {
  DEFAULT_BUDGET,
  MODEL_MAP,
  TEMPLATE_CONFIGS,
  TIER_MAX_TOKENS,
  renderPersona,
} from "./templates.ts";
import {
  type ArtifactRow,
  type ControllerAction,
  type EdgeRow,
  type NodeRow,
  computeBranchScore,
  controllerStep,
} from "./controller.ts";

// ============================================================
// Helpers
// ============================================================

function newId(): string {
  return crypto.randomUUID().replace(/-/g, "").slice(0, 12);
}

/** Kahn's algorithm for topological waves. */
function topologicalWaves(nodes: NodeRow[], edges: EdgeRow[]): string[][] {
  const activeIds = new Set(
    nodes
      .filter((n) => n.status === "pending" || n.status === "running")
      .map((n) => n.id),
  );
  if (activeIds.size === 0) return [];

  const inDegree: Record<string, number> = {};
  const adj: Record<string, string[]> = {};
  for (const nid of activeIds) {
    inDegree[nid] = 0;
    adj[nid] = [];
  }
  for (const e of edges) {
    if (e.active && activeIds.has(e.source_node) && activeIds.has(e.target_node)) {
      adj[e.source_node].push(e.target_node);
      inDegree[e.target_node] = (inDegree[e.target_node] ?? 0) + 1;
    }
  }

  const waves: string[][] = [];
  const remaining = new Set(activeIds);

  while (remaining.size > 0) {
    const wave = [...remaining].filter((nid) => (inDegree[nid] ?? 0) === 0);
    if (wave.length === 0) {
      waves.push([...remaining]);
      break;
    }
    waves.push(wave);
    for (const nid of wave) {
      remaining.delete(nid);
      for (const succ of adj[nid] ?? []) {
        if (remaining.has(succ)) {
          inDegree[succ]--;
        }
      }
    }
  }

  return waves;
}

// ============================================================
// DB helpers
// ============================================================

interface DbContext {
  sb: ReturnType<typeof createClient>;
  episodeId: string;
}

async function loadNodes(ctx: DbContext): Promise<NodeRow[]> {
  const { data } = await ctx.sb
    .from("nodes")
    .select("*")
    .eq("episode_id", ctx.episodeId);
  return (data ?? []) as NodeRow[];
}

async function loadEdges(ctx: DbContext): Promise<EdgeRow[]> {
  const { data } = await ctx.sb
    .from("edges")
    .select("*")
    .eq("episode_id", ctx.episodeId);
  return (data ?? []) as EdgeRow[];
}

async function loadArtifacts(ctx: DbContext): Promise<ArtifactRow[]> {
  const { data } = await ctx.sb
    .from("artifacts")
    .select("*")
    .eq("episode_id", ctx.episodeId);
  return (data ?? []) as ArtifactRow[];
}

async function upsertNode(ctx: DbContext, node: NodeRow): Promise<void> {
  await ctx.sb.from("nodes").upsert({
    id: node.id,
    episode_id: ctx.episodeId,
    template: node.template,
    persona: node.persona,
    model_tier: node.model_tier,
    branch_id: node.branch_id,
    status: node.status,
    round_created: node.round_created,
    rounds_active: node.rounds_active,
    tokens_used: node.tokens_used,
    contribution_score: node.contribution_score,
    metadata: node.metadata,
  });
}

async function upsertEdge(ctx: DbContext, edge: {
  source_node: string;
  target_node: string;
  weight: number;
  active: boolean;
}): Promise<void> {
  await ctx.sb.from("edges").upsert(
    {
      episode_id: ctx.episodeId,
      source_node: edge.source_node,
      target_node: edge.target_node,
      weight: edge.weight,
      message_types: [],
      active: edge.active,
    },
    { onConflict: "episode_id,source_node,target_node" },
  );
}

async function insertArtifact(
  ctx: DbContext,
  artifact: {
    id: string;
    artifact_type: string;
    producer_node: string;
    branch_id: string;
    round_produced: number;
    content: Record<string, unknown>;
    summary: string;
  },
): Promise<void> {
  await ctx.sb.from("artifacts").upsert({
    id: artifact.id,
    episode_id: ctx.episodeId,
    ...artifact,
  });
}

async function insertEvent(
  ctx: DbContext,
  eventType: string,
  round: number | null,
  payload: Record<string, unknown>,
): Promise<void> {
  await ctx.sb.from("events").insert({
    episode_id: ctx.episodeId,
    event_type: eventType,
    round,
    payload,
  });
}

async function insertControllerAction(
  ctx: DbContext,
  action: ControllerAction,
  round: number,
): Promise<void> {
  await ctx.sb.from("controller_actions").insert({
    episode_id: ctx.episodeId,
    action_type: action.actionType,
    target_node: action.targetNode,
    payload: action.payload,
    reason: action.reason,
    round,
  });
}

// ============================================================
// Seed Graph
// ============================================================

async function buildSeedGraph(ctx: DbContext): Promise<void> {
  const seedTemplates = ["planner", "repo_mapper", "coder", "verifier_coordinator"];
  const nodeIds: string[] = [];

  for (const tmpl of seedTemplates) {
    const cfg = TEMPLATE_CONFIGS[tmpl];
    const nodeId = newId();
    nodeIds.push(nodeId);

    await upsertNode(ctx, {
      id: nodeId,
      template: tmpl,
      persona: cfg.personaPrior,
      model_tier: cfg.defaultModelTier,
      branch_id: "main",
      status: "pending",
      round_created: 0,
      rounds_active: 0,
      tokens_used: 0,
      contribution_score: 0,
      metadata: {},
    });
  }

  // Edges: planner→coder, repo_mapper→coder, coder→verifier
  const edgePairs = [
    [nodeIds[0], nodeIds[2]], // planner→coder
    [nodeIds[1], nodeIds[2]], // repo_mapper→coder
    [nodeIds[2], nodeIds[3]], // coder→verifier
  ];

  for (const [src, tgt] of edgePairs) {
    await upsertEdge(ctx, {
      source_node: src,
      target_node: tgt,
      weight: 1.0,
      active: true,
    });
  }
}

// ============================================================
// LLM Dispatch
// ============================================================

async function runNode(
  anthropic: InstanceType<typeof Anthropic>,
  ctx: DbContext,
  node: NodeRow,
  artifacts: ArtifactRow[],
  taskSummary: string,
  currentRound: number,
): Promise<ArtifactRow | null> {
  const cfg = TEMPLATE_CONFIGS[node.template];
  if (!cfg) return null;

  // Build system prompt
  const personaText = renderPersona(cfg.personaPrior);
  const systemPrompt = `${cfg.instruction}\n\n${personaText}`;

  // Build context from artifacts on same branch
  const branchArtifacts = artifacts
    .filter((a) => a.branch_id === node.branch_id)
    .slice(-10);

  const contextText = branchArtifacts.length > 0
    ? "Previous artifacts on this branch:\n" +
      branchArtifacts.map((a) => `- [${a.artifact_type}] ${a.summary}`).join("\n")
    : "No previous artifacts.";

  const userMessage = `Task: ${taskSummary}\n\nRound: ${currentRound}\n\n${contextText}\n\nProduce your output as JSON matching the expected schema.`;

  const model = MODEL_MAP[node.model_tier] ?? MODEL_MAP.haiku;
  const maxTokens = TIER_MAX_TOKENS[node.model_tier] ?? 4096;

  // Mark running
  node.status = "running";
  await upsertNode(ctx, node);

  try {
    const response = await anthropic.messages.create({
      model,
      max_tokens: maxTokens,
      system: systemPrompt,
      messages: [{ role: "user", content: userMessage }],
    });

    const text = response.content
      .filter((b: any) => b.type === "text")
      .map((b: any) => b.text)
      .join("");

    // Parse JSON from response
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(text);
    } catch {
      // Try to extract JSON from text
      const match = text.match(/\{[\s\S]*\}/);
      if (match) {
        try {
          parsed = JSON.parse(match[0]);
        } catch {
          parsed = { raw: text };
        }
      } else {
        parsed = { raw: text };
      }
    }

    // Record tokens
    const totalTokens = (response.usage?.input_tokens ?? 0) + (response.usage?.output_tokens ?? 0);
    node.tokens_used += totalTokens;
    node.status = "done";
    node.rounds_active += 1;
    await upsertNode(ctx, node);

    // Map template to artifact type
    const typeMap: Record<string, string> = {
      planner: "plan",
      repo_mapper: "repo_map",
      coder: "patch",
      verifier_coordinator: "verification",
      debugger: "debug_report",
      test_writer: "test_code",
      skeptic_reviewer: "review",
      security_reviewer: "review",
      regression_reviewer: "review",
      synthesizer: "synthesis",
    };

    const artifactType = typeMap[node.template] ?? "patch";
    const artifact: ArtifactRow = {
      id: newId(),
      artifact_type: artifactType,
      producer_node: node.id,
      branch_id: node.branch_id,
      round_produced: currentRound,
      content: parsed,
      summary: (parsed as any).strategy ??
        (parsed as any).changes_summary ??
        (parsed as any).root_cause ??
        `${artifactType} by ${node.template}`,
    };

    await insertArtifact(ctx, artifact);
    return artifact;
  } catch (err) {
    console.error(`Error running node ${node.id}:`, err);
    node.status = "done";
    node.rounds_active += 1;
    await upsertNode(ctx, node);
    return null;
  }
}

// ============================================================
// Apply Controller Actions
// ============================================================

async function applyActions(
  ctx: DbContext,
  actions: ControllerAction[],
  nodes: NodeRow[],
  edges: EdgeRow[],
  currentRound: number,
): Promise<void> {
  for (const action of actions) {
    await insertControllerAction(ctx, action, currentRound);

    if (action.actionType === "spawn") {
      const tmpl = (action.payload.template as string) ?? "coder";
      const branchId = (action.payload.branch_id as string) ?? "main";
      const cfg = TEMPLATE_CONFIGS[tmpl];
      if (!cfg) continue;

      const nodeId = newId();
      await upsertNode(ctx, {
        id: nodeId,
        template: tmpl,
        persona: cfg.personaPrior,
        model_tier: cfg.defaultModelTier,
        branch_id: branchId,
        status: "pending",
        round_created: currentRound,
        rounds_active: 0,
        tokens_used: 0,
        contribution_score: 0,
        metadata: {},
      });

      // Connect to existing nodes on same branch
      for (const existing of nodes.filter((n) => n.branch_id === branchId && n.status !== "pruned")) {
        if (existing.id !== nodeId) {
          await upsertEdge(ctx, {
            source_node: existing.id,
            target_node: nodeId,
            weight: 1.0,
            active: true,
          });
        }
      }
    } else if (action.actionType === "prune") {
      await ctx.sb.from("nodes").update({ status: "pruned" }).eq("id", action.targetNode);
      await ctx.sb
        .from("edges")
        .update({ active: false })
        .eq("episode_id", ctx.episodeId)
        .or(`source_node.eq.${action.targetNode},target_node.eq.${action.targetNode}`);
    } else if (action.actionType === "merge") {
      const sourceBranch = action.payload.source_branch as string;
      const targetBranch = action.payload.target_branch as string;
      await ctx.sb
        .from("nodes")
        .update({ status: "merged", branch_id: targetBranch })
        .eq("episode_id", ctx.episodeId)
        .eq("branch_id", sourceBranch);
    } else if (action.actionType === "escalate") {
      const newTier = (action.payload.new_tier as string) ?? "sonnet";
      await ctx.sb.from("nodes").update({ model_tier: newTier }).eq("id", action.targetNode);
    }
  }
}

// ============================================================
// Main Handler
// ============================================================

Deno.serve(async (req) => {
  try {
    const { episode_id } = await req.json();
    if (!episode_id) {
      return new Response(JSON.stringify({ error: "episode_id required" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Init clients
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const anthropicKey = Deno.env.get("ANTHROPIC_API_KEY")!;

    const sb = createClient(supabaseUrl, supabaseKey);
    const anthropic = new Anthropic({ apiKey: anthropicKey });
    const ctx: DbContext = { sb, episodeId: episode_id };

    // Load episode
    const { data: episodeData } = await sb
      .from("episodes")
      .select("*")
      .eq("id", episode_id)
      .single();

    if (!episodeData) {
      return new Response(JSON.stringify({ error: "episode not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    const task = episodeData.task;
    const budgetConfig = episodeData.budget_config ?? DEFAULT_BUDGET;
    const maxRounds = budgetConfig.max_rounds ?? DEFAULT_BUDGET.max_rounds;
    const maxNodes = budgetConfig.max_nodes ?? DEFAULT_BUDGET.max_nodes;
    const maxBranches = budgetConfig.max_branches ?? DEFAULT_BUDGET.max_branches;
    const maxTotalTokens = budgetConfig.max_total_tokens ?? DEFAULT_BUDGET.max_total_tokens;

    // Update status to running
    await sb.from("episodes").update({ status: "running" }).eq("id", episode_id);
    await insertEvent(ctx, "episode_start", 0, { task });

    // Build seed graph
    await buildSeedGraph(ctx);

    let totalTokens = 0;
    let terminatedReason = "budget_rounds";

    // Main loop
    for (let round = 0; round < maxRounds; round++) {
      await insertEvent(ctx, "round_start", round, {});

      let nodes = await loadNodes(ctx);
      let edges = await loadEdges(ctx);
      let artifacts = await loadArtifacts(ctx);

      // Dispatch in topological waves
      const waves = topologicalWaves(nodes, edges);
      let nodesRun = 0;

      for (const wave of waves) {
        // Run all nodes in wave in parallel
        const results = await Promise.all(
          wave
            .map((nid) => nodes.find((n) => n.id === nid))
            .filter((n): n is NodeRow => n !== undefined && n.status === "pending")
            .map((n) => runNode(anthropic, ctx, n, artifacts, task, round)),
        );

        nodesRun += results.filter((r) => r !== null).length;

        // Refresh artifacts after each wave
        artifacts = await loadArtifacts(ctx);
      }

      await insertEvent(ctx, "round_dispatched", round, { nodes_run: nodesRun });

      // Reload state after dispatch
      nodes = await loadNodes(ctx);
      edges = await loadEdges(ctx);
      artifacts = await loadArtifacts(ctx);

      // Compute total tokens
      totalTokens = nodes.reduce((sum, n) => sum + n.tokens_used, 0);

      // Budget check
      if (totalTokens >= maxTotalTokens) {
        terminatedReason = "budget_tokens";
        break;
      }

      // Controller step
      const budgetPressure = totalTokens / maxTotalTokens;
      const ctrlState = controllerStep(
        nodes, edges, artifacts, round, budgetPressure, maxNodes, maxBranches,
      );

      await insertEvent(ctx, "controller_step", round, {
        actions: ctrlState.actionsTaken.length,
        branch_scores: ctrlState.branchScores,
      });

      // Apply actions
      await applyActions(ctx, ctrlState.actionsTaken, nodes, edges, round);

      // Record controller actions
      for (const action of ctrlState.actionsTaken) {
        await insertControllerAction(ctx, action, round);
      }

      // Update episode progress
      await sb.from("episodes").update({
        rounds_completed: round + 1,
        tokens_used: totalTokens,
        branch_scores: ctrlState.branchScores,
      }).eq("id", episode_id);

      // Check convergence
      const scores = Object.values(ctrlState.branchScores);
      if (scores.length > 0) {
        const bestScore = Math.max(...scores);
        if (bestScore >= 0.9 && ctrlState.actionsTaken.length === 0) {
          terminatedReason = "converged";
          break;
        }
      }

      // Reset done nodes to pending for next round
      await sb
        .from("nodes")
        .update({ status: "pending" })
        .eq("episode_id", episode_id)
        .eq("status", "done");
    }

    // Finalize
    await sb.from("episodes").update({
      status: "completed",
      terminated_reason: terminatedReason,
      tokens_used: totalTokens,
    }).eq("id", episode_id);

    await insertEvent(ctx, "episode_complete", null, {
      terminated_reason: terminatedReason,
      tokens_used: totalTokens,
    });

    return new Response(
      JSON.stringify({
        success: true,
        episode_id,
        terminated_reason: terminatedReason,
        tokens_used: totalTokens,
      }),
      { headers: { "Content-Type": "application/json" } },
    );
  } catch (err) {
    console.error("Edge function error:", err);

    // Try to mark episode as failed
    try {
      const { episode_id } = await req.clone().json();
      if (episode_id) {
        const sb = createClient(
          Deno.env.get("SUPABASE_URL")!,
          Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
        );
        await sb.from("episodes").update({
          status: "failed",
          terminated_reason: `error: ${err}`,
        }).eq("id", episode_id);
      }
    } catch { /* ignore cleanup errors */ }

    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }
});
