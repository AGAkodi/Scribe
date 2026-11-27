import { spawnSync } from 'node:child_process'
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve, relative, isAbsolute } from 'node:path'
import { packageManifest, networkOrigin } from './package-config.mjs'

const origin = networkOrigin(process.env.SCRIBE_API_ORIGIN || '')
const manifest = packageManifest(JSON.parse(readFileSync('app.json', 'utf8')), origin)
const temporary = mkdtempSync(join(tmpdir(), 'scribe-pack-'))
const manifestPath = join(temporary, 'app.json')
const env = { ...process.env, VITE_API_BASE_URL: origin }
function run(script, args = []) {
  const result = spawnSync(process.execPath, [resolve(script), ...args], { stdio: 'inherit', env })
  if (result.error) throw result.error
  if (result.status !== 0) throw new Error(`Packaging command failed with status ${result.status}`)
}
try {
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2))
  run('node_modules/typescript/bin/tsc', ['--noEmit'])
  run('node_modules/vite/bin/vite.js', ['build'])
  run('node_modules/@evenrealities/evenhub-cli/main.js', ['pack', manifestPath, resolve('dist'), '--sdk-ver', '0.0.10', '-o', resolve(process.env.SCRIBE_PACKAGE_OUTPUT || 'out.ehpk')])
} finally {
  const insideTemp = relative(resolve(tmpdir()), resolve(temporary))
  if (!insideTemp || insideTemp.startsWith('..') || isAbsolute(insideTemp)) throw new Error('Refusing to remove a directory outside the temporary root')
  rmSync(temporary, { recursive: true, force: true })
}
