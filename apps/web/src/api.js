// @ts-check

/** @param {string} path @param {RequestInit} [init] @returns {Promise<any>} */
export async function api(path, init) {
  const res = await fetch(`/api${path}`, init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
  return body
}

/** @type {Record<import('./types.js').Source, string>} */
export const SOURCE_LABEL = { gmail: 'Gmail', chat: 'Google Chat', clickup: 'ClickUp Chat' }

/** @type {Record<import('./types.js').Source, string>} */
export const SOURCE_ICON = { gmail: '✉', chat: '💬', clickup: '◆' }

/** @param {import('./types.js').ActionSource[]} sources @returns {[import('./types.js').Source, number][]} */
export function sourceCounts(sources) {
  /** @type {Record<string, number>} */
  const counts = {}
  for (const s of sources) counts[s.source] = (counts[s.source] ?? 0) + 1
  return /** @type {any} */ (Object.entries(counts))
}

/** @param {string} projectId @param {number | null} actionIndex */
export const projectUrl = (projectId, actionIndex) => `/p/${projectId}${actionIndex === null ? '' : `?action=${actionIndex}`}`

/** @type {Record<import('./types.js').Status, string>} */
export const STATUS_STYLE = {
  behind: 'bg-rose-900/60 hover:bg-rose-900/80 text-rose-100 ring-1 ring-inset ring-rose-800/60',
  reply: 'bg-amber-900/50 hover:bg-amber-900/70 text-amber-100 ring-1 ring-inset ring-amber-800/60',
  ok: 'bg-emerald-900/50 hover:bg-emerald-900/70 text-emerald-100 ring-1 ring-inset ring-emerald-800/60',
}
