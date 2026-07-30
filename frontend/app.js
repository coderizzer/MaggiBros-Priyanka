// -------------------------------------------------------------
// CampusPilot Premium App Logic Engine
// Handles API calls, tab navigation, modals, and dynamic data state
// -------------------------------------------------------------

const BACKEND_URL = "http://localhost:8000";

// Global Data Store
let state = {
    locations: [],
    departments: [],
    awaitingLocation: false,
    currentComplaintMessage: "",
    currentComplaintCategory: ""
};

// Start initialization
document.addEventListener("DOMContentLoaded", () => {
    initNavigation();
    initChat();
    checkBackendHealth();
    
    // Initial fetch of static configuration data
    fetchLocations();
    fetchDepartments();
    
    // Periodically fetch dashboard
    refreshDashboard();
    fetchTickets();
});

// 1. Navigation Tab Controller
function initNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    const tabs = document.querySelectorAll(".tab-content");

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");
            
            navItems.forEach(nav => nav.classList.remove("active"));
            tabs.forEach(tab => tab.classList.remove("active"));
            
            item.classList.add("active");
            document.getElementById(`${targetTab}-tab`).classList.add("active");
            
            // Screen specific loads
            if (targetTab === "dashboard") {
                refreshDashboard();
            } else if (targetTab === "tickets") {
                fetchTickets();
            }
        });
    });
}

// 2. Health Checker
async function checkBackendHealth() {
    const statusText = document.getElementById("backend-status");
    try {
        const response = await fetch(`${BACKEND_URL}/health`);
        if (response.ok) {
            statusText.textContent = "Operations Online";
            statusText.style.color = "#10b981";
        } else {
            statusText.textContent = "Operational Delay";
            statusText.style.color = "#f59e0b";
        }
    } catch (e) {
        statusText.textContent = "Connection Offline";
        statusText.style.color = "#ef4444";
    }
}

// 3. Static Lists Fetching
async function fetchLocations() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/locations`);
        if (res.ok) {
            state.locations = await res.json();
            populateLocationPicker();
        }
    } catch (e) {
        console.error("Error loading locations:", e);
    }
}

async function fetchDepartments() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/departments`);
        if (res.ok) {
            state.departments = await res.json();
            
            // Populate modal dropdown
            const modalDeptSelect = document.getElementById("modal-dept");
            modalDeptSelect.innerHTML = state.departments.map(d => 
                `<option value="${d.id}">${d.name}</option>`
            ).join("");
        }
    } catch (e) {
        console.error("Error loading departments:", e);
    }
}

// Populate grid helper
function populateLocationPicker() {
    const grid = document.getElementById("location-grid");
    grid.innerHTML = state.locations.map(loc => 
        `<button class="location-btn" onclick="submitTicketWithLocation(${loc.id})">${loc.name}</button>`
    ).join("");
}

// 4. Chat copilot client logic
function initChat() {
    const input = document.getElementById("chat-input");
    const btn = document.getElementById("btn-send");
    
    const sendMessage = async () => {
        const message = input.value.trim();
        if (!message) return;
        
        appendChatMessage("user", message);
        input.value = "";
        
        await dispatchChatMessage({ message });
    };
    
    btn.addEventListener("click", sendMessage);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendMessage();
    });
}

