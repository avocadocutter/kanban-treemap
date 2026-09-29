// @ts-check
import { useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { api, SOURCE_ICON, SOURCE_LABEL, sourceCounts, STATUS_STYLE } from '../api.js'

/** @typedef {import('../types.js').Item} Item */
/** @typedef {import('../types.js').Action} Action */

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

/** @param {string} s */
const normalize = (s) => s.toLowerCase().replace(/\s+/g, ' ').trim()

/** @param {string} messageText @param {string} quote */
function containsQuote(messageText, quote) {
  const q = normalize(quote)
  return q.length > 0 && normalize(messageText).includes(q.slice(0, 40))
}

export default function ProjectPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const [data, setData] = useState(
    /** @type {{ project: import('../types.js').ProjectNode, items: Item[] } | null} */ (null),
  )
  const [selectedId, setSelectedId] = useState(/** @type {string | null} */ (null))
  const [openAction, setOpenAction] = useState(/** @type {number | null} */ (null))
  const [highlight, setHighlight] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api(`/projects/${id}`)
      .then((d) => {
        setData(d)
        const actionIndex = searchParams.has('action') ? Number(searchParams.get('action')) : null
        const first = actionIndex === null ? null : d.project.actions[actionIndex]?.sources[0]
        setOpenAction(actionIndex)
        setSelectedId(first?.item_id ?? d.items[0]?.id ?? null)
        setHighlight(first?.quote ?? '')
      })
      .catch((e) => setError(e.message))
  }, [id, searchParams])

  if (error) return <p className="p-4 text-red-400">{error}</p>
  if (!data) return <p className="p-4 text-zinc-400">Loading…</p>
  const { project, items } = data
  const selected = items.find((it) => it.id === selectedId)

  /** @param {string} itemId */
  const actionNumbersFor = (itemId) =>
    project.actions.flatMap((a, i) => (a.sources.some((s) => s.item_id === itemId) ? [i + 1] : []))

  /** @param {string} itemId @param {string} quote */
  const showSource = (itemId, quote) => {
    setSelectedId(itemId)
    setHighlight(quote)
  }

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
        <div className="grid min-h-0 flex-1 gap-3 md:grid-cols-[minmax(280px,1fr)_2fr]">
          <div className="flex min-h-0 flex-col gap-3">
            {project.actions.length > 0 && (
              <section className="max-h-[55%] shrink-0 overflow-y-auto rounded-md border border-zinc-800">
                <h2 className="sticky top-0 z-10 bg-zinc-950 px-3 py-2 text-xs font-semibold uppercase text-zinc-400">
                  Actions ({project.actions.length})
                </h2>
                <ol>
                  {project.actions.map((a, i) => (
                    <ActionRow
                      key={i}
                      action={a}
                      number={i + 1}
                      open={openAction === i}
                      onToggle={() => setOpenAction(openAction === i ? null : i)}
                      onSource={showSource}
                      selectedId={selectedId}
                    />
                  ))}
                </ol>
              </section>
            )}

            <ul className="min-h-0 flex-1 overflow-y-auto rounded-md border border-zinc-800">
              {items.map((it) => {
                const numbers = actionNumbersFor(it.id)
                return (
                  <li key={it.id}>
                    <button
                      onClick={() => showSource(it.id, '')}
                      className={`w-full border-b border-zinc-800 px-3 py-2 text-left hover:bg-zinc-900 ${it.id === selectedId ? 'bg-zinc-800' : ''}`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="min-w-0 flex-1 truncate font-medium">{it.title}</span>
                        {!!it.needs_reply && <span className="size-2 shrink-0 rounded-full bg-amber-600" title="needs reply" />}
                      </div>
                      <div className="flex justify-between gap-2 text-xs text-zinc-500">
                        <span>
                          {SOURCE_LABEL[it.source]}
                          {numbers.length > 0 && <span className="text-zinc-400"> → {numbers.map((n) => `#${n}`).join(' ')}</span>}
                        </span>
                        <span>{new Date(it.updated_at).toLocaleDateString()}</span>
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>

          {selected && <Conversation item={selected} highlight={highlight} />}
        </div>
      )}
    </div>
  )
}

/**
 * @param {{ action: Action, number: number, open: boolean, onToggle: () => void,
 *   onSource: (itemId: string, quote: string) => void, selectedId: string | null }} props
 */
function ActionRow({ action, number, open, onToggle, onSource, selectedId }) {
  return (
    <li className="border-t border-zinc-800">
      <button onClick={onToggle} className={`flex w-full items-start gap-2 px-3 py-1.5 text-left text-sm hover:bg-zinc-900 ${open ? 'bg-zinc-900' : ''}`}>
        <span className="w-4 shrink-0 text-xs leading-5 text-zinc-500">{open ? '▼' : '▶'}</span>
        <span className="w-5 shrink-0 text-right text-xs leading-5 text-zinc-500">{number}.</span>
        <span className={`min-w-0 flex-1 leading-5 ${action.feedback ? 'text-zinc-500 line-through' : ''}`}>{action.text}</span>
        {action.due && <span className="shrink-0 rounded bg-zinc-800 px-1 text-xs leading-5">{action.due.slice(5)}</span>}
        {sourceCounts(action.sources).map(([src, n]) => (
          <span key={src} title={SOURCE_LABEL[src]} className="shrink-0 text-xs leading-5 text-zinc-400">
            {SOURCE_ICON[src]}{n > 1 && n}
          </span>
        ))}
      </button>
      {open && (
        <ul className="bg-zinc-900/60 pb-1">
          {action.sources.length === 0 && <li className="px-12 py-1 text-xs text-zinc-500">No linked thread</li>}
          {action.sources.map((s) => (
            <li key={s.item_id}>
              <button
                onClick={() => onSource(s.item_id, s.quote)}
                className={`flex w-full items-start gap-2 py-1 pl-12 pr-3 text-left text-xs hover:bg-zinc-800 ${s.item_id === selectedId ? 'text-sky-300' : 'text-zinc-300'}`}
              >
                <span className="shrink-0" title={SOURCE_LABEL[s.source]}>{SOURCE_ICON[s.source]}</span>
                <span className="w-32 shrink-0 truncate font-medium">{s.title}</span>
                {s.quote && <span className="min-w-0 flex-1 italic text-zinc-400">“{s.quote}”</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

/** @param {{ item: Item, highlight: string }} props */
function Conversation({ item, highlight }) {
  const highlighted = useRef(/** @type {HTMLLIElement | null} */ (null))
  const messages = parseMessages(item.body)
  const matchIndex = highlight ? messages.findIndex((m) => containsQuote(m.text, highlight)) : -1

  useEffect(() => {
    highlighted.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [item.id, highlight])

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
        {messages.map((m, i) => (
          <li
            key={i}
            ref={i === matchIndex ? highlighted : null}
            className={`${m.who === 'me' ? 'ml-8 bg-sky-950' : 'mr-8 bg-zinc-900'} rounded-md p-2 ${i === matchIndex ? 'ring-2 ring-amber-500/70' : ''}`}
          >
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
