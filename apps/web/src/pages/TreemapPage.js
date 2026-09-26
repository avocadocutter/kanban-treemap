// @ts-check
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { hierarchy, treemap, treemapSquarify } from 'd3-hierarchy'
import { api, STATUS_STYLE } from '../api.js'

/** @typedef {import('../types.js').ProjectNode} ProjectNode */

export default function TreemapPage() {
  const [data, setData] = useState(/** @type {{ projects: ProjectNode[], google_connected: boolean, synced_at: string | null } | null} */ (null))
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
          {data && !data.google_connected && (
            <a href="/api/auth/google" className="rounded bg-zinc-100 px-3 py-1.5 font-medium text-zinc-900">Connect Google</a>
          )}
          <button
            onClick={sync}
            disabled={syncing || !data?.google_connected}
            className="rounded bg-sky-600 px-3 py-1.5 font-medium disabled:opacity-40"
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
      <span><i className="mr-1 inline-block size-2.5 rounded-sm bg-red-600" />Behind schedule</span>
      <span><i className="mr-1 inline-block size-2.5 rounded-sm bg-amber-500" />Needs reply</span>
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
      {leaves.map((leaf) => {
        /** @type {ProjectNode} */
        const p = leaf.data
        const w = leaf.x1 - leaf.x0
        const h = leaf.y1 - leaf.y0
        return (
          <Link
            key={p.id}
            to={`/p/${p.id}`}
            title={p.description}
            style={{ left: leaf.x0, top: leaf.y0, width: w, height: h }}
            className={`absolute overflow-hidden rounded-md p-3 transition-colors ${STATUS_STYLE[p.status]}`}
          >
            <div className="font-semibold leading-tight">{p.name}</div>
            {h > 60 && w > 110 && (
              <div className="mt-1 space-y-0.5 text-xs opacity-90">
                <div>{'★'.repeat(p.importance)}</div>
                {p.overdue > 0 && <div>{p.overdue} overdue</div>}
                {p.replies > 0 && <div>{p.replies} to reply</div>}
                <div>{p.count} items{p.deadline && ` · due ${p.deadline}`}</div>
              </div>
            )}
          </Link>
        )
      })}
    </div>
  )
}
