import os
import hashlib
import asyncio
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services' / 'api'))
from fastapi.testclient import TestClient
from scribe import main


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB', str(tmp_path / 'test.sqlite3'))
    main.init_db()
    with main.db() as conn:
        conn.execute('INSERT INTO sessions (token_hash, expires) VALUES (?, ?)', (hashlib.sha256(('x' * 32).encode()).hexdigest(), time.time() + 3600))
    return TestClient(main.app)


def test_auth_and_health(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.get('/health').json() == {'status': 'ok'}
    assert c.get('/projects').status_code == 401
    assert c.post('/transcribe', headers={'Authorization': 'Bearer ' + 'x' * 32}, files={'audio': ('x', b'1')}).status_code == 400


def test_pairing_is_single_use(tmp_path, monkeypatch):
    monkeypatch.setenv('SCRIBE_PAIRING_CODE', 'p' * 32)
    c = client(tmp_path, monkeypatch)
    response = c.post('/pair', json={'code': 'p' * 32})
    assert response.status_code == 200
    assert c.post('/pair', json={'code': 'p' * 32}).status_code == 401
    assert c.get('/actions/missing', headers={'Authorization': 'Bearer ' + response.json()['token']}).status_code == 404


def test_access_code_is_reusable_until_expiry(tmp_path, monkeypatch):
    monkeypatch.setenv('SCRIBE_ACCESS_CODE', 'a' * 32)
    monkeypatch.setenv('SCRIBE_ACCESS_CODE_EXPIRES', '2099-01-01T00:00:00Z')
    c = client(tmp_path, monkeypatch)
    first, second = (c.post('/pair', json={'code': 'a' * 32}) for _ in range(2))
    assert first.status_code == second.status_code == 200
    assert first.json()['token'] != second.json()['token']
    assert c.get('/actions/missing', headers={'Authorization': 'Bearer ' + second.json()['token']}).status_code == 404
    assert c.post('/pair', json={'code': 'b' * 32}).status_code == 401


def test_access_code_session_never_outlives_code(tmp_path, monkeypatch):
    soon = time.time() + 120
    monkeypatch.setenv('SCRIBE_ACCESS_CODE', 'a' * 32)
    monkeypatch.setenv('SCRIBE_ACCESS_CODE_EXPIRES', main.datetime.fromtimestamp(soon, main.timezone.utc).isoformat())
    c = client(tmp_path, monkeypatch)
    assert abs(c.post('/pair', json={'code': 'a' * 32}).json()['expires_at'] - soon) <= 1


def test_access_code_expired_or_misconfigured_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv('SCRIBE_ACCESS_CODE', 'a' * 32)
    for index, expires in enumerate(('2020-01-01T00:00:00Z', '', 'next week')):
        monkeypatch.setenv('SCRIBE_ACCESS_CODE_EXPIRES', expires)
        (tmp_path / str(index)).mkdir()
        c = client(tmp_path / str(index), monkeypatch)
        assert c.post('/pair', json={'code': 'a' * 32}).status_code == 401
    monkeypatch.setenv('SCRIBE_ACCESS_CODE', 'short')
    monkeypatch.setenv('SCRIBE_ACCESS_CODE_EXPIRES', '2099-01-01')
    assert main.access_code() is None


def test_rotating_access_code_revokes_its_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv('SCRIBE_ACCESS_CODE', 'a' * 32)
    monkeypatch.setenv('SCRIBE_ACCESS_CODE_EXPIRES', '2099-01-01')
    c = client(tmp_path, monkeypatch)
    token = c.post('/pair', json={'code': 'a' * 32}).json()['token']
    monkeypatch.delenv('SCRIBE_ACCESS_CODE')
    main.init_db()  # what a restart does
    assert c.get('/actions/missing', headers={'Authorization': 'Bearer ' + token}).status_code == 401
    assert c.get('/actions/missing', headers={'Authorization': 'Bearer ' + 'x' * 32}).status_code == 404


def test_retrieval_requires_overlap():
    chunks = [{'id': 'a', 'text': 'The advisor hides a rebel letter'}, {'id': 'b', 'text': 'A blue sky'}]
    assert main.rank('advisor rebel', chunks) == chunks[:1]
    assert main.rank('ocean', chunks) == []
    assert main.rank('what is the', chunks) == []
    assert main.rank('rebellion', chunks) == chunks[:1]
    # Deepgram can transcribe "advisor" as "adviser".
    assert main.rank('What if the adviser secretly supports them?', chunks) == chunks[:1]
    assert main.rank('advisers', chunks) == chunks[:1]


def test_cancel_and_expired_actions(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    headers = {'Authorization': 'Bearer ' + 'x' * 32}
    with main.db() as conn:
        conn.execute("INSERT INTO actions (id,project,transcript,status,created,owner_hash) VALUES ('a','p','text','pending',?,'c62e4615bd39e222572f3a1bf7c2132ea1e65b17ec805047bd6b2842c593493f')", (time.time(),))
    assert c.post('/actions/a/cancel', headers=headers).json()['status'] == 'cancelled'
    with main.db() as conn:
        assert conn.execute("SELECT transcript FROM actions WHERE id='a'").fetchone()['transcript'] == ''
    assert c.post('/actions/a/cancel', headers=headers).status_code == 409
    assert c.get('/actions/a', headers=headers).json()['status'] == 'cancelled'


def test_confirm_is_idempotent_and_cancelled_does_not_write(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    headers = {'Authorization': 'Bearer ' + 'x' * 32}
    monkeypatch.setenv('NOTION_IDEAS_ID', 'ideas')
    calls = []
    async def allow(_): pass
    async def fake_notion(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {'id': 'saved-page'}
    monkeypatch.setattr(main, 'authorize_project', allow)
    monkeypatch.setattr(main, 'notion', fake_notion)
    with main.db() as conn:
        conn.execute("INSERT INTO actions (id,project,transcript,status,created,owner_hash) VALUES ('a','p','original','pending',?,'c62e4615bd39e222572f3a1bf7c2132ea1e65b17ec805047bd6b2842c593493f')", (time.time(),))
        conn.execute("INSERT INTO actions (id,project,transcript,status,created,owner_hash) VALUES ('b','p','discard','cancelled',?,'c62e4615bd39e222572f3a1bf7c2132ea1e65b17ec805047bd6b2842c593493f')", (time.time(),))
    assert c.post('/actions/a/confirm', headers=headers).json()['status'] == 'saved'
    assert c.post('/actions/a/confirm', headers=headers).json()['status'] == 'saved'
    assert c.post('/actions/b/confirm', headers=headers).status_code == 409
    assert len(calls) == 1
    assert calls[0][2]['json']['children'][0]['paragraph']['rich_text'][0]['text']['content'] == 'original'
    with main.db() as conn:
        assert conn.execute("SELECT transcript FROM actions WHERE id='a'").fetchone()['transcript'] == ''


def test_failed_write_is_unknown_and_cannot_repeat(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    headers = {'Authorization': 'Bearer ' + 'x' * 32}
    monkeypatch.setenv('NOTION_IDEAS_ID', 'ideas')
    calls = []
    async def allow(_): pass
    async def fail(*args, **kwargs):
        calls.append(1)
        raise main.HTTPException(502, 'provider error')
    monkeypatch.setattr(main, 'authorize_project', allow)
    monkeypatch.setattr(main, 'notion', fail)
    with main.db() as conn:
        conn.execute("INSERT INTO actions (id,project,transcript,status,created,owner_hash) VALUES ('a','p','text','pending',?,'c62e4615bd39e222572f3a1bf7c2132ea1e65b17ec805047bd6b2842c593493f')", (time.time(),))
    assert c.post('/actions/a/confirm', headers=headers).status_code == 502
    assert c.get('/actions/a', headers=headers).json()['status'] == 'unknown'
    assert c.post('/actions/a/confirm', headers=headers).status_code == 409
    assert len(calls) == 2  # write plus safe lookup, never a second write


def test_model_rejects_fabricated_source(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-key')
    monkeypatch.setenv('OPENROUTER_MODEL', 'fixture-model')
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {'choices': [{'message': {'content': json.dumps({'title': 'Idea', 'category': 'Idea', 'summary': 'Summary', 'connection_type': 'related', 'connection': 'Claim', 'source_ids': ['invented']})}}]}
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return Response()
    monkeypatch.setattr(main.httpx, 'AsyncClient', Client)
    result = asyncio.run(main.generate(main.Assist(project_id='p', transcript='advisor'), [{'id': 'real', 'text': 'advisor'}]))
    assert result['connection_type'] == 'none'
    assert result['sources'] == []


def test_model_rejects_non_object_json(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-key')
    monkeypatch.setenv('OPENROUTER_MODEL', 'fixture-model')
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'choices': [{'message': {'content': '[]'}}]}
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return Response()
    monkeypatch.setattr(main.httpx, 'AsyncClient', Client)
    result = asyncio.run(main.generate(main.Assist(project_id='p', transcript='advisor'), [{'id': 'real', 'text': 'advisor'}]))
    assert result['connection_type'] == 'none'


def test_model_returns_only_retrieved_sources(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-key')
    monkeypatch.setenv('OPENROUTER_MODEL', 'fixture-model')
    sent = []
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {'choices': [{'message': {'content': json.dumps({'title': 'Advisor', 'category': 'Idea', 'summary': 'A possible idea', 'connection_type': 'related', 'connection': 'The hidden letter could be relevant.', 'source_ids': ['real'], 'evidence_quotes': [{'source_id': 'real', 'quote': 'The advisor hid a rebel letter.'}]})}}]}
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): sent.append(kwargs['json']); return Response()
    monkeypatch.setattr(main.httpx, 'AsyncClient', Client)
    source = {'id': 'real', 'text': 'The advisor hid a rebel letter.'}
    result = asyncio.run(main.generate(main.Assist(project_id='p', transcript='advisor'), [source]))
    assert result['connection_type'] == 'related'
    assert result['sources'] == [{**source, 'evidence': 'The advisor hid a rebel letter.'}]
    assert result['summary'] == ''
    assert sent[0]['response_format']['type'] == 'json_schema'


def test_conflicts_are_withheld_without_factual_verification(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-key')
    monkeypatch.setenv('OPENROUTER_MODEL', 'fixture-model')
    class Response:
        def raise_for_status(self): pass
        def json(self):
            content = {'title': 'T', 'category': 'Idea', 'summary': '', 'connection_type': 'possible_conflict', 'connection': 'Conflict', 'source_ids': ['real'], 'evidence_quotes': [{'source_id': 'real', 'quote': 'Mara hid a rebel letter.'}]}
            return {'choices': [{'message': {'content': json.dumps(content)}}]}
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return Response()
    monkeypatch.setattr(main.httpx, 'AsyncClient', Client)
    result = asyncio.run(main.generate(main.Assist(project_id='p', transcript='advisor'), [{'id': 'real', 'text': 'Mara hid a rebel letter.'}]))
    assert result['ai_status'] == 'unverified_conflict'
    assert result['connection_type'] == 'none'


def test_brainstorm_is_labelled_speculation_and_separate(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-key')
    monkeypatch.setenv('OPENROUTER_MODEL', 'fixture-model')
    class Response:
        def raise_for_status(self): pass
        def json(self):
            content = {'title': 'T', 'category': 'Idea', 'summary': 'invented summary', 'connection_type': 'related', 'connection': 'What if Mara hides a second letter?', 'source_ids': ['real'], 'evidence_quotes': [{'source_id': 'real', 'quote': 'Mara hid a rebel letter.'}]}
            return {'choices': [{'message': {'content': json.dumps(content)}}]}
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return Response()
    monkeypatch.setattr(main.httpx, 'AsyncClient', Client)
    result = asyncio.run(main.generate(main.Assist(project_id='p', mode='brainstorm', transcript='What next?'), [{'id': 'real', 'text': 'Mara hid a rebel letter.'}]))
    assert result['connection'].startswith('Speculative suggestion:')
    assert result['category'] == 'Brainstorm'
    assert result['summary'] == ''


def test_model_rejects_fabricated_quote_and_uncited_summary(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-key')
    monkeypatch.setenv('OPENROUTER_MODEL', 'fixture-model')
    class Response:
        def raise_for_status(self): pass
        def json(self):
            content = {'title': 'T', 'category': 'Idea', 'summary': 'Invented fact', 'connection_type': 'related', 'connection': 'Claim', 'source_ids': ['real'], 'evidence_quotes': [{'source_id': 'real', 'quote': 'A quote that does not occur'}]}
            return {'choices': [{'message': {'content': json.dumps(content)}}]}
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return Response()
    monkeypatch.setattr(main.httpx, 'AsyncClient', Client)
    result = asyncio.run(main.generate(main.Assist(project_id='p', transcript='advisor'), [{'id': 'real', 'text': 'The advisor hid a rebel letter.'}]))
    assert result['ai_status'] == 'invalid_response'
    assert result['summary'] == ''
    assert result['sources'] == []


def test_long_notion_block_is_split_without_losing_tail(monkeypatch):
    text = 'A' * 1700 + 'END OF BLOCK'
    async def fixture_notion(method, path, **kwargs):
        return {'results': [{'id': 'block', 'type': 'paragraph', 'paragraph': {'rich_text': [{'plain_text': text}]}, 'has_children': False}], 'has_more': False}
    monkeypatch.setattr(main, 'notion', fixture_notion)
    chunks = asyncio.run(main.read_blocks('project'))
    assert ''.join(chunk['text'] for chunk in chunks) == text
    assert len(chunks) == 2
    assert all(chunk['block_id'] == 'block' for chunk in chunks)


def test_no_match_does_not_call_model(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-key')
    monkeypatch.setenv('OPENROUTER_MODEL', 'fixture-model')
    def forbidden_client(*args, **kwargs):
        raise AssertionError('Model must not be called without retrieved evidence')
    monkeypatch.setattr(main.httpx, 'AsyncClient', forbidden_client)
    result = asyncio.run(main.generate(main.Assist(project_id='p', transcript='unrelated'), []))
    assert result['connection_type'] == 'none'
    assert result['sources'] == []
    assert result['ai_status'] == 'no_match'


def test_model_billing_error_is_not_reported_as_no_match(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-key')
    monkeypatch.setenv('OPENROUTER_MODEL', 'fixture-model')
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            request = main.httpx.Request('POST', 'https://example.test')
            return main.httpx.Response(402, request=request)
    monkeypatch.setattr(main.httpx, 'AsyncClient', Client)
    result = asyncio.run(main.generate(main.Assist(project_id='p', transcript='advisor'), [{'id': 'real', 'text': 'advisor'}]))
    assert result['ai_status'] == 'insufficient_credits'
    assert 'credits' in result['connection']


def test_free_model_rate_limit_uses_only_free_fallback(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-key')
    monkeypatch.setenv('OPENROUTER_MODEL', 'fixture-primary:free')
    models = []
    class Response:
        def __init__(self, limited): self.limited = limited
        def raise_for_status(self):
            if self.limited:
                request = main.httpx.Request('POST', 'https://example.test')
                raise main.httpx.HTTPStatusError('rate limit', request=request, response=main.httpx.Response(429, request=request))
        def json(self):
            content = {'title': 'T', 'category': 'Idea', 'summary': '', 'connection_type': 'related', 'connection': 'The letter is related.', 'source_ids': ['real'], 'evidence_quotes': [{'source_id': 'real', 'quote': 'Mara hid a rebel letter.'}]}
            return {'choices': [{'message': {'content': json.dumps(content)}}]}
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            models.append(kwargs['json']['model'])
            return Response(len(models) == 1)
    monkeypatch.setattr(main.httpx, 'AsyncClient', Client)
    result = asyncio.run(main.generate(main.Assist(project_id='p', transcript='letter'), [{'id': 'real', 'text': 'Mara hid a rebel letter.'}]))
    assert result['ai_status'] == 'ok'
    assert models == ['fixture-primary:free', 'nvidia/nemotron-3.5-super-vl:free']


def test_invalid_free_response_retries_free_fallback(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'fixture-key')
    monkeypatch.setenv('OPENROUTER_MODEL', 'fixture-primary:free')
    models = []
    class Response:
        def __init__(self, first): self.first = first
        def raise_for_status(self): pass
        def json(self):
            content = {'title': 'T', 'category': 'Idea', 'summary': '', 'connection_type': 'related', 'connection': 'The letter is related.', 'source_ids': ['real'], 'evidence_quotes': [{'source_id': 'real', 'quote': 'Mara hid a rebel letter.'}]}
            return {'choices': [{'message': {'content': 'not json' if self.first else json.dumps(content)}}]}
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            models.append(kwargs['json']['model'])
            return Response(len(models) == 1)
    monkeypatch.setattr(main.httpx, 'AsyncClient', Client)
    result = asyncio.run(main.generate(main.Assist(project_id='p', transcript='letter'), [{'id': 'real', 'text': 'Mara hid a rebel letter.'}]))
    assert result['ai_status'] == 'ok'
    assert models == ['fixture-primary:free', 'nvidia/nemotron-3.5-super-vl:free']


def test_concurrent_confirms_make_at_most_one_write(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    headers = {'Authorization': 'Bearer ' + 'x' * 32}
    monkeypatch.setenv('NOTION_IDEAS_ID', 'ideas')
    calls = []
    async def allow(_): pass
    async def write(method, path, **kwargs):
        calls.append(path)
        await asyncio.sleep(0.25)
        return {'id': 'saved-page'}
    monkeypatch.setattr(main, 'authorize_project', allow)
    monkeypatch.setattr(main, 'notion', write)
    with main.db() as conn:
        conn.execute("INSERT INTO actions (id,project,transcript,status,created,owner_hash) VALUES ('race','p','text','pending',?,'c62e4615bd39e222572f3a1bf7c2132ea1e65b17ec805047bd6b2842c593493f')", (time.time(),))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: c.post('/actions/race/confirm', headers=headers).status_code, range(2)))
    assert sorted(results) == [200, 409]
    assert calls == ['pages']


def test_expired_confirmation_does_not_write(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    monkeypatch.setenv('NOTION_IDEAS_ID', 'ideas')
    async def allow(_): pass
    monkeypatch.setattr(main, 'authorize_project', allow)
    with main.db() as conn:
        conn.execute("INSERT INTO actions (id,project,transcript,status,created,owner_hash) VALUES ('old','p','text','pending',?,'c62e4615bd39e222572f3a1bf7c2132ea1e65b17ec805047bd6b2842c593493f')", (time.time() - 1801,))
    assert c.post('/actions/old/confirm', headers={'Authorization': 'Bearer ' + 'x' * 32}).status_code == 409


def test_assist_is_project_scoped_and_never_writes(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    headers = {'Authorization': 'Bearer ' + 'x' * 32}
    calls = []
    async def fixture_projects():
        return [{'id': 'project-a', 'title': 'A'}, {'id': 'project-b', 'title': 'B'}]
    async def fixture_blocks(project):
        calls.append(project)
        return [{'id': project + '-block', 'text': 'advisor hides letter'}]
    monkeypatch.setattr(main, 'projects', fixture_projects)
    monkeypatch.setattr(main, 'read_blocks', fixture_blocks)
    response = c.post('/assist', headers=headers, json={'project_id': 'project-a', 'transcript': 'advisor letter'})
    assert response.status_code == 200
    assert calls == ['project-a']
    with main.db() as conn:
        row = conn.execute('SELECT status, owner_hash FROM actions WHERE id=?', (response.json()['action_id'],)).fetchone()
        assert row['status'] == 'pending'
        assert row['owner_hash'] == hashlib.sha256(('x' * 32).encode()).hexdigest()
    forbidden = c.post('/assist', headers=headers, json={'project_id': 'outside', 'transcript': 'advisor'})
    assert forbidden.status_code == 403
    assert calls == ['project-a']


def test_status_reconciles_only_one_matching_capture(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    monkeypatch.setenv('NOTION_IDEAS_ID', 'ideas')
    async def lookup(method, path, **kwargs):
        assert kwargs['json']['filter']['rich_text']['equals'] == 'unknown-id'
        return {'results': [{'id': 'actual-page'}], 'has_more': False}
    monkeypatch.setattr(main, 'notion', lookup)
    with main.db() as conn:
        conn.execute("INSERT INTO actions (id,project,transcript,status,created,owner_hash) VALUES ('unknown-id','p','text','unknown',?,'c62e4615bd39e222572f3a1bf7c2132ea1e65b17ec805047bd6b2842c593493f')", (time.time(),))
    response = c.get('/actions/unknown-id', headers={'Authorization': 'Bearer ' + 'x' * 32})
    assert response.json()['status'] == 'saved'
    assert response.json()['notion_id'] == 'actual-page'


def test_other_session_cannot_read_cancel_or_confirm_action(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    other = 'y' * 32
    with main.db() as conn:
        conn.execute('INSERT INTO sessions (token_hash, expires) VALUES (?, ?)', (hashlib.sha256(other.encode()).hexdigest(), time.time() + 3600))
        conn.execute("INSERT INTO actions (id,project,transcript,status,created,owner_hash) VALUES ('private','p','text','pending',?,?)", (time.time(), hashlib.sha256(('x' * 32).encode()).hexdigest()))
        conn.execute("INSERT INTO actions (id,project,transcript,status,created) VALUES ('legacy','p','text','pending',?)", (time.time(),))
    headers = {'Authorization': 'Bearer ' + other}
    assert c.get('/actions/private', headers=headers).status_code == 404
    assert c.post('/actions/private/cancel', headers=headers).status_code == 409
    assert c.post('/actions/private/confirm', headers=headers).status_code == 404
    assert c.get('/actions/legacy', headers=headers).status_code == 404
    with main.db() as conn:
        assert conn.execute("SELECT status FROM actions WHERE id='private'").fetchone()['status'] == 'pending'


def test_legacy_migration_keeps_receipts_but_does_not_assign_owner(tmp_path, monkeypatch):
    path = tmp_path / 'legacy.sqlite3'
    conn = main.sqlite3.connect(path)
    conn.execute('CREATE TABLE actions (id TEXT PRIMARY KEY, project TEXT NOT NULL, transcript TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL, notion_id TEXT)')
    conn.execute("INSERT INTO actions VALUES ('old','p','old text','saved',?,'notion-page')", (time.time(),))
    conn.commit(); conn.close()
    monkeypatch.setattr(main, 'DB', str(path))
    main.init_db()
    with main.db() as conn:
        row = conn.execute("SELECT notion_id, owner_hash FROM actions WHERE id='old'").fetchone()
        assert row['notion_id'] == 'notion-page'
        assert row['owner_hash'] is None


def test_preview_fields_match_confirmed_notion_payload(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    monkeypatch.setenv('NOTION_IDEAS_ID', 'ideas')
    async def fixture_projects(): return [{'id': 'project-a', 'title': 'Fiction'}]
    async def fixture_blocks(_): return [{'id': 'block-a', 'title': 'Chapter 4', 'text': 'Mara hid a rebel letter.', 'url': 'https://notion.example/chapter'}]
    async def fixture_generate(body, sources):
        return {'title': 'ignored', 'category': 'ignored', 'summary': '', 'connection_type': 'related', 'connection': 'Speculative suggestion: Mara might hide another letter.', 'sources': [{**sources[0], 'evidence': 'Mara hid a rebel letter.'}], 'ai_status': 'ok'}
    writes = []
    async def fixture_notion(method, path, **kwargs):
        writes.append(kwargs['json']); return {'id': 'new-page'}
    monkeypatch.setattr(main, 'projects', fixture_projects)
    monkeypatch.setattr(main, 'read_blocks', fixture_blocks)
    monkeypatch.setattr(main, 'generate', fixture_generate)
    monkeypatch.setattr(main, 'notion', fixture_notion)
    headers = {'Authorization': 'Bearer ' + 'x' * 32}
    preview = c.post('/assist', headers=headers, json={'project_id': 'project-a', 'transcript': 'A rebel idea', 'mode': 'brainstorm'}).json()
    assert c.post('/actions/' + preview['action_id'] + '/confirm', headers=headers).status_code == 200
    payload = writes[0]
    assert payload['properties']['Name']['title'][0]['text']['content'] == preview['title']
    assert payload['properties']['Category']['select']['name'] == preview['category'] == 'Brainstorm'
    assert payload['properties']['AI connection']['rich_text'][0]['text']['content'] == preview['connection']
    assert payload['properties']['Project']['relation'][0]['id'] == 'project-a'
    assert payload['children'][0]['paragraph']['rich_text'][0]['text']['content'] == preview['transcript']
    assert preview['sources'][0]['url'] in payload['properties']['Source references']['rich_text'][0]['text']['content']
