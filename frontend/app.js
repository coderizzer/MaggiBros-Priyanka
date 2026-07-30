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
    checkLoginState();
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
    const views = document.querySelectorAll(".view-content");
    const titleEl = document.getElementById("view-title");

    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");
            
            navItems.forEach(nav => nav.classList.remove("active"));
            views.forEach(view => view.classList.remove("active"));
            
            item.classList.add("active");
            
            // Show corresponding view
            const targetView = document.getElementById(`${targetTab}-view`);
            if (targetView) {
                targetView.classList.add("active");
            }
            
            // Update Title
            if (titleEl) {
                titleEl.textContent = targetTab.charAt(0).toUpperCase() + targetTab.slice(1);
            }
            
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
            if (modalDeptSelect) {
                modalDeptSelect.innerHTML = state.departments.map(d => 
                    `<option value="${d.id}">${d.name}</option>`
                ).join("");
            }
        }
    } catch (e) {
        console.error("Error loading departments:", e);
    }
}

// Populate grid helper
function populateLocationPicker() {
    const grid = document.getElementById("location-grid");
    if (grid) {
        grid.innerHTML = state.locations.map(loc => 
            `<button class="location-btn" onclick="submitTicketWithLocation(${loc.id})">${loc.name}</button>`
        ).join("");
    }
}

// 4. Chat copilot client logic
function initChat() {
    const input = document.getElementById("chat-input");
    const btn = document.getElementById("btn-send");
    
    if (input && btn) {
        const sendMessage = async () => {
            const message = input.value.trim();
            if (!message) return;
            
            appendChatMessage("user", `<strong>Admin</strong><br>${message}`);
            input.value = "";
            
            await dispatchChatMessage({ message });
        };
        
        btn.addEventListener("click", sendMessage);
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") sendMessage();
        });
    }
}

function appendChatMessage(sender, text, extra = null) {
    const container = document.querySelector(".chat-body");
    if (!container) return;
    
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", sender);
    
    let bubbleContent = `<p>${text}</p>`;
    
    if (extra && extra.source) {
        bubbleContent += `
            <div class="message-source">
                <i class="fa-solid fa-file-invoice"></i>
                <span>Source: ${extra.source.document} (Page ${extra.source.page})</span>
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
            appendChatMessage("assistant", "<strong>Copilot</strong><br>Sorry, I had trouble processing that request. Please try again.");
            return;
        }
        
        const data = await res.json();
        handleChatResponse(data, payload.message);
    } catch (e) {
        appendChatMessage("assistant", "<strong>Copilot</strong><br>Unable to connect to the CampusPilot service. Verify your server connection.");
    }
}

function handleChatResponse(data, originalMessage) {
    if (data.type === "complaint") {
        // Step 1: Prompt Location picker
        state.awaitingLocation = true;
        state.currentComplaintMessage = originalMessage;
        state.currentComplaintCategory = data.category;
        
        appendChatMessage("assistant", `<strong>Copilot</strong><br>${data.message} Please select the campus location from the picker.`);
        const picker = document.getElementById("location-picker");
        if (picker) {
            picker.classList.remove("hidden");
        }
    } else if (data.type === "ticket_created") {
        // Step 2: Ticket Creation Complete
        appendChatMessage("assistant", `<strong>Copilot</strong><br>${data.message}<br><br>Ticket Reference: <strong>#${data.ticket_id}</strong><br>Department: <strong>${data.department}</strong><br>SLA Estimation: <strong>${data.estimated_resolution}</strong>`);
        refreshDashboard();
        fetchTickets();
    } else if (data.type === "ticket_status") {
        // Ticket Status retrieval
        appendChatMessage("assistant", `<strong>Copilot</strong><br>Ticket Reference: <strong>#${data.ticket_id}</strong><br>Status: <strong>${data.status}</strong><br>Department: <strong>${data.department}</strong><br>SLA Estimation: <strong>${data.estimated_resolution}</strong>`);
    } else {
        // FAQ Answer
        appendChatMessage("assistant", `<strong>Copilot</strong><br>${data.message}`, { source: data.source, confidence: data.confidence });
    }
}

function cancelComplaintFiling() {
    state.awaitingLocation = false;
    const picker = document.getElementById("location-picker");
    if (picker) {
        picker.classList.add("hidden");
    }
    appendChatMessage("assistant", "<strong>Copilot</strong><br>Complaint registration cancelled.");
}

async function submitTicketWithLocation(locationId) {
    const picker = document.getElementById("location-picker");
    if (picker) {
        picker.classList.add("hidden");
    }
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
            
            const totalEl = document.getElementById("metric-total");
            const openEl = document.getElementById("metric-open");
            const resolvedEl = document.getElementById("metric-resolved");
            
            if (totalEl) totalEl.textContent = data.total_tickets;
            if (openEl) openEl.textContent = data.open_tickets;
            if (resolvedEl) resolvedEl.textContent = data.resolved_today;
        }
        
        // Load insights
        const insightsRes = await fetch(`${BACKEND_URL}/api/analytics/insights`);
        if (insightsRes.ok) {
            const insightsData = await insightsRes.json();
            const list = document.getElementById("insights-list");
            if (list && insightsData.insights.length > 0) {
                list.innerHTML = insightsData.insights.map(item => {
                    const severityClass = item.severity.toLowerCase();
                    return `
                        <div class="insight-item ${severityClass}">
                            <div class="insight-header">
                                <span class="insight-title">${item.title}</span>
                                <span class="insight-time">Updated</span>
                            </div>
                            <p class="insight-desc">${item.description}</p>
                        </div>
                    `;
                }).join("");
            }
        }

        // Load Heatmap hotspots from backend and overlay them on the map
        const mapRes = await fetch(`${BACKEND_URL}/api/map/complaints`);
        if (mapRes.ok) {
            const mapData = await mapRes.json();
            populateMapOverlay(mapData.locations, ".map-vector-container", ".map-img");
            populateMapOverlay(mapData.locations, "#big-map-container", ".map-img-big");
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
    if (!tbody) return;
    
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
    const modalId = document.getElementById("modal-ticket-id");
    const modalStatus = document.getElementById("modal-status");
    const modalDept = document.getElementById("modal-dept");
    const modal = document.getElementById("ticket-modal");
    
    if (modalId) modalId.value = id;
    if (modalStatus) modalStatus.value = status;
    if (modalDept && departmentId) {
        modalDept.value = departmentId;
    }
    
    if (modal) {
        modal.classList.remove("hidden");
    }
}

