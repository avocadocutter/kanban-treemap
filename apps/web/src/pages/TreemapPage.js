// @ts-check
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { hierarchy, treemap, treemapSquarify } from 'd3-hierarchy'
import { api, projectUrl, SOURCE_ICON, SOURCE_LABEL } from '../api.js'

/** @typedef {import('../types.js').ProjectNode} ProjectNode */
/** @typedef {import('../types.js').Action} Action */
/** @typedef {import('../types.js').FeedbackState} FeedbackState */
/** @typedef {import('../types.js').LastRun} LastRun */

const EDGE = { behind: 'border-rose-400/40', reply: 'border-amber-300/40', ok: 'border-emerald-400/30' }
const TAG = { behind: 'text-rose-300 bg-rose-400/10', reply: 'text-amber-200 bg-amber-300/10', ok: 'text-emerald-300 bg-emerald-400/10' }
const TAG_TEXT = { behind: 'at_risk', reply: 'needs_reply', ok: 'on_track' }
const STEP_COLOR = ['bg-sky-500/60', 'bg-violet-500/60', 'bg-teal-500/60']
const OUTCOME = {
  done: { note: 'marked done', cls: 'text-emerald-300' },
  snoozed: { note: 'snoozed until tomorrow', cls: 'text-sky-300' },
  dismissed: { note: 'not an action · the agent will learn from this', cls: 'text-zinc-400' },
}

/** @param {string} date */
function dueLabel(date) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const days = Math.round((Date.parse(`${date}T00:00:00`) - today.getTime()) / 86400000)
  if (Number.isNaN(days)) return date
  if (days < 0) return `${-days}d late`
  if (days === 0) return 'today'
  if (days === 1) return 'tomorrow'
  return `in ${days}d`
}

