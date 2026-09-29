// @ts-check
import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { api, SOURCE_LABEL, SOURCE_SHORT, STATUS_STYLE } from '../api.js'

/** @typedef {import('../types.js').Item} Item */

/** @param {string | null} body @returns {{ who: string, text: string }[]} */
export function parseMessages(body) {
  return (body ?? '')
    .split(/\n---\n|\n(?=(?:me|them): )/)
    .filter((block) => block.trim())
    .map((block) => {
      const i = block.indexOf(': ')
      return i === -1 ? { who: '', text: block } : { who: block.slice(0, i), text: block.slice(i + 2) }
    })
}

export default function ProjectPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const [data, setData] = useState(
    /** @type {{ project: import('../types.js').ProjectNode, items: Item[] } | null} */ (null),
  )
  const [selectedId, setSelectedId] = useState(/** @type {string | null} */ (null))
  const [error, setError] = useState('')

  useEffect(() => {
    api(`/projects/${id}`)
      .then((d) => {
        setData(d)
        setSelectedId(searchParams.get('item') ?? d.items[0]?.id ?? null)
      })
      .catch((e) => setError(e.message))
  }, [id, searchParams])

  if (error) return <p className="p-4 text-red-400">{error}</p>
  if (!data) return <p className="p-4 text-zinc-400">Loading…</p>
  const { project, items } = data
  const selected = items.find((it) => it.id === selectedId)

  return (
    <div className="flex h-screen flex-col gap-3 p-4">
      <div>
        <Link to="/" className="text-sm text-sky-400">← Treemap</Link>
        <div className={`mt-2 rounded-md px-4 py-3 ${STATUS_STYLE[project.status]}`}>
          <h1 className="text-xl font-semibold">{project.name}</h1>
          <p className="text-xs opacity-90">
            {'★'.repeat(project.importance)} · {project.replies} to reply · {project.count} threads
            {project.deadline && ` · due ${project.deadline}`}
          </p>
        </div>
      </div>

      {items.length === 0 ? (
        <p className="text-zinc-400">Nothing here.</p>
      ) : (
        <div className="grid min-h-0 flex-1 gap-3 md:grid-cols-[minmax(240px,1fr)_2fr]">
          <div className="flex min-h-0 flex-col gap-3">
          {project.actions.length > 0 && (
            <section className="max-h-[45%] shrink-0 overflow-y-auto rounded-md border border-zinc-800">
              <h2 className="sticky top-0 bg-zinc-950 px-3 py-2 text-xs font-semibold uppercase text-zinc-400">
                Actions ({project.actions.length})
              </h2>
              <ol>
                {project.actions.map((a, i) => (
                  <li key={i}>
                    <button
                      onClick={() => a.item_id && setSelectedId(a.item_id)}
                      className={`flex w-full items-start gap-2 border-t border-zinc-800 px-3 py-1.5 text-left text-sm hover:bg-zinc-900 ${a.item_id && a.item_id === selectedId ? 'bg-zinc-800' : ''}`}
                    >
                      <span className="w-5 shrink-0 text-right text-xs leading-5 text-zinc-500">{i + 1}.</span>
                      <span className="min-w-0 flex-1 leading-5">{a.text}</span>
                      {a.due && <span className="shrink-0 rounded bg-zinc-800 px-1 text-xs leading-5">{a.due.slice(5)}</span>}
                      {a.source && <span className="shrink-0 text-[10px] uppercase leading-5 text-zinc-500">{SOURCE_SHORT[a.source]}</span>}
                    </button>
                  </li>
                ))}
              </ol>
            </section>
          )}
          <ul className="min-h-0 flex-1 overflow-y-auto rounded-md border border-zinc-800">
            {items.map((it) => (
              <li key={it.id}>
                <button
                  onClick={() => setSelectedId(it.id)}
                  className={`w-full border-b border-zinc-800 px-3 py-2 text-left hover:bg-zinc-900 ${it.id === selectedId ? 'bg-zinc-800' : ''}`}
                >
                  <div className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate font-medium">{it.title}</span>
                    {!!it.needs_reply && <span className="size-2 shrink-0 rounded-full bg-amber-600" title="needs reply" />}
                  </div>
                  <div className="flex justify-between text-xs text-zinc-500">
                    <span>{SOURCE_LABEL[it.source]}</span>
                    <span>{new Date(it.updated_at).toLocaleDateString()}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
          </div>

          {selected && <Conversation item={selected} />}
        </div>
      )}
    </div>
  )
}

/** @param {{ item: Item }} props */
function Conversation({ item }) {
  return (
    <section className="flex min-h-0 flex-col rounded-md border border-zinc-800">
      <header className="border-b border-zinc-800 px-4 py-3">
        <div className="flex items-start gap-2">
          <h2 className="min-w-0 flex-1 font-semibold">{item.title}</h2>
          {!!item.needs_reply && <span className="rounded bg-amber-900/60 px-1.5 text-xs text-amber-100">reply</span>}
        </div>
        <p className="text-xs text-zinc-500">{SOURCE_LABEL[item.source]} · {item.people}</p>
        {item.summary && <p className="mt-1 text-sm text-zinc-300">AI: {item.summary}</p>}
      </header>
      <ul className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {parseMessages(item.body).map((m, i) => (
          <li key={i} className={m.who === 'me' ? 'ml-8 rounded-md bg-sky-950 p-2' : 'mr-8 rounded-md bg-zinc-900 p-2'}>
            {m.who && <div className="text-xs font-medium text-zinc-400">{m.who}</div>}
            <div className="whitespace-pre-wrap text-sm">{m.text}</div>
          </li>
        ))}
      </ul>
      <footer className="border-t border-zinc-800 px-4 py-2">
        <a href={item.url} target="_blank" rel="noreferrer" className="text-sm text-sky-400 hover:underline">
          Open in {SOURCE_LABEL[item.source]} ↗
        </a>
      </footer>
    </section>
  )
}
