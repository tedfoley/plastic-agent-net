// PlasticAgentNet Dashboard — Supabase Realtime + D3.js

// ============================================================
// Supabase Client
// ============================================================

const sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// State
let currentEpisodeId = null;
let realtimeChannel = null;

// ============================================================
// D3 Graph Setup
// ============================================================

let simulation = null;
let linkGroup = null;
let nodeGroup = null;
let graphNodes = [];  // Persistent node objects for D3 simulation
let graphLinks = [];  // Persistent link objects for D3 simulation

function initGraph() {
    const svg = d3.select("#graph-svg");
    svg.selectAll("*").remove();

    // Reset persistent state
    graphNodes = [];
    graphLinks = [];

    // Add a root <g> for zoom/pan
    const rootG = svg.append("g").attr("class", "graph-root");
    linkGroup = rootG.append("g").attr("class", "links");
    nodeGroup = rootG.append("g").attr("class", "nodes");

    // Enable zoom & pan
    const zoom = d3.zoom()
        .scaleExtent([0.3, 3])
        .on("zoom", (event) => rootG.attr("transform", event.transform));
    svg.call(zoom);

    const rect = svg.node().getBoundingClientRect();
    const width = rect.width || 800;
    const height = rect.height || 500;

    simulation = d3.forceSimulation()
        .force("link", d3.forceLink().id(d => d.id).distance(120))
        .force("charge", d3.forceManyBody().strength(-400))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide(40))
        .on("tick", ticked);
}

function ticked() {
    if (!linkGroup || !nodeGroup) return;

    linkGroup.selectAll("line")
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

    nodeGroup.selectAll("g.node")
        .attr("transform", d => `translate(${d.x},${d.y})`);
}

function updateGraph(nodes, edges) {
    if (!simulation || !linkGroup || !nodeGroup) return;

    // Filter to non-pruned nodes
    const displayNodes = nodes.filter(n => n.status !== "pruned");
    const displayNodeIds = new Set(displayNodes.map(n => n.id));
    const displayEdges = edges.filter(e =>
        displayNodeIds.has(e.source_node) && displayNodeIds.has(e.target_node)
    );

    // --- Merge new data into persistent graphNodes (preserve positions) ---
    const existingById = new Map(graphNodes.map(n => [n.id, n]));
    const newNodeIds = new Set(displayNodes.map(n => n.id));

    // Remove nodes no longer present
    graphNodes = graphNodes.filter(n => newNodeIds.has(n.id));

    // Update existing / add new
    for (const n of displayNodes) {
        const existing = existingById.get(n.id);
        if (existing) {
            // Update mutable fields, keep x/y
            existing.template = n.template;
            existing.status = n.status;
        } else {
            // New node — let simulation place it
            graphNodes.push({ id: n.id, template: n.template, status: n.status });
        }
    }

    // --- Build links referencing node IDs ---
    graphLinks = displayEdges.map(e => ({
        source: e.source_node,
        target: e.target_node,
        active: e.active,
    }));

    // --- D3 data join: Links ---
    const links = linkGroup.selectAll("line")
        .data(graphLinks, d => `${d.source.id || d.source}-${d.target.id || d.target}`);

    links.exit().remove();

    const linksEnter = links.enter()
        .append("line")
        .attr("class", d => `link${d.active ? " active" : ""}`);

    links.merge(linksEnter)
        .attr("class", d => `link${d.active ? " active" : ""}`);

    // --- D3 data join: Nodes ---
    const nodesSel = nodeGroup.selectAll("g.node")
        .data(graphNodes, d => d.id);

    nodesSel.exit().remove();

    const nodesEnter = nodesSel.enter()
        .append("g")
        .attr("class", "node")
        .call(d3.drag()
            .on("start", dragStarted)
            .on("drag", dragged)
            .on("end", dragEnded));

    nodesEnter.append("circle").attr("r", 14);
    nodesEnter.append("text")
        .attr("dy", 28)
        .attr("text-anchor", "middle");

    // Merge enter + update
    const merged = nodesSel.merge(nodesEnter);

    merged.select("circle")
        .attr("r", d => d.status === "running" ? 17 : 14)
        .attr("class", d => `template-${d.template}`)
        .attr("opacity", d => d.status === "merged" ? 0.35 : 1);

    merged.select("text")
        .text(d => d.template.replace(/_/g, " "));

    // --- Update simulation ---
    simulation.nodes(graphNodes);
    simulation.force("link").links(graphLinks);
    simulation.alpha(0.4).restart();
}

function dragStarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragEnded(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

// ============================================================
// Episode List
// ============================================================

async function loadEpisodeList() {
    const { data, error } = await sb
        .from("episodes")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(50);

    if (error) {
        console.error("Failed to load episodes:", error);
        return;
    }

    const list = document.getElementById("episode-list");
    const noEp = document.getElementById("no-episodes");

    if (!data || data.length === 0) {
        list.innerHTML = "";
        noEp.style.display = "block";
        return;
    }

    noEp.style.display = "none";
    list.innerHTML = data.map(ep => {
        const created = new Date(ep.created_at).toLocaleString();
        return `
            <div class="episode-card" onclick="openEpisode('${ep.id}')">
                <div class="ep-task">${escapeHtml(ep.task)}</div>
                <div class="ep-meta">
                    <span class="status ${ep.status}">${ep.status}</span>
                    <span>Rounds: ${ep.rounds_completed}</span>
                    <span>Tokens: ${(ep.tokens_used || 0).toLocaleString()}</span>
                    <span>${created}</span>
                </div>
            </div>
        `;
    }).join("");
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text || "";
    return div.innerHTML;
}

// ============================================================
// Episode Detail
// ============================================================

async function openEpisode(episodeId) {
    currentEpisodeId = episodeId;

    document.getElementById("view-list").classList.remove("active");
    document.getElementById("view-detail").classList.add("active");
    document.getElementById("back-btn").style.display = "inline-block";

    initGraph();
    await refreshEpisodeDetail();
    subscribeRealtime(episodeId);
}

function showEpisodeList() {
    currentEpisodeId = null;

    if (realtimeChannel) {
        sb.removeChannel(realtimeChannel);
        realtimeChannel = null;
    }

    document.getElementById("view-detail").classList.remove("active");
    document.getElementById("view-list").classList.add("active");
    document.getElementById("back-btn").style.display = "none";

    document.getElementById("status-indicator").textContent = "idle";
    document.getElementById("status-indicator").className = "status idle";
    document.getElementById("round-counter").textContent = "Round: —";
    document.getElementById("token-counter").textContent = "Tokens: —";
    document.getElementById("node-counter").textContent = "Nodes: —";

    loadEpisodeList();
}

// Debounce refresh to avoid rapid-fire updates
let refreshTimer = null;
function scheduleRefresh() {
    if (refreshTimer) return;
    refreshTimer = setTimeout(() => {
        refreshTimer = null;
        refreshEpisodeDetail();
    }, 300);
}

async function refreshEpisodeDetail() {
    if (!currentEpisodeId) return;

    try {
        const [epRes, nodesRes, edgesRes, artifactsRes, eventsRes] = await Promise.all([
            sb.from("episodes").select("*").eq("id", currentEpisodeId).single(),
            sb.from("nodes").select("*").eq("episode_id", currentEpisodeId),
            sb.from("edges").select("*").eq("episode_id", currentEpisodeId),
            sb.from("artifacts").select("*").eq("episode_id", currentEpisodeId).order("created_at"),
            sb.from("events").select("*").eq("episode_id", currentEpisodeId).order("created_at", { ascending: false }).limit(100),
        ]);

        const episode = epRes.data;
        const nodes = nodesRes.data || [];
        const edges = edgesRes.data || [];
        const artifacts = artifactsRes.data || [];
        const events = eventsRes.data || [];

        // Update status bar
        if (episode) {
            const indicator = document.getElementById("status-indicator");
            indicator.textContent = episode.status;
            indicator.className = `status ${episode.status}`;
            document.getElementById("round-counter").textContent = `Round: ${episode.rounds_completed}`;
            document.getElementById("token-counter").textContent = `Tokens: ${(episode.tokens_used || 0).toLocaleString()}`;
        }

        // Update node counter
        const activeNodes = nodes.filter(n => n.status === "pending" || n.status === "running");
        document.getElementById("node-counter").textContent = `Nodes: ${activeNodes.length}`;

        // Update graph
        updateGraph(nodes, edges);

        // Update branch scores
        if (episode && episode.branch_scores) {
            updateBranchScores(episode.branch_scores);
        } else {
            document.getElementById("branch-scores").innerHTML = "";
        }

        // Update artifacts
        updateArtifacts(artifacts);

        // Update log
        updateLogStream(events);

    } catch (e) {
        console.error("Refresh failed:", e);
    }
}

// ============================================================
// Supabase Realtime
// ============================================================

function subscribeRealtime(episodeId) {
    if (realtimeChannel) {
        sb.removeChannel(realtimeChannel);
    }

    const dot = document.getElementById("realtime-dot");
    dot.classList.remove("disconnected");

    realtimeChannel = sb
        .channel(`episode-${episodeId}`)
        .on(
            "postgres_changes",
            { event: "*", schema: "public", table: "nodes", filter: `episode_id=eq.${episodeId}` },
            () => scheduleRefresh()
        )
        .on(
            "postgres_changes",
            { event: "*", schema: "public", table: "edges", filter: `episode_id=eq.${episodeId}` },
            () => scheduleRefresh()
        )
        .on(
            "postgres_changes",
            { event: "*", schema: "public", table: "artifacts", filter: `episode_id=eq.${episodeId}` },
            () => scheduleRefresh()
        )
        .on(
            "postgres_changes",
            { event: "*", schema: "public", table: "events", filter: `episode_id=eq.${episodeId}` },
            () => scheduleRefresh()
        )
        .on(
            "postgres_changes",
            { event: "UPDATE", schema: "public", table: "episodes", filter: `id=eq.${episodeId}` },
            () => scheduleRefresh()
        )
        .subscribe((status) => {
            if (status === "SUBSCRIBED") {
                dot.classList.remove("disconnected");
            } else if (status === "CLOSED" || status === "CHANNEL_ERROR") {
                dot.classList.add("disconnected");
            }
        });
}

// ============================================================
// UI Update Helpers
// ============================================================

function updateBranchScores(scores) {
    const container = document.getElementById("branch-scores");
    if (!scores || Object.keys(scores).length === 0) {
        container.innerHTML = "";
        return;
    }

    container.innerHTML = Object.entries(scores)
        .sort((a, b) => b[1] - a[1])
        .map(([bid, score]) => `
            <div class="branch-score">
                <span style="width: 80px; flex-shrink: 0">${escapeHtml(bid)}</span>
                <div class="bar">
                    <div class="bar-fill" style="width: ${(score * 100).toFixed(0)}%"></div>
                </div>
                <span>${(score * 100).toFixed(0)}%</span>
            </div>
        `).join("");
}

function updateArtifacts(artifacts) {
    const list = document.getElementById("artifact-list");
    if (!artifacts || artifacts.length === 0) {
        list.innerHTML = '<div class="empty-state">No artifacts yet</div>';
        return;
    }
    list.innerHTML = artifacts.map(a => `
        <div class="artifact-item" onclick="showArtifactDetail('${a.id}')">
            <div class="type">${escapeHtml(a.artifact_type)} · round ${a.round_produced}</div>
            <div class="summary">${escapeHtml(a.summary || "—")}</div>
        </div>
    `).join("");
}

async function showArtifactDetail(artifactId) {
    const { data, error } = await sb
        .from("artifacts")
        .select("*")
        .eq("id", artifactId)
        .single();

    if (!data) return;

    const modal = document.getElementById("artifact-modal");
    document.getElementById("modal-title").textContent =
        `${data.artifact_type} — Round ${data.round_produced}`;
    document.getElementById("modal-summary").textContent = data.summary || "";
    document.getElementById("modal-content-pre").textContent =
        JSON.stringify(data.content, null, 2);

    modal.style.display = "flex";
    // Trigger transition
    requestAnimationFrame(() => modal.classList.add("visible"));
}

function closeArtifactModal() {
    const modal = document.getElementById("artifact-modal");
    modal.classList.remove("visible");
    setTimeout(() => { modal.style.display = "none"; }, 250);
}

// Close modal on overlay click
document.addEventListener("click", (e) => {
    if (e.target.id === "artifact-modal") closeArtifactModal();
});
document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeArtifactModal();
});

function updateLogStream(events) {
    const log = document.getElementById("log-stream");
    if (!events || events.length === 0) {
        log.innerHTML = '<div class="empty-state">No events yet</div>';
        return;
    }
    log.innerHTML = events.map(e => {
        const roundTag = e.round !== null && e.round !== undefined
            ? `<span class="round-tag">R${e.round}</span> `
            : "";
        const payload = escapeHtml(JSON.stringify(e.payload || {}).slice(0, 120));
        return `
            <div class="log-entry">
                <span class="event-type">${escapeHtml(e.event_type)}</span>
                ${roundTag}
                <span class="payload-text">${payload}</span>
            </div>
        `;
    }).join("");
}

// ============================================================
// Init
// ============================================================

const urlParams = new URLSearchParams(window.location.search);
const episodeParam = urlParams.get("episode");

if (episodeParam) {
    openEpisode(episodeParam);
} else {
    loadEpisodeList();
}

// Subscribe to new episodes on the list view
sb.channel("episode-list")
    .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "episodes" },
        () => {
            if (!currentEpisodeId) loadEpisodeList();
        }
    )
    .subscribe();
