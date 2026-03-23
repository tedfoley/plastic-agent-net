/**
 * Port of control/ modules: scoring, spawn/prune/merge/escalate rules.
 */

import {
  ESCALATION_FAILURE_COUNT,
  MERGE_SIMILARITY_THRESHOLD,
  PRUNE_CONTRIBUTION_THRESHOLD,
  SCORING_WEIGHTS,
  TEMPLATE_CONFIGS,
} from "./templates.ts";

// ============================================================
// Types
// ============================================================

export interface NodeRow {
  id: string;
  template: string;
  branch_id: string;
  status: string;
  round_created: number;
  rounds_active: number;
  tokens_used: number;
  contribution_score: number;
  model_tier: string;
  persona: Record<string, number>;
  metadata: Record<string, unknown>;
}

export interface EdgeRow {
  source_node: string;
  target_node: string;
  weight: number;
  active: boolean;
}

export interface ArtifactRow {
  id: string;
  artifact_type: string;
  producer_node: string;
  branch_id: string;
  round_produced: number;
  content: Record<string, unknown>;
  summary: string;
}

export interface ControllerAction {
  actionType: string;
  targetNode: string;
  payload: Record<string, unknown>;
  reason: string;
}

export interface ControllerState {
  round: number;
  actionsTaken: ControllerAction[];
  branchScores: Record<string, number>;
  nodeContributions: Record<string, number>;
}

// ============================================================
// Scoring
// ============================================================

export function computeNodeContribution(
  node: NodeRow,
  edges: EdgeRow[],
  allNodes: NodeRow[],
  artifacts: ArtifactRow[],
  currentRound: number,
): number {
  const w = SCORING_WEIGHTS;
  const nodeArtifacts = artifacts.filter((a) => a.producer_node === node.id);
  if (nodeArtifacts.length === 0) return 0;

  let score = 0;

  // Novelty
  const typesProduced = new Set(nodeArtifacts.map((a) => a.artifact_type));
  score += w.novelty * Math.min(1.0, typesProduced.size / 3);

  // Verification delta
  const branchVerifs = artifacts
    .filter((a) => a.artifact_type === "verification" && a.branch_id === node.branch_id)
    .sort((a, b) => a.round_produced - b.round_produced);

  if (branchVerifs.length >= 2) {
    const prev = (branchVerifs[branchVerifs.length - 2].content as any).overall_score ?? 0;
    const curr = (branchVerifs[branchVerifs.length - 1].content as any).overall_score ?? 0;
    score += w.verification_delta * Math.max(0, curr - prev);
  } else if (branchVerifs.length === 1) {
    score += w.verification_delta * ((branchVerifs[0].content as any).overall_score ?? 0);
  }

  // Peer agreement
  const successors = edges
    .filter((e) => e.source_node === node.id && e.active)
    .map((e) => e.target_node);
  if (successors.length > 0) {
    const activeSuccessors = successors.filter((s) => {
      const n = allNodes.find((nn) => nn.id === s);
      return n && (n.status === "running" || n.status === "done");
    }).length;
    score += w.peer_agreement * Math.min(1.0, activeSuccessors / Math.max(1, successors.length));
  }

  // Recency
  const age = currentRound - node.round_created;
  score += w.recency * Math.max(0, 1.0 - age / 10);

  return Math.min(1.0, score);
}

export function computeBranchScore(
  branchId: string,
  nodes: NodeRow[],
  edges: EdgeRow[],
  artifacts: ArtifactRow[],
  currentRound: number,
): number {
  const branchVerifs = artifacts
    .filter((a) => a.artifact_type === "verification" && a.branch_id === branchId)
    .sort((a, b) => a.round_produced - b.round_produced);

  let verifScore = 0;
  if (branchVerifs.length > 0) {
    verifScore = (branchVerifs[branchVerifs.length - 1].content as any).overall_score ?? 0;
  }

  const branchNodes = nodes.filter((n) => n.branch_id === branchId);
  let avgContrib = 0;
  if (branchNodes.length > 0) {
    const contribs = branchNodes.map((n) =>
      computeNodeContribution(n, edges, nodes, artifacts, currentRound)
    );
    avgContrib = contribs.reduce((s, v) => s + v, 0) / contribs.length;
  }

  return 0.7 * verifScore + 0.3 * avgContrib;
}

// ============================================================
// Spawn Rules
// ============================================================

