// openf1.js
const fetch = require('node-fetch');
const API_BASE = 'https://api.openf1.org/v1';

async function get(endpoint, params = {}) {
    const urlParams = new URLSearchParams(params);
    const url = `${API_BASE}/${endpoint}?${urlParams.toString()}`;
    try {
        const response = await fetch(url);
        if (!response.ok) {
            console.error(`API Error ${response.status}: ${await response.text()}`);
            return [];
        }
        return response.json();
    } catch (error) {
        console.error(`[OpenF1 Client Error] Fetch failed for ${url}:`, error);
        return [];
    }
}

async function getSessionMeta(session_key) {
    const sessions = await get('sessions', { session_key });
    return sessions.length > 0 ? sessions[0] : null;
}

async function getPositions(session_key, from_iso, to_iso) {
    return get('location', { session_key, 'date>': from_iso, 'date<': to_iso });
}

module.exports = { getSessionMeta, getPositions };