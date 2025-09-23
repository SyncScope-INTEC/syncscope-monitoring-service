# Generated manually to safely handle table renames for monitoring schema
from django.db import migrations, connection


def check_and_rename_tables(apps, schema_editor):
    """
    Safely rename tables to monitoring schema only if needed.
    """
    if connection.vendor == 'sqlite':
        # For SQLite (tests), we don't use schema prefixes
        return

    # For PostgreSQL, check if tables exist and rename only if needed
    cursor = connection.cursor()

    # Table mappings: old_name -> new_name
    table_mappings = {
        'monitoring_activitylog': 'monitoring.activity_logs',
        'monitoring_codemetrics': 'monitoring.code_metrics',
        'monitoring_developersession': 'monitoring.developer_sessions',
        'monitoring_gitevent': 'monitoring.git_events',
    }

    # Check which tables exist in the current schema
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema IN ('monitoring', 'public')
        AND table_name LIKE 'monitoring_%' OR table_name LIKE 'activity_logs' OR table_name LIKE 'code_metrics' OR table_name LIKE 'developer_sessions' OR table_name LIKE 'git_events'
    """)

    existing_tables = set(row[0] for row in cursor.fetchall())

    # Also check monitoring schema specifically
    cursor.execute("""
        SELECT schemaname || '.' || tablename as full_name
        FROM pg_tables
        WHERE schemaname = 'monitoring'
    """)

    existing_schema_tables = set(row[0] for row in cursor.fetchall())

    for old_name, new_name in table_mappings.items():
        # Extract just the table name from new_name (after the dot)
        new_table_name = new_name.split('.')[-1]

        if new_name in existing_schema_tables:
            print(f"Table {new_name} already exists in monitoring schema, skipping rename")
        elif old_name in existing_tables:
            try:
                # Rename to monitoring schema
                cursor.execute(f'ALTER TABLE "{old_name}" SET SCHEMA monitoring;')
                cursor.execute(f'ALTER TABLE monitoring."{old_name.replace("monitoring_", "")}" RENAME TO "{new_table_name}";')
                print(f"Renamed {old_name} to {new_name}")
            except Exception as e:
                print(f"Could not rename {old_name} to {new_name}: {e}")
        else:
            print(f"Table {old_name} not found, probably already in correct schema as {new_name}")


def reverse_rename_tables(apps, schema_editor):
    """
    Reverse the table renames if needed.
    """
    # For reverse migration, we'd rename back, but this is usually not needed
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            check_and_rename_tables,
            reverse_rename_tables,
        ),
    ]