function appendChatMessage(sender, text, extra = null) {
    const container = document.getElementById("chat-messages");
    
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", sender);
    
    let bubbleContent = `<p>${text}</p>`;
    
    if (extra && extra.source) {
        bubbleContent += `
            <div class="message-source">
                <i class="fa-solid fa-file-invoice"></i>
                <span>Source: ${extra.source.document} (Page ${extra.source.page}) | Confidence: ${(extra.confidence * 100).toFixed(0)}%</span>
            </div>
        `;
    }
    
    msgDiv.innerHTML = `<div class="message-bubble">${bubbleContent}</div>`;
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

async function dispatchChatMessage(payload) {
    try {
        const res = await fetch(`${BACKEND_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) {
            appendChatMessage("assistant", "Sorry, I had trouble processing that request. Please try again.");
            return;
        }
        
        const data = await res.json();
        handleChatResponse(data, payload.message);
    } catch (e) {
        appendChatMessage("assistant", "Unable to connect to the CampusPilot service. Verify your server connection.");
    }
}

function handleChatResponse(data, originalMessage) {
    if (data.type === "complaint") {
        // Step 1: Prompt Location picker
        state.awaitingLocation = true;
        state.currentComplaintMessage = originalMessage;
        state.currentComplaintCategory = data.category;
        
        appendChatMessage("assistant", `${data.message} Please select the campus location from the panel below to file a ticket.`);
        document.getElementById("location-picker").classList.remove("hidden");
    } else if (data.type === "ticket_created") {
        // Step 2: Ticket Creation Complete
        appendChatMessage("assistant", `${data.message}\n\nTicket Reference: **#${data.ticket_id}**\nDepartment: **${data.department}**\nSLA: **${data.estimated_resolution}**`);
    } else if (data.type === "ticket_status") {
        // Ticket Status retrieval
        appendChatMessage("assistant", `**Ticket Reference #${data.ticket_id}**\nStatus: **${data.status}**\nDepartment: **${data.department}**\nSLA: **${data.estimated_resolution}**`);
    } else {
        // FAQ Answer
        appendChatMessage("assistant", data.message, { source: data.source, confidence: data.confidence });
    }
}

function cancelComplaintFiling() {
    state.awaitingLocation = false;
    document.getElementById("location-picker").classList.add("hidden");
    appendChatMessage("assistant", "Complaint registration cancelled.");
}

async function submitTicketWithLocation(locationId) {
    document.getElementById("location-picker").classList.add("hidden");
    state.awaitingLocation = false;
    
    // Dispatch second step query with location_id
    await dispatchChatMessage({
        message: state.currentComplaintMessage,
        location_id: locationId
    });
}

// 5. Dashboard Aggregations Fetcher
async function refreshDashboard() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/dashboard`);
        if (res.ok) {
            const data = await res.json();
            
            document.getElementById("metric-total").textContent = data.total_tickets;
            document.getElementById("metric-open").textContent = data.open_tickets;
            document.getElementById("metric-resolved").textContent = data.resolved_today;
            document.getElementById("metric-sla").textContent = `${data.average_resolution_time.toFixed(1)}h`;
        }
        
        // Load insights
        const insightsRes = await fetch(`${BACKEND_URL}/api/analytics/insights`);
        if (insightsRes.ok) {
            const insightsData = await insightsRes.json();
            const list = document.getElementById("insights-list");
            list.innerHTML = insightsData.insights.map(item => `
                <div class="insight-card ${item.severity}">
                    <h4>${item.title} (${item.severity})</h4>
                    <p>${item.description}</p>
                </div>
            `).join("");
        }
        
        // Load Heatmap hotspots
        const mapRes = await fetch(`${BACKEND_URL}/api/map/complaints`);
        if (mapRes.ok) {
            const mapData = await mapRes.json();
            const list = document.getElementById("heatmap-list");
            list.innerHTML = mapData.locations.map(loc => `
                <div class="hotspot-row">
                    <div class="hotspot-info">
                        <span class="hotspot-name">${loc.name}</span>
                        <span class="hotspot-coords">Lat: ${loc.latitude.toFixed(4)}, Lng: ${loc.longitude.toFixed(4)}</span>
                    </div>
                    <span class="hotspot-count">${loc.total_complaints} active issues</span>
                </div>
            `).join("");
        }
    } catch (e) {
        console.error("Dashboard refresh failure:", e);
    }
}

// 6. Tickets Manager Logic
async function fetchTickets() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/tickets`);
        if (res.ok) {
            const tickets = await res.json();
            populateTicketsTable(tickets);
        }
    } catch (e) {
        console.error("Error loading tickets:", e);
    }
}

