// -------------------------------------------------------------
// CampusPilot Premium App Logic Engine
// Handles API calls, tab navigation, modals, and dynamic data state
// -------------------------------------------------------------

const BACKEND_URL = window.location.origin.includes("localhost") || window.location.origin.includes("127.0.0.1")
    ? "http://localhost:8000"
    : window.location.origin;

// Global Data Store
let state = {
    locations: [],
    departments: [],
    awaitingLocation: false,
    currentComplaintMessage: "",
    currentComplaintCategory: "",
    selectedMapCategory: "ALL",
    mapLocations: [],
    isLiveSyncActive: true,
    liveSyncInterval: null
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
    
    // Start live sync interval loop
    startLiveSync();
});

// 1. Navigation Tab Controller
function initNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");
            switchTab(targetTab);
        });
    });
}

function switchTab(targetTab) {
    const navItems = document.querySelectorAll(".nav-item");
    const views = document.querySelectorAll(".view-content");
    const titleEl = document.getElementById("view-title");

    navItems.forEach(nav => {
        if (nav.getAttribute("data-tab") === targetTab) {
            nav.classList.add("active");
        } else {
            nav.classList.remove("active");
        }
    });

    views.forEach(view => {
        if (view.id === `${targetTab}-view`) {
            view.classList.add("active");
        } else {
            view.classList.remove("active");
        }
    });

    // Update Title
    if (titleEl) {
        let cleanTitle = targetTab.replace("-", " ");
        titleEl.textContent = cleanTitle.charAt(0).toUpperCase() + cleanTitle.slice(1);
    }

    // Screen specific loads
    if (targetTab === "dashboard") {
        refreshDashboard();
    } else if (targetTab === "tickets") {
        fetchTickets();
    } else if (targetTab === "my-tickets") {
        fetchStudentTickets();
    } else if (targetTab === "analytics") {
        renderAnalyticsBars();
    }
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
            
            // Populate Student Raise Ticket dropdown
            const studentLocSelect = document.getElementById("student-location");
            if (studentLocSelect) {
                studentLocSelect.innerHTML = state.locations.map(l => 
                    `<option value="${l.id}">${l.name}</option>`
                ).join("");
            }
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
            state.mapLocations = mapData.locations;
            populateMapOverlay(state.mapLocations, ".map-vector-container", ".map-img");
            populateMapOverlay(state.mapLocations, "#big-map-container", ".map-img-big");
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
        "Lab Complex": { top: "18%", left: "24%" },
        "Mayuri Mess": { top: "42%", left: "45%" }
    };
    
    locations.forEach(loc => {
        const coords = coordsLookup[loc.name];
        const selectedCat = state.selectedMapCategory || 'ALL';
        
        let count = 0;
        if (selectedCat === 'ALL') {
            count = loc.total_complaints;
        } else {
            count = loc.categories ? (loc.categories[selectedCat] || 0) : 0;
        }

        if (coords && count > 0) {
            const pin = document.createElement("div");
            pin.className = "heatmap-overlay-pin";
            pin.style.top = coords.top;
            pin.style.left = coords.left;
            
            // Select severity color
            if (count > 15) {
                pin.classList.add("pin-severity-high");
            } else if (count > 5) {
                pin.classList.add("pin-severity-medium");
            } else {
                pin.classList.add("pin-severity-low");
            }
            
            // Scale pin size depending on active volume
            const size = Math.min(10 + count * 1.5, 32);
            pin.style.width = `${size}px`;
            pin.style.height = `${size}px`;
            
            // Hover details tooltip
            const tooltip = document.createElement("span");
            tooltip.className = "pin-tooltip";
            tooltip.innerHTML = `<strong>${loc.name}</strong><br>${count} active ${selectedCat !== 'ALL' ? selectedCat.replace('_', ' ') : ''} issues`;
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
state.selectedLoginRole = "STUDENT";

function selectLoginRole(role) {
    state.selectedLoginRole = role;
    const btnStudent = document.getElementById("btn-role-student");
    const btnAdmin = document.getElementById("btn-role-admin");
    const instructions = document.getElementById("login-instructions-text");
    const localInput = document.getElementById("local-email-input");
    
    if (role === "STUDENT") {
        if (btnStudent) {
            btnStudent.style.background = "var(--primary)";
            btnStudent.style.color = "white";
        }
        if (btnAdmin) {
            btnAdmin.style.background = "none";
            btnAdmin.style.color = "var(--text-muted)";
        }
        if (instructions) {
            instructions.textContent = "Please sign in using your official student email account to file complaints and track issues.";
        }
        if (localInput) {
            localInput.placeholder = "student@vitbhopal.ac.in";
        }
    } else {
        if (btnAdmin) {
            btnAdmin.style.background = "var(--primary)";
            btnAdmin.style.color = "white";
        }
        if (btnStudent) {
            btnStudent.style.background = "none";
            btnStudent.style.color = "var(--text-muted)";
        }
        if (instructions) {
            instructions.textContent = "Please sign in using your official administrator account to access the command center and manage telemetry.";
        }
        if (localInput) {
            localInput.placeholder = "admin@vitbhopal.ac.in";
        }
    }
}

function checkLoginState() {
    const email = localStorage.getItem("user_email");
    const name = localStorage.getItem("user_name");
    const role = localStorage.getItem("user_role") || "STUDENT";
    const overlay = document.getElementById("login-overlay");
    const profileName = document.getElementById("profile-name");
    
    if (email && email.toLowerCase().endsWith("@vitbhopal.ac.in")) {
        if (profileName) profileName.textContent = `${name || "VIT Member"} (${role})`;
        if (overlay) overlay.classList.add("hidden");
        
        // Hide/Show items based on role
        document.querySelectorAll(".admin-only").forEach(el => {
            if (role === "ADMIN") el.classList.remove("hidden");
            else el.classList.add("hidden");
        });
        document.querySelectorAll(".student-only").forEach(el => {
            if (role === "STUDENT") el.classList.remove("hidden");
            else el.classList.add("hidden");
        });

        // Hide chatbot window and fab for admin
        const chatWindow = document.getElementById("chat-copilot");
        const chatFab = document.getElementById("chat-fab");
        if (role === "ADMIN") {
            if (chatWindow) chatWindow.classList.add("hidden");
            if (chatFab) chatFab.classList.add("hidden");
            
            // If currently viewing a student page, swap to dashboard
            const activeView = document.querySelector(".view-content.active");
            if (!activeView || activeView.classList.contains("student-only")) {
                switchTab("dashboard");
            }
        } else {
            // Student: Default chatbot minimized FAB
            if (chatWindow && !chatWindow.classList.contains("hidden")) {
                // Keep open
            } else if (chatFab) {
                chatFab.classList.remove("hidden");
            }
            
            // If currently viewing an admin page, swap to raise-ticket
            const activeView = document.querySelector(".view-content.active");
            if (!activeView || activeView.classList.contains("admin-only")) {
                switchTab("raise-ticket");
            }
        }
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
            localStorage.setItem("user_role", state.selectedLoginRole || "STUDENT");
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
        localStorage.setItem("user_role", state.selectedLoginRole || "STUDENT");
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
    localStorage.removeItem("user_role");
    
    // Hide chat windows on logout
    const chatWindow = document.getElementById("chat-copilot");
    const chatFab = document.getElementById("chat-fab");
    if (chatWindow) chatWindow.classList.add("hidden");
    if (chatFab) chatFab.classList.add("hidden");
    
    checkLoginState();
}

function showLoginError(msg) {
    const errorSpan = document.getElementById("login-error-msg");
    if (errorSpan) {
        errorSpan.textContent = msg;
        errorSpan.classList.remove("hidden");
    }
}

// 10/10 Hackathon Upgrade Interactions
function filterMapCategory(category) {
    state.selectedMapCategory = category;
    
    // Highlight active filter pill
    const badges = document.querySelectorAll(".map-filter-badge");
    badges.forEach(badge => {
        if (badge.getAttribute("onclick").includes(`'${category}'`)) {
            badge.style.background = "var(--primary)";
            badge.style.color = "white";
            badge.style.borderColor = "var(--primary)";
        } else {
            badge.style.background = "var(--bg-card)";
            badge.style.color = "var(--text-muted)";
            badge.style.borderColor = "var(--border-color)";
        }
    });

    // Re-render map layers
    populateMapOverlay(state.mapLocations, ".map-vector-container", ".map-img");
    populateMapOverlay(state.mapLocations, "#big-map-container", ".map-img-big");
}

function sendQuickStarter(text) {
    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("btn-send");
    
    // Check if chat drawer is visible. If not, open it
    const chatDrawer = document.getElementById("chat-copilot");
    if (chatDrawer && chatDrawer.classList.contains("hidden")) {
        toggleChatWindow();
    }
    
    if (chatInput && sendBtn) {
        chatInput.value = text;
        sendBtn.click();
    }
}

async function exportTicketsCSV() {
    try {
        const res = await fetch(`${BACKEND_URL}/api/tickets`);
        if (!res.ok) throw new Error();
        const tickets = await res.json();
        
        // Compile CSV contents
        let csvContent = "data:text/csv;charset=utf-8,";
        csvContent += "Ticket ID,Title,Description,Status,Priority,Department,Location,Created At\n";
        
        tickets.forEach(t => {
            const row = [
                t.id,
                `"${t.title.replace(/"/g, '""')}"`,
                `"${t.description.replace(/"/g, '""')}"`,
                t.status,
                t.priority,
                t.department ? t.department.name : "Unassigned",
                t.location ? t.location.name : "Unassigned",
                t.created_at
            ].join(",");
            csvContent += row + "\n";
        });
        
        // Direct browser file download trigger
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `campuspilot_export_${Date.now()}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (e) {
        alert("Failed to export tickets list. Backend connection error.");
    }
}

function startLiveSync() {
    if (state.liveSyncInterval) clearInterval(state.liveSyncInterval);
    
    state.liveSyncInterval = setInterval(() => {
        if (state.isLiveSyncActive) {
            refreshDashboard();
            fetchTickets();
        }
    }, 10000); // 10s auto-refresh heartbeat
}

function toggleLiveSync() {
    state.isLiveSyncActive = !state.isLiveSyncActive;
    const badge = document.getElementById("live-sync-toggle");
    const dot = badge ? badge.querySelector(".sync-pulse-dot") : null;
    
    if (badge) {
        if (state.isLiveSyncActive) {
            badge.style.color = "#10b981";
            badge.style.background = "rgba(16, 185, 129, 0.08)";
            badge.style.borderColor = "rgba(16, 185, 129, 0.2)";
            if (dot) {
                dot.style.backgroundColor = "#10b981";
                dot.style.animation = "syncPulse 1.5s infinite";
            }
        } else {
            badge.style.color = "var(--text-muted)";
            badge.style.background = "rgba(255, 255, 255, 0.02)";
            badge.style.borderColor = "var(--border-color)";
            if (dot) {
                dot.style.backgroundColor = "var(--text-muted)";
                dot.style.animation = "none";
            }
        }
    }
}

// Student Ticket Filing & Verification Helpers
function getUserIdFromEmail(email) {
    if (!email) return 101;
    let hash = 0;
    for (let i = 0; i < email.length; i++) {
        hash += email.charCodeAt(i);
    }
    return (hash % 1000) + 1;
}

async function submitStudentComplaint(event) {
    event.preventDefault();
    const title = document.getElementById("student-title").value.trim();
    const desc = document.getElementById("student-desc").value.trim();
    const category = document.getElementById("student-category").value;
    const locationId = document.getElementById("student-location").value;
    const priority = document.getElementById("student-priority").value;
    
    const email = localStorage.getItem("user_email") || "student@vitbhopal.ac.in";
    const userId = getUserIdFromEmail(email);

    try {
        // Step 1: Create Complaint record
        const compRes = await fetch(`${BACKEND_URL}/api/complaints`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_id: userId,
                location_id: parseInt(locationId),
                category: category,
                description: desc,
                priority: priority
            })
        });

        if (!compRes.ok) throw new Error("Complaint submission failed.");
        const complaintData = await compRes.json();

        // Step 2: Spawn Ticket record
        const tickRes = await fetch(`${BACKEND_URL}/api/tickets`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                complaint_id: complaintData.id,
                title: title,
                description: desc
            })
        });

        if (!tickRes.ok) throw new Error("Ticket assignment failed.");
        
        // Success Alert
        alert(`Complaint filed successfully! Ticket ID #${complaintData.id} has been registered.`);
        
        // Clear form inputs
        document.getElementById("student-complaint-form").reset();
        
        // Dynamic switch to My Tickets tab view
        switchTab("my-tickets");
    } catch (e) {
        alert(e.message || "Connection failed. Please retry.");
    }
}

async function fetchStudentTickets() {
    const tableBody = document.getElementById("student-tickets-table-body");
    const countBadge = document.getElementById("student-ticket-count");
    const email = localStorage.getItem("user_email");
    const userId = getUserIdFromEmail(email);

    try {
        const res = await fetch(`${BACKEND_URL}/api/tickets`);
        if (res.ok) {
            const tickets = await res.json();
            
            // Filter tickets belonging to the current user's generated ID
            const myTickets = tickets.filter(t => t.complaint && t.complaint.user_id === userId);
            
            if (countBadge) countBadge.textContent = `${myTickets.length} Tickets`;
            
            if (!tableBody) return;
            if (myTickets.length === 0) {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 30px;">
                            <i class="fa-solid fa-folder-open" style="font-size: 24px; margin-bottom: 8px; display: block;"></i>
                            No complaints logged yet under this account.
                        </td>
                    </tr>`;
                return;
            }
            
            tableBody.innerHTML = myTickets.map(t => {
                let priorityClass = t.priority.toLowerCase();
                let statusClass = t.status.toLowerCase().replace('_', '-');
                return `
                    <tr>
                        <td>#${t.id}</td>
                        <td style="font-weight: 600; color: white;">${t.title}</td>
                        <td><span class="badge category-tag">${t.complaint ? t.complaint.category.replace('_', ' ') : 'other'}</span></td>
                        <td>${t.location ? t.location.name : 'Unassigned'}</td>
                        <td><span class="badge priority-${priorityClass}">${t.priority}</span></td>
                        <td><span class="badge status-${statusClass}">${t.status}</span></td>
                        <td>${new Date(t.created_at).toLocaleDateString()}</td>
                    </tr>`;
            }).join("");
        }
    } catch (e) {
        console.error("Failed loading student tickets:", e);
    }
}

// Chatbot Minimizing Controls
function minimizeChatWindow() {
    const chatWindow = document.getElementById("chat-copilot");
    const chatFab = document.getElementById("chat-fab");
    
    if (chatWindow) chatWindow.classList.add("hidden");
    if (chatFab) chatFab.classList.remove("hidden");
}

function restoreChatWindow() {
    const chatWindow = document.getElementById("chat-copilot");
    const chatFab = document.getElementById("chat-fab");
    
    if (chatFab) chatFab.classList.add("hidden");
    if (chatWindow) chatWindow.classList.remove("hidden");
}

// Render workload metrics graphs in Analytics panel
async function renderAnalyticsBars() {
    const catContainer = document.getElementById("analytics-category-bars");
    const deptContainer = document.getElementById("analytics-department-bars");
    if (!catContainer || !deptContainer) return;

    try {
        const res = await fetch(`${BACKEND_URL}/api/tickets`);
        if (!res.ok) return;
        const tickets = await res.json();

        // Calculate counts
        const catMap = {};
        const deptMap = {};
        tickets.forEach(t => {
            const catName = t.complaint ? t.complaint.category.replace('_', ' ').toUpperCase() : 'OTHER';
            const deptName = t.department ? t.department.name : 'UNASSIGNED';
            catMap[catName] = (catMap[catName] || 0) + 1;
            deptMap[deptName] = (deptMap[deptName] || 0) + 1;
        });

        // Generate category workload bars html
        const catEntries = Object.entries(catMap).sort((a,b) => b[1] - a[1]);
        const maxCatVal = catEntries.length > 0 ? catEntries[0][1] : 1;
        catContainer.innerHTML = catEntries.map(([name, val]) => {
            const pct = (val / maxCatVal) * 100;
            return `
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px; color: var(--text-muted);">
                        <span>${name}</span>
                        <span style="font-weight: 700; color: white;">${val} active</span>
                    </div>
                    <div style="width: 100%; height: 8px; background: rgba(255,255,255,0.04); border-radius: 4px; overflow: hidden;">
                        <div style="width: ${pct}%; height: 100%; background: linear-gradient(90deg, var(--primary), var(--secondary)); border-radius: 4px;"></div>
                    </div>
                </div>`;
        }).join("");

        // Generate department workload bars html
        const deptEntries = Object.entries(deptMap).sort((a,b) => b[1] - a[1]);
        const maxDeptVal = deptEntries.length > 0 ? deptEntries[0][1] : 1;
        deptContainer.innerHTML = deptEntries.map(([name, val]) => {
            const pct = (val / maxDeptVal) * 100;
            return `
                <div style="margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px; color: var(--text-muted);">
                        <span>${name}</span>
                        <span style="font-weight: 700; color: white;">${val} tickets</span>
                    </div>
                    <div style="width: 100%; height: 8px; background: rgba(255,255,255,0.04); border-radius: 4px; overflow: hidden;">
                        <div style="width: ${pct}%; height: 100%; background: linear-gradient(90deg, #10b981, #3b82f6); border-radius: 4px;"></div>
                    </div>
                </div>`;
        }).join("");
    } catch (e) {
        console.error("Error drawing analytics charts:", e);
    }
}
