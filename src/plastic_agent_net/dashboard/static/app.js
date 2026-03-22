// PlasticAgentNet Dashboard — D3.js force-directed graph + live updates

const svg = d3.select("#graph-svg");
const width = svg.node().getBoundingClientRect().width;
const height = svg.node().getBoundingClientRect().height;

const simulation = d3.forceSimulation()
    .force("link", d3.forceLink().id(d => d.id).distance(100))
    .force("charge", d3.forceManyBody().strength(-300))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide(30));

let linkGroup = svg.append("g").attr("class", "links");
let nodeGroup = svg.append("g").attr("class", "nodes");

// State
let graphData = { nodes: [], edges: [] };

function updateGraph(data) {
    graphData = data;

    // Links
    const links = linkGroup.selectAll("line")
        .data(data.edges, d => `${d.source}-${d.target}`);

    links.exit().remove();

    const linksEnter = links.enter()
        .append("line")
        .attr("class", d => `link ${d.active ? "active" : ""}`);

    // Nodes
    const nodes = nodeGroup.selectAll("g.node")
        .data(data.nodes, d => d.id);

    nodes.exit().remove();

    const nodesEnter = nodes.enter()
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
        .attr("opacity", d => d.status === "pruned" ? 0.3 : 1);

    // Simulation
    const allNodes = nodeGroup.selectAll("g.node");
    const allLinks = linkGroup.selectAll("line");

    simulation.nodes(data.nodes);
    simulation.force("link").links(data.edges.map(e => ({
        source: e.source,
        target: e.target
    })));
    simulation.alpha(0.3).restart();

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

// Artifact list
function updateArtifacts(artifacts) {
    const list = document.getElementById("artifact-list");
    list.innerHTML = artifacts.map(a => `
        <div class="artifact-item" onclick="fetchArtifact('${a.id}')">
            <div class="type">[${a.type}] round ${a.round}</div>
            <div class="summary">${a.summary || "—"}</div>
        </div>
    `).join("");
}

async function fetchArtifact(id) {
    const res = await fetch(`/api/artifacts/${id}`);
    const data = await res.json();
    console.log("Artifact detail:", data);
}

// Log stream
function addLogEntry(event) {
    const log = document.getElementById("log-stream");
    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.innerHTML = `<span class="event-type">${event.event || "?"}</span> ${JSON.stringify(event).slice(0, 120)}`;
    log.prepend(entry);
    if (log.children.length > 200) log.removeChild(log.lastChild);
}

// Status bar
function updateStatus(status) {
    const indicator = document.getElementById("status-indicator");
    indicator.textContent = status.status;
    indicator.className = `status ${status.status}`;

    if (status.round !== undefined) {
        document.getElementById("round-counter").textContent = `Round: ${status.round}`;
    }
    if (status.nodes !== undefined) {
        document.getElementById("node-counter").textContent = `Nodes: ${status.nodes}`;
    }
}

// SSE connection
function connectSSE() {
    const es = new EventSource("/events");

    es.addEventListener("round_start", e => {
        const data = JSON.parse(e.data);
        addLogEntry(data);
        refresh();
    });

    es.addEventListener("verification", e => {
        addLogEntry(JSON.parse(e.data));
    });

    es.addEventListener("controller_step", e => {
        const data = JSON.parse(e.data);
        addLogEntry(data);
        refresh();
    });

    es.addEventListener("episode_complete", e => {
        addLogEntry(JSON.parse(e.data));
        refresh();
    });

    es.addEventListener("update", e => {
        addLogEntry(JSON.parse(e.data));
    });

    es.onerror = () => {
        setTimeout(connectSSE, 3000);
    };
}

// Polling refresh
async function refresh() {
    try {
        const [graphRes, artifactRes, statusRes, budgetRes] = await Promise.all([
            fetch("/api/graph"),
            fetch("/api/artifacts"),
            fetch("/api/status"),
            fetch("/api/budget"),
        ]);

        const graph = await graphRes.json();
        const artifacts = await artifactRes.json();
        const status = await statusRes.json();
        const budget = await budgetRes.json();

        if (graph.nodes) updateGraph(graph);
        if (artifacts.artifacts) updateArtifacts(artifacts.artifacts);
        updateStatus(status);

        if (budget.usage) {
            document.getElementById("token-counter").textContent =
                `Tokens: ${budget.usage.total_tokens?.toLocaleString() || "—"}`;
        }
    } catch (e) {
        console.warn("Refresh failed:", e);
    }
}

// Init
connectSSE();
refresh();
setInterval(refresh, 5000);