function populateTicketsTable(tickets) {
    const tbody = document.getElementById("tickets-tbody");
    
    // Sort priority-wise: CRITICAL (highest) -> HIGH -> MEDIUM -> LOW
    const priorityWeights = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1
    };
    
    tickets.sort((a, b) => {
        const weightA = priorityWeights[a.priority.toUpperCase()] || 0;
        const weightB = priorityWeights[b.priority.toUpperCase()] || 0;
        return weightB - weightA;
    });
    
    tbody.innerHTML = tickets.map(t => {
        const deptName = t.department ? t.department.name : "Unassigned";
        const badgeClass = `badge-${t.status.toLowerCase().replace('_', '')}`;
        const prioClass = `priority-${t.priority.toLowerCase()}`;
        return `
            <tr>
                <td>#${t.id}</td>
                <td><strong>${t.title}</strong></td>
                <td>${t.complaint ? t.complaint.category.replace('_', ' ').toUpperCase() : "GENERAL"}</td>
                <td><span class="badge ${prioClass}">${t.priority}</span></td>
                <td>${deptName}</td>
                <td><span class="badge ${badgeClass}">${t.status}</span></td>
                <td>
                    <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;" onclick="openTicketModal(${t.id}, '${t.status}', ${t.department_id || 'null'})">
                        <i class="fa-solid fa-pen-to-square"></i> Action
                    </button>
                </td>
            </tr>
        `;
    }).join("");
}

// Ticket action modal logic
function openTicketModal(id, status, departmentId) {
    document.getElementById("modal-ticket-id").value = id;
    document.getElementById("modal-status").value = status;
    
    if (departmentId) {
        document.getElementById("modal-dept").value = departmentId;
    }
    
    document.getElementById("ticket-modal").classList.remove("hidden");
}

function closeTicketModal() {
    document.getElementById("ticket-modal").classList.add("hidden");
}

async function saveTicketChanges() {
    const id = document.getElementById("modal-ticket-id").value;
    const status = document.getElementById("modal-status").value;
    const deptId = document.getElementById("modal-dept").value;
    
    try {
        // Save Status Update
        await fetch(`${BACKEND_URL}/api/tickets/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status })
        });
        
        // Save Department re-route
        await fetch(`${BACKEND_URL}/api/tickets/${id}/department`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ department_id: parseInt(deptId) })
        });
        
        closeTicketModal();
        fetchTickets();
        refreshDashboard();
    } catch (e) {
        alert("Failed to save changes. Verify backend connection.");
    }
}

// 7. RAG Knowledge Base Search
async function searchKnowledgeBase() {
    const input = document.getElementById("knowledge-search-input");
    const query = input.value.trim();
    if (!query) return;
    
    const resultsContainer = document.getElementById("knowledge-results");
    resultsContainer.innerHTML = `<div class="placeholder-results"><i class="fa-solid fa-spinner fa-spin"></i><p>Searching knowledge documents...</p></div>`;
    
    try {
        const res = await fetch(`${BACKEND_URL}/api/knowledge/search`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query })
        });
        
        if (res.ok) {
            const data = await res.json();
            if (data.results.length === 0) {
                resultsContainer.innerHTML = `<div class="placeholder-results"><i class="fa-solid fa-circle-info"></i><p>No document matches found. Populate documents/ directory and execute ingestion.</p></div>`;
                return;
            }
            
            resultsContainer.innerHTML = data.results.map(chunk => `
                <div class="chunk-card">
                    <p class="chunk-text">"${chunk.text}"</p>
                    <div class="chunk-meta">
                        <span><strong>Source:</strong> ${chunk.source} (Page ${chunk.page})</span>
                        <span><strong>Cosine Similarity:</strong> ${(chunk.score * 100).toFixed(1)}%</span>
                    </div>
                </div>
            `).join("");
        } else {
            resultsContainer.innerHTML = `<div class="placeholder-results"><i class="fa-solid fa-circle-xmark text-danger"></i><p>Failed to retrieve search details.</p></div>`;
        }
    } catch (e) {
        resultsContainer.innerHTML = `<div class="placeholder-results"><i class="fa-solid fa-circle-xmark text-danger"></i><p>RAG service search disconnected.</p></div>`;
    }
}
