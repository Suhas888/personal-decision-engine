import re
files = ['tests/pg/test_pg_crud.py', 'tests/pg/test_pg_security.py', 'tests/pg/test_pg_commands.py']

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix priority in task creation
    content = re.sub(r'"estimated_minutes": (\d+)(?!\s*,\s*"priority")', r'"estimated_minutes": \1, "priority": 1', content)
    content = content.replace('"priority": 1, "completed"', '"priority": 1, "completed"')
    
    # Fix event creation:
    pattern = r'"title": "([^"]+)",\s*"start_datetime": "[^"]+",\s*"end_datetime": "[^"]+"'
    repl = r'"title": "\1", "day_of_week": "Monday", "start_time": 540, "end_time": 600'
    content = re.sub(pattern, repl, content)
    
    # For test_pg_crud complete task update: it had "estimated_minutes": 30, "completed": True.
    # It will get replaced to "estimated_minutes": 30, "priority": 1, "completed": True which is correct.
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
print('Fixed payload shapes.')
