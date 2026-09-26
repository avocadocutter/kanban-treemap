// @ts-check

/** @param {string} path @param {RequestInit} [init] @returns {Promise<any>} */
export async function api(path, init) {
  const res = await fetch(`/api${path}`, init)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail ?? `${res.status} ${res.statusText}`)
  return body
}

/** @type {Record<import('./types.js').Status, string>} */
export const STATUS_STYLE = {
  behind: 'bg-red-600 hover:bg-red-500',
  reply: 'bg-amber-500 hover:bg-amber-400 text-zinc-950',
  ok: 'bg-emerald-700 hover:bg-emerald-600',
}