function checkSpawnTriggers(
  nodes: NodeRow[],
  edges: EdgeRow[],
  artifacts: ArtifactRow[],
  currentRound: number,
): ControllerAction[] {
  const actions: ControllerAction[] = [];

  // Uncertainty branching
  const plans = artifacts.filter((a) => a.artifact_type === "plan");
  for (const plan of plans) {
    const uncertainties = (plan.content as any).uncertainties ?? [];
    if (uncertainties.length > 0 && (plan.content as any).needs_branching) {
      actions.push({
        actionType: "spawn",
        targetNode: "",
        payload: { template: "coder", branch_id: `branch_${currentRound}` },
        reason: `Plan has ${uncertainties.length} uncertainties, spawning alternative branch`,
      });
    }
  }

  // Repeated failures → spawn debugger
  const verifications = artifacts.filter((a) => a.artifact_type === "verification");
  const branchFailures: Record<string, number> = {};
  for (const v of verifications) {
    const c = v.content as any;
    if (!c.tests_passed || !c.build_passed) {
      branchFailures[v.branch_id] = (branchFailures[v.branch_id] ?? 0) + 1;
    }
  }
  for (const [branchId, count] of Object.entries(branchFailures)) {
    if (count >= ESCALATION_FAILURE_COUNT) {
      const hasDebugger = nodes.some(
        (n) => n.template === "debugger" && n.branch_id === branchId,
      );
      if (!hasDebugger) {
        actions.push({
          actionType: "spawn",
          targetNode: "",
          payload: { template: "debugger", branch_id: branchId },
          reason: `Branch ${branchId} has ${count} verification failures`,
        });
      }
    }
  }

  // Unreviewed patches → spawn reviewer
  const patches = artifacts.filter((a) => a.artifact_type === "patch");
  const reviews = artifacts.filter((a) => a.artifact_type === "review");
  const reviewedBranches = new Set(reviews.map((r) => r.branch_id));
  for (const patch of patches) {
    if (!reviewedBranches.has(patch.branch_id)) {
      const hasReviewer = nodes.some(
        (n) =>
          (n.template === "skeptic_reviewer" || n.template === "security_reviewer") &&
          n.branch_id === patch.branch_id,
      );
      if (!hasReviewer) {
        actions.push({
          actionType: "spawn",
          targetNode: "",
          payload: { template: "skeptic_reviewer", branch_id: patch.branch_id },
          reason: `Patch on branch ${patch.branch_id} has no review`,
        });
      }
    }
  }

  return actions;
}

// ============================================================
// Prune Rules
// ============================================================

function checkPruneTriggers(
  nodes: NodeRow[],
  edges: EdgeRow[],
  artifacts: ArtifactRow[],
  currentRound: number,
  budgetPressure: number,
): ControllerAction[] {
  const actions: ControllerAction[] = [];
  const activeNodes = nodes.filter((n) => n.status === "pending" || n.status === "running");

  for (const node of activeNodes) {
    if (node.rounds_active < 2) continue;
    const contrib = computeNodeContribution(node, edges, nodes, artifacts, currentRound);
    let threshold = PRUNE_CONTRIBUTION_THRESHOLD;
    if (budgetPressure > 0.7) threshold *= 2;
    if (contrib < threshold) {
      actions.push({
        actionType: "prune",
        targetNode: node.id,
        payload: {},
        reason: `Low contribution (${contrib.toFixed(2)} < ${threshold.toFixed(2)})`,
      });
    }
  }

  // Prune dominated branches
  const branchIds = [...new Set(activeNodes.map((n) => n.branch_id))];
  if (branchIds.length > 1) {
    const branchScores: Record<string, number> = {};
    for (const bid of branchIds) {
      branchScores[bid] = computeBranchScore(bid, nodes, edges, artifacts, currentRound);
    }
    const bestScore = Math.max(...Object.values(branchScores));
    for (const [bid, score] of Object.entries(branchScores)) {
      if (bid === "main") continue;
      if (score < bestScore * 0.3 && currentRound > 3) {
        for (const node of nodes.filter((n) => n.branch_id === bid)) {
          if (node.status === "pending" || node.status === "running") {
            actions.push({
              actionType: "prune",
              targetNode: node.id,
              payload: {},
              reason: `Branch ${bid} dominated (score ${score.toFixed(2)} vs best ${bestScore.toFixed(2)})`,
            });
          }
        }
      }
    }
  }

  return actions;
}

// ============================================================
// Merge Rules
// ============================================================

