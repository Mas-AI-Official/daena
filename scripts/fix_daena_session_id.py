#!/usr/bin/env python3
"""Fix daena.py to add session_id to chat/start response"""
import codecs
import os

file_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'routes', 'daena.py')

with codecs.open(file_path, 'r', 'utf-8') as f:
    lines = f.readlines()

modified = False
for i, line in enumerate(lines):
    if '"session": session,' in line and 140 < i < 150:
        # Check if session_id already added
        if i > 0 and 'session_id' not in lines[i-1]:
            # Insert session_id line before this
            indent = '        '
            lines.insert(i, indent + '"session_id": session_id,\r\n')
            print(f'Inserted session_id at line {i+1}')
            modified = True
        else:
            print('session_id already exists')
        break

if modified:
    with codecs.open(file_path, 'w', 'utf-8') as f:
        f.writelines(lines)
    print('File saved')
else:
    print('No changes made')
