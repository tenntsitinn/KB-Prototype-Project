import asyncio, asyncpg, re

async def main():
    conn = await asyncpg.connect('postgresql://kb_user:kb_pass@119.45.220.37:5432/knowledge_base')
    row = await conn.fetchrow('SELECT content FROM knowledge_units WHERE id = $1', '3cbf44fe6a5a')
    text = row['content']

    pattern = r'!\[(.*?)\]\(([^)]+)\)'
    matches = list(re.finditer(pattern, text))
    print(f'Total markdown image refs: {len(matches)}')
    for m in matches:
        print(f'  alt={m.group(1)[:40]}... url={m.group(2)[:80]}')

    print(f'Lines containing 1782981609557:')
    for i, line in enumerate(text.split('\n')):
        if '1782981609557' in line:
            print(f'  Line {i}: {line[:200]}')

    await conn.close()

asyncio.run(main())