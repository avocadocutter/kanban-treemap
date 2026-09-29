// @ts-check
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { hierarchy, treemap, treemapSquarify } from 'd3-hierarchy'
import { api, projectUrl, SOURCE_SHORT, STATUS_STYLE } from '../api.js'

/** @typedef {import('../types.js').ProjectNode} ProjectNode */

export default function TreemapPage() {
  const [data, setData] = useState(/** @type {{ projects: ProjectNode[], google_enabled: boolean, google_connected: boolean, synced_at: string | null } | null} */ (null))
  const [syncing, setSyncing] = useState(false)
  const [message, setMessage] = useState('')

  const load = () => api('/treemap').then(setData).catch((e) => setMessage(e.message))
  useEffect(() => { load() }, [])

  async function sync() {
    setSyncing(true)
    setMessage('')
    try {
      const r = await api('/sync', { method: 'POST' })
      const counts = Object.entries(r.fetched).map(([k, v]) => `${k} ${v}`).join(' · ')
      setMessage([`Fetched ${counts}. Classified ${r.classified}.`, ...r.warnings].join('  ⚠ '))
      await load()
    } catch (e) {
      setMessage(e.message)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="flex h-screen flex-col gap-3 p-4">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-semibold">Focus</h1>
        <Legend />
        <div className="ml-auto flex items-center gap-3 text-sm">
          {data?.synced_at && <span className="text-zinc-400">Synced {new Date(data.synced_at).toLocaleTimeString()}</span>}
          {data?.google_enabled && !data.google_connected && (
            <a href="/api/auth/google" className="rounded bg-zinc-100 px-3 py-1.5 font-medium text-zinc-900">Connect Google</a>
          )}
          <button
            onClick={sync}
            disabled={syncing}
            className="rounded bg-sky-800 px-3 py-1.5 font-medium text-sky-50 disabled:opacity-40"
          >
            {syncing ? 'Syncing…' : 'Sync'}
          </button>
        </div>
      </header>
      {message && <p className="text-sm text-zinc-300">{message}</p>}
      {data && <Treemap projects={data.projects} />}
    </div>
  )
}

function Legend() {
  return (
    <div className="flex gap-3 text-xs text-zinc-400">
      <span><i className="mr-1 inline-block size-2.5 rounded-sm bg-rose-700" />Behind schedule</span>
      <span><i className="mr-1 inline-block size-2.5 rounded-sm bg-amber-600" />Needs reply</span>
      <span><i className="mr-1 inline-block size-2.5 rounded-sm bg-emerald-700" />On track</span>
    </div>
  )
}

/** @param {{ projects: ProjectNode[] }} props */
function Treemap({ projects }) {
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
  const leaves = treemap().size([size.w, size.h]).paddingInner(4).tile(treemapSquarify)(root).leaves()

  return (
    <div ref={ref} className="relative flex-1">
      {leaves.map((leaf) => (
        <ProjectBox
          key={leaf.data.id}
          p={leaf.data}
          style={{ left: leaf.x0, top: leaf.y0, width: leaf.x1 - leaf.x0, height: leaf.y1 - leaf.y0 }}
          compact={leaf.x1 - leaf.x0 < 180 || leaf.y1 - leaf.y0 < 120}
        />
      ))}
    </div>
  )
}

/** @param {{ p: ProjectNode, style: import('react').CSSProperties, compact: boolean }} props */
function ProjectBox({ p, style, compact }) {
  const navigate = useNavigate()
  const open = () => navigate(projectUrl(p.id, null))
  const meta = [p.replies > 0 && `${p.replies} to reply`, `${p.count} threads`, p.deadline && `due ${p.deadline}`]

  return (
    <div
      role="link"
      tabIndex={0}
      title={p.description}
      onClick={open}
      onKeyDown={(e) => e.key === 'Enter' && open()}
      style={style}
      className={`absolute flex cursor-pointer flex-col overflow-hidden rounded-md p-3 transition-colors ${STATUS_STYLE[p.status]}`}
    >
      <div className="flex items-baseline gap-2">
        <span className="min-w-0 flex-1 truncate font-semibold">{p.name}</span>
        <span className="shrink-0 text-xs opacity-70">{'★'.repeat(p.importance)}</span>
      </div>
      <div className="truncate text-xs opacity-75">{meta.filter(Boolean).join(' · ')}</div>

      {compact ? (
        p.actions.length > 0 && <div className="mt-1 text-xs font-medium">{p.actions.length} actions</div>
      ) : (
        <ol className="mt-2 min-h-0 flex-1 space-y-0.5 overflow-y-auto pr-1 text-sm">
          {p.actions.length === 0 && <li className="text-xs opacity-60">No actions</li>}
          {p.actions.map((a, i) => (
            <li key={i}>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  navigate(projectUrl(p.id, a.item_id))
                }}
                className="flex w-full items-start gap-2 rounded px-1 py-0.5 text-left hover:bg-black/20"
              >
                <span className="w-5 shrink-0 text-right text-xs leading-5 opacity-60">{i + 1}.</span>
                <span className="min-w-0 flex-1 leading-5">{a.text}</span>
                {a.due && <span className="shrink-0 rounded bg-black/25 px-1 text-xs leading-5">{a.due.slice(5)}</span>}
                {a.source && <span className="shrink-0 text-[10px] uppercase leading-5 opacity-60">{SOURCE_SHORT[a.source]}</span>}
              </button>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