function checkMergeTriggers(
  nodes: NodeRow[],
  edges: EdgeRow[],
  artifacts: ArtifactRow[],
  currentRound: number,
): ControllerAction[] {
  const actions: ControllerAction[] = [];
  const activeNodes = nodes.filter(
    (n) => n.status !== "pruned" && n.status !== "merged",
  );
  const branchIds = [...new Set(activeNodes.map((n) => n.branch_id))];
  if (branchIds.length < 2) return actions;

  // Near-duplicate branches
  const branchPatches: Record<string, Set<string>> = {};
  for (const bid of branchIds) {
    const patches = artifacts.filter(
      (a) => a.artifact_type === "patch" && a.branch_id === bid,
    );
    const files = new Set<string>();
    for (const p of patches) {
      for (const patch of (p.content as any).patches ?? []) {
        files.add(patch.file_path ?? "");
      }
    }
    branchPatches[bid] = files;
  }

  const checked = new Set<string>();
  for (const b1 of branchIds) {
    for (const b2 of branchIds) {
      const key = [b1, b2].sort().join("|");
      if (b1 === b2 || checked.has(key)) continue;
      checked.add(key);

      const f1 = branchPatches[b1] ?? new Set();
      const f2 = branchPatches[b2] ?? new Set();
      if (f1.size === 0 || f2.size === 0) continue;

      const union = new Set([...f1, ...f2]);
      const intersection = [...f1].filter((x) => f2.has(x));
      const overlap = intersection.length / Math.max(1, union.size);

      if (overlap >= MERGE_SIMILARITY_THRESHOLD) {
        const s1 = computeBranchScore(b1, nodes, edges, artifacts, currentRound);
        const s2 = computeBranchScore(b2, nodes, edges, artifacts, currentRound);
        const [winner, loser] = s1 >= s2 ? [b1, b2] : [b2, b1];
        actions.push({
          actionType: "merge",
          targetNode: "",
          payload: { source_branch: loser, target_branch: winner, overlap },
          reason: `Branches ${loser}→${winner} overlap ${(overlap * 100).toFixed(0)}%`,
        });
      }
    }
  }

  // Converged branches
  for (const bid of branchIds) {
    if (bid === "main") continue;
    const score = computeBranchScore(bid, nodes, edges, artifacts, currentRound);
    const mainScore = computeBranchScore("main", nodes, edges, artifacts, currentRound);
    if (score > 0.8 && mainScore > 0.8 && currentRound > 5) {
      actions.push({
        actionType: "merge",
        targetNode: "",
        payload: { source_branch: bid, target_branch: "main", convergence: true },
        reason: `Branch ${bid} converged with main (both > 0.8)`,
      });
    }
  }

  return actions;
}

// ============================================================
// Escalation
// ============================================================

function checkEscalation(nodes: NodeRow[]): ControllerAction[] {
  const actions: ControllerAction[] = [];
  const activeNodes = nodes.filter((n) => n.status === "pending" || n.status === "running");

  for (const node of activeNodes) {
    if (node.model_tier === "opus") continue;
    if (node.rounds_active >= 3 && node.contribution_score < 0.2) {
      const cfg = TEMPLATE_CONFIGS[node.template];
      const newTier = cfg?.escalationTier ?? "sonnet";
      actions.push({
        actionType: "escalate",
        targetNode: node.id,
        payload: { new_tier: newTier },
        reason: `Node ${node.id} underperforming, escalating to ${newTier}`,
      });
    }
  }

  return actions;
}

// ============================================================
// Main Controller Step
// ============================================================

export function controllerStep(
  nodes: NodeRow[],
  edges: EdgeRow[],
  artifacts: ArtifactRow[],
  currentRound: number,
  budgetPressure: number,
  maxNodes: number,
  maxBranches: number,
): ControllerState {
  let actions: ControllerAction[] = [];

  actions.push(...checkSpawnTriggers(nodes, edges, artifacts, currentRound));
  actions.push(...checkPruneTriggers(nodes, edges, artifacts, currentRound, budgetPressure));
  actions.push(...checkMergeTriggers(nodes, edges, artifacts, currentRound));
  actions.push(...checkEscalation(nodes));

  // Filter spawns by budget
  const activeNodes = nodes.filter((n) => n.status === "pending" || n.status === "running");
  const activeBranches = new Set(
    nodes.filter((n) => n.status !== "pruned" && n.status !== "merged").map((n) => n.branch_id),
  );
  let pendingSpawns = 0;

  actions = actions.filter((a) => {
    if (a.actionType === "spawn") {
      if (activeNodes.length + pendingSpawns >= maxNodes) return false;
      const newBranch = (a.payload.branch_id as string) ?? "main";
      if (!activeBranches.has(newBranch) && activeBranches.size >= maxBranches) return false;
      pendingSpawns++;
    }
    return true;
  });

  // Compute scores
  const branchIds = [...new Set(
    nodes.filter((n) => n.status !== "pruned" && n.status !== "merged").map((n) => n.branch_id),
  )];
  const branchScores: Record<string, number> = {};
  for (const bid of branchIds) {
    branchScores[bid] = computeBranchScore(bid, nodes, edges, artifacts, currentRound);
  }

  const nodeContributions: Record<string, number> = {};
  for (const node of activeNodes) {
    nodeContributions[node.id] = computeNodeContribution(
      node, edges, nodes, artifacts, currentRound,
    );
  }

  return {
    round: currentRound,
    actionsTaken: actions,
    branchScores,
    nodeContributions,
  };
}
