"""Local simulator fixture. Never deploy: no real transcription or Notion writes."""
import os
import uuid
import sys
from pathlib import Path

os.environ['SCRIBE_PAIRING_CODE'] = 'fixture-code-not-for-production-0001'
os.environ['DATABASE_PATH'] = str(Path(__file__).resolve().parents[1] / '.research' / f'fixture-{uuid.uuid4()}.sqlite3')
os.environ['NOTION_PROJECTS_ID'] = 'fixture-projects'
os.environ['NOTION_IDEAS_ID'] = 'fixture-ideas'
os.environ['DEEPGRAM_API_KEY'] = 'fixture'
os.environ.pop('OPENROUTER_API_KEY', None)
os.environ.pop('OPENROUTER_MODEL', None)
os.environ['ALLOWED_ORIGINS'] = 'http://127.0.0.1:15173'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services' / 'api'))

import uvicorn
from scribe import main

PROJECT = '00000000-0000-4000-8000-000000000001'
OTHER = '00000000-0000-4000-8000-000000000002'
BLOCK = '00000000-0000-4000-8000-000000000003'
saved = []

async def fixture_notion(method, path, **kwargs):
    if path == 'databases/fixture-projects/query':
        return {'results': [{'id': p, 'properties': {'Name': {'type': 'title', 'title': [{'plain_text': name}]}}} for p, name in [(PROJECT, 'FIXTURE Forgotten King'), (OTHER, 'FIXTURE Other Project')]], 'has_more': False}
    if path == f'blocks/{PROJECT}/children':
        return {'results': [{'id': BLOCK, 'type': 'paragraph', 'paragraph': {'rich_text': [{'plain_text': 'The advisor hid a rebel letter in Chapter 4.'}]}, 'has_children': False}], 'has_more': False}
    if path.startswith('blocks/'):
        return {'results': [], 'has_more': False}
    if path == 'pages':
        saved.append(kwargs['json'])
        return {'id': 'FIXTURE-PAGE-NOT-A-NOTION-WRITE'}
    if path == 'databases/fixture-ideas/query':
        return {'results': [], 'has_more': False}
    raise main.HTTPException(404, 'Fixture route unavailable')

class FixtureResponse:
    def raise_for_status(self): pass
    def json(self):
        return {'results': {'channels': [{'alternatives': [{'transcript': 'FIXTURE: What if the advisor supports the rebellion?'}]}]}}

class FixtureClient:
    def __init__(self, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def post(self, url, **kwargs):
        if not url.startswith('https://api.deepgram.com/'):
            raise RuntimeError('Fixture refuses non-Deepgram requests')
        return FixtureResponse()

if __name__ == '__main__':
    main.notion = fixture_notion
    main.httpx.AsyncClient = FixtureClient
    print('FIXTURE ONLY: transcription and Notion writes are simulated', flush=True)
    uvicorn.run(main.app, host='127.0.0.1', port=18080, log_level='warning')
