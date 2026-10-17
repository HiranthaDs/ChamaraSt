const configuredApi = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const configuredIsLocal = ['localhost', '127.0.0.1'].includes(new URL(configuredApi).hostname);
export const API_BASE = (configuredIsLocal && !['localhost', '127.0.0.1'].includes(location.hostname)
  ? location.origin
  : configuredApi).replace(/\/$/, '');

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Backend request failed (${response.status}).`);
  return body;
}

export const fetchERPState = () => request('/api/state');
let saveQueue = Promise.resolve();
export const saveERPState = (state, actor = null) => {
  const snapshot = structuredClone(state);
  const headers = actor ? { 'X-Demo-Role': actor.role || '', 'X-Demo-Employee-Id': actor.id || '' } : {};
  const saving = saveQueue.catch(() => {}).then(() => request('/api/state', { method: 'PUT', headers, body: JSON.stringify({ state: snapshot }) }));
  saveQueue = saving.then(() => undefined, () => undefined);
  return saving;
};
