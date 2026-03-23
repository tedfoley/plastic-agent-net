// PlasticAgentNet Dashboard — Supabase Realtime + D3.js
// Replaces SSE with Supabase Realtime subscriptions

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

function initGraph() {
    const svg = d3.select("#graph-svg");
    const rect = svg.node().getBoundingClientRect();
    const width = rect.width || 800;
    const height = rect.height || 500;

    svg.selectAll("*").remove();

    linkGroup = svg.append("g").attr("class", "links");
    nodeGroup = svg.append("g").attr("class", "nodes");

    simulation = d3.forceSimulation()
        .force("link", d3.forceLink().id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody().strength(-300))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide(30));
}

function updateGraph(nodes, edges) {
    if (!simulation || !linkGroup || !nodeGroup) return;

    // Filter to non-pruned nodes for display
    const displayNodes = nodes.filter(n => n.status !== "pruned");
    const displayNodeIds = new Set(displayNodes.map(n => n.id));
    const displayEdges = edges.filter(e =>
        e.active && displayNodeIds.has(e.source_node) && displayNodeIds.has(e.target_node)
    );

    // Links
    const links = linkGroup.selectAll("line")
        .data(displayEdges, d => `${d.source_node}-${d.target_node}`);

    links.exit().remove();

    links.enter()
        .append("line")
        .attr("class", d => `link ${d.active ? "active" : ""}`);

    // Nodes
    const nodesSel = nodeGroup.selectAll("g.node")
        .data(displayNodes, d => d.id);

    nodesSel.exit().remove();

    const nodesEnter = nodesSel.enter()
        .append("g")
        .attr("class", "node")
        .call(d3.drag()
            .on("start", dragStarted)
            .on("drag", dragged)
            .on("end", dragEnded));

    nodesEnter.append("circle")
        .attr("r", 12)
        .attr("class", d => `template-${d.template}`);

    nodesEnter.append("text")
        .attr("dy", 25)
        .attr("text-anchor", "middle")
        .text(d => d.template.replace(/_/g, " "));

    // Update existing
    nodeGroup.selectAll("circle")
        .attr("r", d => d.status === "running" ? 15 : 12)
        .attr("opacity", d => d.status === "merged" ? 0.4 : 1);

    // Update simulation
    const simNodes = displayNodes.map(n => ({
        ...n,
        x: n.x || undefined,
        y: n.y || undefined,
    }));

    const simLinks = displayEdges.map(e => ({
        source: e.source_node,
        target: e.target_node,
    }));

    simulation.nodes(simNodes);
    simulation.force("link").links(simLinks);
    simulation.alpha(0.3).restart();

    const allLinks = linkGroup.selectAll("line");
    const allNodes = nodeGroup.selectAll("g.node");

    simulation.on("tick", () => {
        allLinks
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        allNodes.attr("transform", d => `translate(${d.x},${d.y})`);
    });
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
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================
// Episode Detail
// ============================================================

async function openEpisode(episodeId) {
    currentEpisodeId = episodeId;

    // Switch views
    document.getElementById("view-list").classList.remove("active");
    document.getElementById("view-detail").classList.add("active");
    document.getElementById("back-btn").style.display = "inline-block";

    initGraph();
    await refreshEpisodeDetail();
    subscribeRealtime(episodeId);
}

function showEpisodeList() {
    currentEpisodeId = null;

    // Unsubscribe from realtime
    if (realtimeChannel) {
        sb.removeChannel(realtimeChannel);
        realtimeChannel = null;
    }

    document.getElementById("view-detail").classList.remove("active");
    document.getElementById("view-list").classList.add("active");
    document.getElementById("back-btn").style.display = "none";

    // Reset status bar
    document.getElementById("status-indicator").textContent = "idle";
    document.getElementById("status-indicator").className = "status idle";
    document.getElementById("round-counter").textContent = "Round: —";
    document.getElementById("token-counter").textContent = "Tokens: —";
    document.getElementById("node-counter").textContent = "Nodes: —";

    loadEpisodeList();
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
            () => refreshEpisodeDetail()
        )
        .on(
            "postgres_changes",
            { event: "*", schema: "public", table: "edges", filter: `episode_id=eq.${episodeId}` },
            () => refreshEpisodeDetail()
        )
        .on(
            "postgres_changes",
            { event: "*", schema: "public", table: "artifacts", filter: `episode_id=eq.${episodeId}` },
            () => refreshEpisodeDetail()
        )
        .on(
            "postgres_changes",
            { event: "*", schema: "public", table: "events", filter: `episode_id=eq.${episodeId}` },
            () => refreshEpisodeDetail()
        )
        .on(
            "postgres_changes",
            { event: "UPDATE", schema: "public", table: "episodes", filter: `id=eq.${episodeId}` },
            () => refreshEpisodeDetail()
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
                <span style="width: 80px">${escapeHtml(bid)}</span>
                <div class="bar">
                    <div class="bar-fill" style="width: ${(score * 100).toFixed(0)}%"></div>
                </div>
                <span>${(score * 100).toFixed(0)}%</span>
            </div>
        `).join("");
}

function updateArtifacts(artifacts) {
    const list = document.getElementById("artifact-list");
    list.innerHTML = artifacts.map(a => `
        <div class="artifact-item" onclick="showArtifactDetail('${a.id}')">
            <div class="type">[${escapeHtml(a.artifact_type)}] round ${a.round_produced}</div>
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

    if (data) {
        console.log("Artifact detail:", data);
        alert(`[${data.artifact_type}] ${data.summary}\n\n${JSON.stringify(data.content, null, 2).slice(0, 1000)}`);
    }
}

function updateLogStream(events) {
    const log = document.getElementById("log-stream");
    log.innerHTML = events.map(e => `
        <div class="log-entry">
            <span class="event-type">${escapeHtml(e.event_type)}</span>
            ${e.round !== null ? `R${e.round}` : ""}
            ${JSON.stringify(e.payload || {}).slice(0, 100)}
        </div>
    `).join("");
}

function addLogEntry(event) {
    const log = document.getElementById("log-stream");
    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.innerHTML = `<span class="event-type">${escapeHtml(event.event_type || "?")}</span> ${JSON.stringify(event.payload || {}).slice(0, 100)}`;
    log.prepend(entry);
    if (log.children.length > 200) log.removeChild(log.lastChild);
}

// ============================================================
// Init
// ============================================================

// Check URL params for direct episode link
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
