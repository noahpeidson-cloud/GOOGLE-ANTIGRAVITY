import sqlite3
import json
conn = sqlite3.connect('media_manifest.sqlite')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT * FROM asset_manifest WHERE source_file_name LIKE '%Baptism%' OR metadata_json LIKE '%Baptism%'")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(dict(row))
else:
    print("No matching records found.")