export default function TreemapPage() {
  const [data, setData] = useState(
    /** @type {{ projects: ProjectNode[], google_enabled: boolean, google_connected: boolean, last_run: LastRun | null } | null} */ (null),
  )
  const [syncing, setSyncing] = useState(false)
  const [message, setMessage] = useState('')

  const load = () => api('/treemap').then(setData).catch((e) => setMessage(e.message))
  useEffect(() => { load() }, [])

  async function sync() {
    setSyncing(true)
    setMessage('')
    try {
      const r = await api('/sync', { method: 'POST' })
      if (r.warnings.length) setMessage(r.warnings.join('  ⚠ '))
      await load()
    } catch (e) {
      setMessage(e.message)
    } finally {
      setSyncing(false)
    }
  }

  /** @param {string} projectId @param {string} text @param {FeedbackState | null} state */
  async function setFeedback(projectId, text, state) {
    setData((d) => d && {
      ...d,
      projects: d.projects.map((p) => p.id !== projectId ? p : {
        ...p,
        actions: p.actions.map((a) => (a.text === text ? { ...a, feedback: state } : a)),
      }),
    })
    try {
      await api('/actions/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId, text, state }),
      })
    } catch (e) {
      setMessage(e.message)
      load()
    }
  }

  return (
    <div className="flex h-screen flex-col bg-[#09090b] text-[13px] text-zinc-200">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-zinc-800/80 px-4 py-2.5">
        <span className="font-semibold">Focus</span>
        {data?.last_run && (
          <span className="font-mono text-[11px] text-zinc-500">
            {data.last_run.model} · synced {new Date(data.last_run.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
        <RunTimeline run={data?.last_run ?? null} />
        {data?.google_enabled && !data.google_connected && (
          <a href="/api/auth/google" className="rounded-md bg-zinc-100 px-2.5 py-1 font-medium text-zinc-900">Connect Google</a>
        )}
        <button
          onClick={sync}
          disabled={syncing}
          className="rounded-md border border-zinc-700 px-2.5 py-1 text-zinc-300 hover:bg-zinc-800 disabled:opacity-40"
        >
          {syncing ? 'Syncing…' : 'Sync'}
        </button>
      </header>
      {message && <p className="border-b border-zinc-800/80 px-4 py-1.5 text-zinc-300">{message}</p>}
      {data && <Treemap projects={data.projects} onFeedback={setFeedback} />}
    </div>
  )
}

/** @param {{ run: LastRun | null }} props */
function RunTimeline({ run }) {
  if (!run) return <div className="flex-1 font-mono text-[11px] text-zinc-600">no sync yet</div>
  const total = run.steps.reduce((s, x) => s + x.seconds, 0) || 1
  return (
    <div className="flex min-w-[320px] flex-1 items-center gap-1" title="last sync">
      {run.steps.map((s, i) => (
        <div key={s.name} className="min-w-0" style={{ flex: Math.max(s.seconds / total, 0.08) }}>
          <div className={`h-1.5 rounded-sm ${STEP_COLOR[i % STEP_COLOR.length]}`} />
          <div className="truncate font-mono text-[10px] text-zinc-500">
            {s.name} <span className="text-zinc-600">{s.seconds.toFixed(1)}s · {s.detail}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

/** @param {{ projects: ProjectNode[], onFeedback: (projectId: string, text: string, state: FeedbackState | null) => void }} props */
function Treemap({ projects, onFeedback }) {
  const ref = useRef(/** @type {HTMLDivElement | null} */ (null))
  const [size, setSize] = useState({ w: 0, h: 0 })

  useEffect(() => {
    const obs = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }))
    obs.observe(ref.current)
    return () => obs.disconnect()
  }, [])

  const root = hierarchy(/** @type {any} */ ({ children: projects }))
    .sum((d) => d.value ?? 0)
    .sort((a, b) => b.value - a.value)
  const leaves = treemap().size([size.w, size.h]).paddingInner(6).tile(treemapSquarify)(root).leaves()

  return (
    <div ref={ref} className="relative m-3 flex-1">
      {leaves.map((leaf) => (
        <ProjectBox
          key={leaf.data.id}
          p={leaf.data}
          style={{ left: leaf.x0, top: leaf.y0, width: leaf.x1 - leaf.x0, height: leaf.y1 - leaf.y0 }}
          roomy={leaf.x1 - leaf.x0 > 260 && leaf.y1 - leaf.y0 > 170}
          onFeedback={onFeedback}
        />
      ))}
    </div>
  )
}

/** @param {{ value: number | null }} props */
function Confidence({ value }) {
  if (value === null || value === undefined) return null
  const pct = Math.round(value * 100)
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 font-mono text-[10px] text-zinc-500" title="model confidence">
      <span className="relative h-1 w-10 overflow-hidden rounded-full bg-zinc-800">
        <span className="absolute inset-y-0 left-0 rounded-full bg-sky-400/70" style={{ width: `${pct}%` }} />
      </span>
      {pct}%
    </span>
  )
}

/**
 * @param {{ p: ProjectNode, style: import('react').CSSProperties, roomy: boolean,
 *   onFeedback: (projectId: string, text: string, state: FeedbackState | null) => void }} props
 */
function ProjectBox({ p, style, roomy, onFeedback }) {
  const [openIndex, setOpenIndex] = useState(/** @type {number | null} */ (null))
  const open = p.actions.filter((a) => !a.feedback).length

  return (
    <section style={style} className={`absolute flex flex-col overflow-hidden rounded-lg border bg-zinc-900/50 ${EDGE[p.status]}`}>
      <Link to={projectUrl(p.id, null)} title={p.description} className="flex items-center gap-2 px-3 pt-2.5 hover:text-white">
        <span className="min-w-0 flex-1 truncate font-semibold text-zinc-100">{p.name}</span>
        <span className={`shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] ${TAG[p.status]}`}>{TAG_TEXT[p.status]}</span>
      </Link>

      {roomy && p.why && (
        <div className="mx-3 mt-2 rounded-md border border-zinc-800 bg-black/30 px-2.5 py-1.5">
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wide text-zinc-500">
            reasoning <Confidence value={p.confidence} />
            {p.latency !== null && <span className="ml-auto normal-case">{p.latency}s</span>}
          </div>
          <p className="mt-0.5 text-[12px] leading-snug text-zinc-300">{p.why}</p>
        </div>
      )}

      {!roomy && <div className="px-3 font-mono text-[10px] text-zinc-500">{open} open · {p.count} threads</div>}

      <ol className="mt-2 min-h-0 flex-1 overflow-y-auto px-1.5 pb-2">
        {p.actions.length === 0 && <li className="px-2 text-zinc-600">No actions inferred</li>}
        {p.actions.map((a, i) => (
          <ActionRow
            key={`${i}:${a.text}`}
            action={a}
            rank={i + 1}
            projectId={p.id}
            roomy={roomy}
            open={openIndex === i}
            onToggle={() => setOpenIndex(openIndex === i ? null : i)}
            onFeedback={(state) => onFeedback(p.id, a.text, state)}
          />
        ))}
      </ol>
    </section>
  )
}

/**
 * @param {{ action: Action, rank: number, projectId: string, roomy: boolean, open: boolean,
 *   onToggle: () => void, onFeedback: (state: FeedbackState | null) => void }} props
 */
function ActionRow({ action: a, rank, projectId, roomy, open, onToggle, onFeedback }) {
  if (a.feedback) {
    const o = OUTCOME[a.feedback]
    return (
      <li className="flex items-center gap-2 px-1.5 py-1 text-zinc-600">
        <span className="w-5 shrink-0 text-right font-mono text-[10px]">{rank}</span>
        <span className="min-w-0 flex-1 truncate line-through">{a.text}</span>
        {roomy && <span className={`shrink-0 truncate font-mono text-[10px] ${o.cls}`}>{o.note}</span>}
        <button onClick={() => onFeedback(null)} className="shrink-0 rounded px-1.5 font-mono text-[10px] text-zinc-400 hover:bg-white/5 hover:text-zinc-200">
          undo
        </button>
      </li>
    )
  }

  return (
    <li className={`group rounded-md ${open ? 'bg-zinc-800/60' : 'hover:bg-zinc-800/30'}`}>
      <div className="flex items-center gap-2 px-1.5 py-1">
        <span className="w-5 shrink-0 text-right font-mono text-[10px] text-zinc-500">{rank}</span>
        <button onClick={onToggle} className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <span className="min-w-0 flex-1 truncate">{a.text}</span>
          <span className="flex shrink-0 items-center gap-2 group-focus-within:hidden group-hover:hidden">
            {roomy && <Confidence value={a.confidence} />}
            {a.due && <span className="font-mono text-[10px] text-zinc-400">{dueLabel(a.due)}</span>}
            <span className="font-mono text-[10px] text-zinc-500">{a.sources.length} src {open ? '▾' : '▸'}</span>
          </span>
        </button>
        <span className="hidden shrink-0 items-center gap-1 group-focus-within:flex group-hover:flex">
          <TriageButton onClick={() => onFeedback('done')} className="hover:bg-emerald-400/15 hover:text-emerald-200">✓ Done</TriageButton>
          <TriageButton onClick={() => onFeedback('snoozed')} className="hover:bg-sky-400/15 hover:text-sky-200">Snooze</TriageButton>
          <TriageButton onClick={() => onFeedback('dismissed')} className="hover:bg-white/10 hover:text-zinc-100" title="Not an action: teach the agent">
            Not an action
          </TriageButton>
        </span>
      </div>
      {open && (
        <ul className="space-y-1 px-7 pb-2">
          {a.sources.length === 0 && <li className="text-[12px] text-zinc-500">No linked thread</li>}
          {a.sources.map((s) => (
            <li key={s.item_id} className="text-[12px]">
              <span className="font-mono text-[10px] text-zinc-500" title={SOURCE_LABEL[s.source]}>{SOURCE_ICON[s.source]} {s.title}</span>
              {s.quote && <blockquote className="border-l-2 border-sky-500/40 pl-2 italic text-zinc-300">“{s.quote}”</blockquote>}
            </li>
          ))}
          <li className="pt-0.5">
            <Link to={projectUrl(projectId, rank - 1)} className="font-mono text-[10px] text-sky-400 hover:underline">open conversation ↗</Link>
          </li>
        </ul>
      )}
    </li>
  )
}

/** @param {{ children: import('react').ReactNode, className: string, onClick: () => void, title?: string }} props */
function TriageButton({ children, className, ...props }) {
  return (
    <button
      {...props}
      className={`rounded border border-zinc-700 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300 transition-colors duration-100 ease-out ${className}`}
    >
      {children}
    </button>
  )
}
