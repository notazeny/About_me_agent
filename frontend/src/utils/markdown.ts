// 极简 markdown → HTML 渲染（先转义 HTML 再处理 markdown，防 XSS）
// 从原生前端 static/index.html 里的 mdToHtml 原样搬过来

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function inline(s: string): string {
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>')
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  return s
}

export function mdToHtml(text: string): string {
  const lines = text.split('\n')
  let html = ''
  let i = 0
  let listBuf: string | null = null
  const closeList = () => { if (listBuf) { html += '</' + listBuf + '>'; listBuf = null } }

  while (i < lines.length) {
    const line = lines[i]

    if (line.trim().startsWith('```')) {
      closeList()
      html += '<pre><code>'
      i++
      const buf: string[] = []
      while (i < lines.length && !lines[i].trim().startsWith('```')) { buf.push(lines[i]); i++ }
      html += escapeHtml(buf.join('\n')) + '</code></pre>'
      i++
      continue
    }

    if (line.includes('|') && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1]) && lines[i + 1].includes('-')) {
      closeList()
      const headerCells = line.split('|').map(c => c.trim()).filter(c => c !== '')
      i += 2
      html += '<table><thead><tr>'
      headerCells.forEach(c => html += '<th>' + inline(escapeHtml(c)) + '</th>')
      html += '</tr></thead><tbody>'
      while (i < lines.length && lines[i].includes('|')) {
        const cells = lines[i].split('|').map(c => c.trim())
        if (cells[0] === '') cells.shift()
        if (cells[cells.length - 1] === '') cells.pop()
        html += '<tr>'
        cells.forEach(c => html += '<td>' + inline(escapeHtml(c)) + '</td>')
        html += '</tr>'
        i++
      }
      html += '</tbody></table>'
      continue
    }

    const h = line.match(/^(#{1,4})\s+(.*)$/)
    if (h) { closeList(); html += '<h' + h[1].length + '>' + inline(escapeHtml(h[2])) + '</h' + h[1].length + '>'; i++; continue }

    const ul = line.match(/^\s*[-*]\s+(.*)$/)
    if (ul) { if (listBuf !== 'ul') { closeList(); html += '<ul>'; listBuf = 'ul' } html += '<li>' + inline(escapeHtml(ul[1])) + '</li>'; i++; continue }

    const ol = line.match(/^\s*\d+\.\s+(.*)$/)
    if (ol) { if (listBuf !== 'ol') { closeList(); html += '<ol>'; listBuf = 'ol' } html += '<li>' + inline(escapeHtml(ol[1])) + '</li>'; i++; continue }

    if (line.trim() === '') { closeList(); i++; continue }

    closeList()
    html += '<p>' + inline(escapeHtml(line)) + '</p>'
    i++
  }
  closeList()
  return html
}
