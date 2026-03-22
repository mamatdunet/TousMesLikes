const BASE = '/api';

export async function uploadFile(file, platform) {
  const form = new FormData();
  form.append('file', file);
  form.append('platform', platform);
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

export async function getItems({ platform, category, month, sort, page = 1, perPage = 50 } = {}) {
  const params = new URLSearchParams({ page, per_page: perPage });
  if (platform) params.set('platform', platform);
  if (category) params.set('category', category);
  if (month) params.set('month', month);
  if (sort) params.set('sort', sort);
  const res = await fetch(`${BASE}/items?${params}`);
  return res.json();
}

export async function searchItems(q, { platform, page = 1 } = {}) {
  const params = new URLSearchParams({ q, page });
  if (platform) params.set('platform', platform);
  const res = await fetch(`${BASE}/search?${params}`);
  return res.json();
}

export async function semanticSearch(q, { platform, n = 20 } = {}) {
  const params = new URLSearchParams({ q, n });
  if (platform) params.set('platform', platform);
  const res = await fetch(`${BASE}/semantic-search?${params}`);
  return res.json();
}

export async function getImportHistory() {
  const res = await fetch(`${BASE}/import-history`);
  return res.json();
}

export async function getStats() {
  const res = await fetch(`${BASE}/stats`);
  return res.json();
}

export async function deleteAll() {
  const res = await fetch(`${BASE}/items`, { method: 'DELETE' });
  return res.json();
}

export async function getIndexingStatus() {
  const res = await fetch(`${BASE}/indexing-status`);
  return res.json();
}

export async function runCategorize() {
  const res = await fetch(`${BASE}/categorize`, { method: 'POST' });
  return res.json();
}

export async function getCategorizeStatus() {
  const res = await fetch(`${BASE}/categorize-status`);
  return res.json();
}

export async function getTopics() {
  const res = await fetch(`${BASE}/topics`);
  return res.json();
}

export async function getTopicGraph(minCount = 20, minLink = 5) {
  const res = await fetch(`${BASE}/topic-graph?min_count=${minCount}&min_link=${minLink}`);
  return res.json();
}

export async function getCollections(limit = 12) {
  const res = await fetch(`${BASE}/collections?limit=${limit}`);
  return res.json();
}

export async function getOllamaStatus() {
  const res = await fetch(`${BASE}/ollama/status`);
  return res.json();
}

export async function ragChat(query) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Chat failed');
  }
  return res.json();
}