function closeTicketModal() {
    const modal = document.getElementById("ticket-modal");
    if (modal) {
        modal.classList.add("hidden");
    }
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

function toggleChatWindow() {
    const chat = document.getElementById("chat-copilot");
    if (chat) {
        chat.classList.toggle("hidden");
    }
}

// Map Overlay drawing helper
function populateMapOverlay(locations, containerSelector, imgSelector) {
    const container = document.querySelector(containerSelector);
    if (!container) return;
    
    // Keep only the map image
    const mapImg = container.querySelector(imgSelector);
    container.innerHTML = "";
    if (mapImg) {
        container.appendChild(mapImg);
    }
    
    // Coordinates lookup matching the visual map locations
    const coordsLookup = {
        "Academic Block-1": { top: "25%", left: "32%" },
        "Academic Block-2": { top: "58%", left: "53%" },
        "Boys Hostel Blocks": { top: "28%", left: "60%" },
        "Girls Hostel": { top: "56%", left: "32%" },
        "Hostel Office": { top: "70%", left: "63%" },
        "Boys Playground": { top: "52%", left: "80%" },
        "Special Building": { top: "85%", left: "36%" },
        "Lab Complex": { top: "18%", left: "24%" }
    };
    
    locations.forEach(loc => {
        const coords = coordsLookup[loc.name];
        if (coords && loc.total_complaints > 0) {
            const pin = document.createElement("div");
            pin.className = "heatmap-overlay-pin";
            pin.style.top = coords.top;
            pin.style.left = coords.left;
            
            // Select severity color
            if (loc.total_complaints > 15) {
                pin.classList.add("pin-severity-high");
            } else if (loc.total_complaints > 5) {
                pin.classList.add("pin-severity-medium");
            } else {
                pin.classList.add("pin-severity-low");
            }
            
            // Scale pin size depending on active volume
            const size = Math.min(10 + loc.total_complaints * 0.8, 30);
            pin.style.width = `${size}px`;
            pin.style.height = `${size}px`;
            
            // Hover details tooltip
            const tooltip = document.createElement("span");
            tooltip.className = "pin-tooltip";
            tooltip.innerHTML = `<strong>${loc.name}</strong><br>${loc.total_complaints} active issues`;
            pin.appendChild(tooltip);
            
            container.appendChild(pin);
        }
    });
}

function openMapModal() {
    const modal = document.getElementById("map-modal");
    if (modal) {
        modal.classList.remove("hidden");
        // Trigger quick refresh to fetch latest counts
        refreshDashboard();
    }
}

function closeMapModal() {
    const modal = document.getElementById("map-modal");
    if (modal) {
        modal.classList.add("hidden");
    }
}

// Authentication Logic
function checkLoginState() {
    const email = localStorage.getItem("user_email");
    const name = localStorage.getItem("user_name");
    const overlay = document.getElementById("login-overlay");
    const profileName = document.getElementById("profile-name");
    
    if (email && email.toLowerCase().endsWith("@vitbhopal.ac.in")) {
        if (profileName) profileName.textContent = name || "VIT Member";
        if (overlay) overlay.classList.add("hidden");
    } else {
        if (overlay) overlay.classList.remove("hidden");
    }
}

function handleGoogleSignIn(response) {
    try {
        const base64Url = response.credential.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));

        const profile = JSON.parse(jsonPayload);
        const email = profile.email.toLowerCase();
        
        if (email.endsWith("@vitbhopal.ac.in")) {
            localStorage.setItem("user_email", email);
            localStorage.setItem("user_name", profile.name || "VIT Member");
            checkLoginState();
            refreshDashboard();
            fetchTickets();
        } else {
            showLoginError("Access Denied. Only VIT Bhopal email accounts (@vitbhopal.ac.in) are permitted.");
        }
    } catch (e) {
        showLoginError("Google Sign-In decoding failed. Please use local verification bypass.");
    }
}

function submitLocalLogin() {
    const emailInput = document.getElementById("local-email-input");
    const email = emailInput.value.trim().toLowerCase();
    
    if (email.endsWith("@vitbhopal.ac.in")) {
        const mockName = email.split("@")[0].replace(/[._]/g, " ").toUpperCase();
        localStorage.setItem("user_email", email);
        localStorage.setItem("user_name", mockName);
        checkLoginState();
        refreshDashboard();
        fetchTickets();
    } else {
        showLoginError("Access Denied. Only VIT Bhopal email accounts (@vitbhopal.ac.in) are permitted.");
    }
}

function signOutUser() {
    localStorage.removeItem("user_email");
    localStorage.removeItem("user_name");
    checkLoginState();
}

function showLoginError(msg) {
    const errorSpan = document.getElementById("login-error-msg");
    if (errorSpan) {
        errorSpan.textContent = msg;
        errorSpan.classList.remove("hidden");
    }
}
