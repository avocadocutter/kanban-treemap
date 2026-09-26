// @ts-check
/** @typedef {'behind' | 'reply' | 'ok'} Status */
/**
 * @typedef {{ id: string, name: string, description: string, importance: number, deadline: string | null,
 *   count: number, overdue: number, replies: number, status: Status, value: number }} ProjectNode
 */
/**
 * @typedef {{ id: string, source: 'gmail' | 'chat' | 'clickup', title: string, summary: string | null, url: string,
 *   people: string, updated_at: string, due_at: string | null, needs_reply: number, overdue: boolean }} Item
 */
export {}
