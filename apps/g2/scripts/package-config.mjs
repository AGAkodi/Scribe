export function networkOrigin(value) {
  let parsed
  try { parsed = new URL(value) } catch { throw new Error('SCRIBE_API_ORIGIN must be an HTTPS origin, e.g. https://api.example.com') }
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.pathname !== '/' || parsed.search || parsed.hash || parsed.hostname.includes('*') || ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname)) {
    throw new Error('SCRIBE_API_ORIGIN must be a non-local HTTPS origin without credentials, path, query or fragment')
  }
  return parsed.origin
}

export function packageManifest(manifest, value) {
  const origin = networkOrigin(value)
  return { ...manifest, permissions: [...manifest.permissions.filter(p => p.name !== 'network'), { name: 'network', desc: 'Connect to the Scribe backend for transcription and project notes.', whitelist: [origin] }] }
}
