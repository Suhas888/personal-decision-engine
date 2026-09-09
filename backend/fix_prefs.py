import re
with open(r'tests\pg\test_pg_crud.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('pg_client.post("/api/preferences/"', 'pg_client.put("/api/preferences/"')

with open(r'tests\pg\test_pg_crud.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Done fixing preferences PUT")
