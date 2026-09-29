// @ts-check
/** @typedef {'behind' | 'reply' | 'ok'} Status */
/** @typedef {'gmail' | 'chat' | 'clickup'} Source */
/** @typedef {'done' | 'snoozed' | 'dismissed'} FeedbackState */
/** @typedef {{ item_id: string, source: Source, title: string, quote: string }} ActionSource */
/**
 * @typedef {{ text: string, due: string | null, confidence: number | null, feedback: FeedbackState | null,
 *   sources: ActionSource[] }} Action
 */
/**
 * @typedef {{ id: string, name: string, description: string, importance: number, deadline: string | null,
 *   count: number, overdue: number, replies: number, status: Status, value: number, actions: Action[],
 *   why: string, confidence: number | null, latency: number | null }} ProjectNode
 */
/** @typedef {{ name: string, seconds: number, detail: string }} RunStep */
/** @typedef {{ at: string, model: string, steps: RunStep[] }} LastRun */
/**
 * @typedef {{ id: string, source: Source, title: string, body: string | null, summary: string | null, url: string,
 *   people: string, updated_at: string, due_at: string | null, needs_reply: number, overdue: boolean }} Item
 */
export {}
