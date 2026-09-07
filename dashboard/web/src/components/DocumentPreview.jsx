import { useEffect, useState } from 'react';

// Render a deliberately small Markdown subset as React text. HTML stays inert.
export function MarkdownPreview({ text }) {
  return <article className="document-preview">{String(text || '').split(/\n\s*\n/).map((block, i) => {
    const heading = /^(#{1,6})\s+(.+)$/.exec(block);
    if (heading) return <h4 key={i}>{heading[2]}</h4>;
    if (block.split('\n').every(line => /^[-*] /.test(line))) return <ul key={i}>{block.split('\n').map((line, j) => <li key={j}>{line.slice(2)}</li>)}</ul>;
    return <p key={i} style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{block}</p>;
  })}</article>;
}
export function PDFPreview({ url, title }) {
  const [src, setSrc] = useState(''), [error, setError] = useState('');
  useEffect(() => {
    const abort = new AbortController(); let objectUrl;
    setSrc(''); setError('');
    fetch(url, { signal: abort.signal }).then(async r => {
      if (!r.ok) throw Error('Document preview could not be generated. Existing versions are retained.');
      if (!r.headers.get('content-type')?.includes('application/pdf')) throw Error('Preview returned an unexpected document type.');
      const blob = await r.blob();
      if (!abort.signal.aborted) { objectUrl = URL.createObjectURL(blob); setSrc(objectUrl); }
    }).catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => { abort.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [url]);
  return <section aria-label={title}><h4>{title}</h4>{error ? <p role="alert">{error}</p> : src ? <>
    <iframe title={title} src={src} style={{ width: '100%', height: '70vh', border: '1px solid var(--border)' }} />
    <a href={src} target="_blank" rel="noreferrer">Open preview in a separate tab</a>
  </> : <p role="status">Loading document layout…</p>}</section>;
}
