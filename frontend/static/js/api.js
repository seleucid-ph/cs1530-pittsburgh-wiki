// View Map, View Pages, Search & Filter, Login Attempt, Content Submission, Moderator UI

const BASE_URL = "";

async function request(path, options = {}) {
    try {
        const res = await fetch(`${BASE_URL}${path}`, options);
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return await res.json();
    } catch (err) {
        console.error(`API error on ${path}:`, err);
        return { error: err.message };
    }
}

// view map
async function getMapLocations(neighborhood = "") {
    const q = neighborhood ? `?neighborhood=${encodeURIComponent(neighborhood)}` : "";
    return request(`/api/map${q}`);
}

// view pages
async function getPage(pageId) {
    return request(`/api/pages/${pageId}`);
}

async function getPages() {
    return request(`/api/pages`);
}

// search and filter
async function searchEntries(keyword = "", category = "", neighborhood = "") {
    const params = new URLSearchParams();
    if (keyword) params.append("q", keyword);
    if (category) params.append("category", category);
    if (neighborhood) params.append("neighborhood", neighborhood);
    return request(`/api/search?${params}`);
}

// login attempt
async function login(username, password) {
    return request(`/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
    });
}

async function signup(username, email, password) {
    return request(`/api/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, email, password })
    });
}

// content submission
async function submitContent(entryData) {
    return request(`/api/submissions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entryData)
    });
}

// moderator ui
async function getPendingSubmissions() {
    return request(`/api/moderation/pending`);
}

async function approveSubmission(submissionId) {
    return request(`/api/moderation/${submissionId}/approve`, { method: "POST" });
}

async function rejectSubmission(submissionId) {
    return request(`/api/moderation/${submissionId}/reject`, { method: "POST" });
}

// Export for both script tags and module imports
if (typeof module !== "undefined" && module.exports) {
    module.exports = {
        getMapLocations, getPage, getPages, searchEntries,
        login, signup, submitContent,
        getPendingSubmissions, approveSubmission, rejectSubmission
    };
}