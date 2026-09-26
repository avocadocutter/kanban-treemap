// @ts-check
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api, STATUS_STYLE } from '../api.js'

const SOURCE_LABEL = { gmail: 'Gmail', chat: 'Chat', clickup: 'ClickUp' }

export default function ProjectPage() {
  const { id } = useParams()
  const [data, setData] = useState(
    /** @type {{ project: import('../types.js').ProjectNode, items: import('../types.js').Item[] } | null} */ (null),
  )
  const [error, setError] = useState('')

  useEffect(() => {
    api(`/projects/${id}`).then(setData).catch((e) => setError(e.message))
  }, [id])

  if (error) return <p className="p-4 text-red-400">{error}</p>
  if (!data) return <p className="p-4 text-zinc-400">Loading…</p>
  const { project, items } = data

  return (
    <div className="mx-auto max-w-4xl p-4">
      <Link to="/" className="text-sm text-sky-400">← Treemap</Link>
      <div className={`mt-3 rounded-md p-4 ${STATUS_STYLE[project.status]}`}>
        <h1 className="text-xl font-semibold">{project.name}</h1>
        <p className="text-sm opacity-90">{project.description}</p>
        <p className="mt-1 text-xs opacity-90">
          {'★'.repeat(project.importance)} · {project.overdue} overdue · {project.replies} to reply
          {project.deadline && ` · due ${project.deadline}`}
        </p>
      </div>
      <ul className="mt-4 divide-y divide-zinc-800">
        {items.length === 0 && <li className="py-3 text-zinc-400">Nothing here.</li>}
        {items.map((it) => (
          <li key={it.id} className="flex gap-3 py-3">
            <span className="w-16 shrink-0 text-xs text-zinc-500">{SOURCE_LABEL[it.source]}</span>
            <div className="min-w-0 flex-1">
              <a href={it.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">{it.title}</a>
              {it.summary && <p className="text-sm text-zinc-400">{it.summary}</p>}
              <p className="text-xs text-zinc-600">{it.people}</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1 text-xs">
              {it.overdue && <span className="rounded bg-red-600 px-1.5">overdue {it.due_at?.slice(0, 10)}</span>}
              {!!it.needs_reply && <span className="rounded bg-amber-500 px-1.5 text-zinc-950">reply</span>}
              <span className="text-zinc-500">{new Date(it.updated_at).toLocaleDateString()}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
