// @ts-check
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router'
import TreemapPage from './pages/TreemapPage.js'
import ProjectPage from './pages/ProjectPage.js'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<TreemapPage />} />
        <Route path="/p/:id" element={<ProjectPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
