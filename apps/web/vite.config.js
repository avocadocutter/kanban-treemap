import { defineConfig, transformWithOxc } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const SRC_JS = /\/src\/.*\.js$/

const jsxInJsForBuild = {
  name: 'jsx-in-js-build',
  apply: 'build',
  enforce: 'pre',
  transform(code, id) {
    if (SRC_JS.test(id)) return transformWithOxc(code, id, { lang: 'jsx', jsx: { runtime: 'automatic' } })
  },
}

export default defineConfig(({ command }) => {
  if (command === 'serve' && !process.env.PORT_API) throw new Error('Missing required env vars: PORT_API')
  return {
    plugins: [jsxInJsForBuild, react({ include: /\.js$/ }), tailwindcss()],
    oxc: { include: SRC_JS, exclude: /node_modules/, lang: 'jsx' },
    build: { outDir: '../api/src/kanban_treemap/static', emptyOutDir: true },
    server: { proxy: { '/api': `http://localhost:${process.env.PORT_API}` } },
  }
})
