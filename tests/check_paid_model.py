"""Explicitly approved live model check; uses fictional Notion content only.

This makes at most three billable OpenRouter calls. Run only after approval:
    python tests/check_paid_model.py --allow-paid
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

if sys.argv[1:] != ['--allow-paid']:
    raise SystemExit('Requires explicit approval: pass --allow-paid')
for key, value in dotenv_values('.env').items():
    if value is not None:
        os.environ[key] = value
os.environ['OPENROUTER_MODEL'] = 'openai/gpt-4.1-nano'
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services' / 'api'))
from scribe import main


async def run():
    projects = await main.projects()
    project = next(p for p in projects if p['title'] == 'The Forgotten King')
    sources = main.rank('advisor rebel letter', await main.read_blocks(project['id']))
    for index in range(3):
        result = await main.generate(main.Assist(project_id=project['id'], transcript='What if the advisor secretly supports the rebellion?'), sources)
        print(f"Run {index + 1}: type={result['connection_type']}, sources={len(result['sources'])}, connection={result['connection']}", flush=True)


if __name__ == '__main__':
    asyncio.run(run())
