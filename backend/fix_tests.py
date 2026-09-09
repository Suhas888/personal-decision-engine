import os
import re
import glob

files = glob.glob('tests/test_*.py')
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Add user_id="default_user" to Task and FixedEvent if missing
    new_content = re.sub(r'Task\((?!user_id=)', r'Task(user_id="default_user", ', content)
    new_content = re.sub(r'FixedEvent\((?!user_id=)', r'FixedEvent(user_id="default_user", ', new_content)
    new_content = re.sub(r'DynamicConstraint\((?!user_id=)', r'DynamicConstraint(user_id="default_user", ', new_content)
    
    # clean up trailing commas
    new_content = new_content.replace('user_id="default_user", )', 'user_id="default_user")')
    
    if content != new_content:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(new_content)
        print(f"Updated {f}")
