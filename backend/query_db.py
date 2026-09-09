import sqlite3

conn = sqlite3.connect("pde.db")
cursor = conn.cursor()
cursor.execute("SELECT sql FROM sqlite_master;")
schema = cursor.fetchall()
for s in schema:
    print(s[0])
