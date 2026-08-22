from pymilvus import MilvusClient

client = MilvusClient(uri='http://119.45.115.152:19530')
results = client.query(
    collection_name='knowledge_units',
    filter='unit_id == "3cbf44fe6a5a"',
    output_fields=['chunk_text', 'chunk_index'],
    limit=50,
)

print(f'Total chunks: {len(results)}')
for r in results:
    text = r['chunk_text']
    idx = text.find('1782981609557')
    if idx >= 0:
        print(f'\n=== Chunk {r["chunk_index"]} (len={len(text)}) ===')
        print(text[max(0, idx-30):idx+100])
        print('---')

# Also check for any image references
import re
for r in results:
    text = r['chunk_text']
    refs = re.findall(r'!\[.*?\]\([^)]+\)', text)
    if refs:
        print(f'\nChunk {r["chunk_index"]} images:')
        for ref in refs:
            print(f'  {ref[:120]}')