import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

cursor = connection.cursor()

print("Checking monitoring.code_metrics:")
cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'monitoring' 
    AND table_name = 'code_metrics'
""")
print([row[0] for row in cursor.fetchall()])

print("\nChecking monitoring.\"monitoring.code_metrics\":")
cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_schema = 'monitoring' 
    AND table_name = 'monitoring.code_metrics'
""")
print([row[0] for row in cursor.fetchall()])
