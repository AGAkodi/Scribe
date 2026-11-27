import { test } from 'node:test'
import { strict as assert } from 'node:assert'
import { networkOrigin, packageManifest } from './package-config.mjs'

test('package contains only the exact configured backend network origin', () => {
  const manifest = packageManifest({ permissions: [{ name: 'g2-microphone', desc: 'Capture' }] }, 'https://api.example.com')
  assert.deepEqual(manifest.permissions[1].whitelist, ['https://api.example.com'])
  assert.equal(manifest.permissions[1].name, 'network')
})

test('rejects missing, insecure and overbroad URLs', () => {
  for (const value of ['', 'http://example.com', 'https://localhost', 'https://*.example.com', 'https://user:pass@example.com', 'https://example.com/path', 'https://example.com?q=1']) assert.throws(() => networkOrigin(value))
})
