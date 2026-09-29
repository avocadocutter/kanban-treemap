// @ts-check
/** @typedef {'behind' | 'reply' | 'ok'} Status */
/** @typedef {'gmail' | 'chat' | 'clickup'} Source */
/** @typedef {{ text: string, item_id: string | null, source: Source | null, due: string | null }} Action */
/**
 * @typedef {{ id: string, name: string, description: string, importance: number, deadline: string | null,
 *   count: number, overdue: number, replies: number, status: Status, value: number, actions: Action[] }} ProjectNode
 */
/**
 * @typedef {{ id: string, source: Source, title: string, body: string | null, summary: string | null, url: string,
 *   people: string, updated_at: string, due_at: string | null, needs_reply: number, overdue: boolean }} Item
 */
export {}
