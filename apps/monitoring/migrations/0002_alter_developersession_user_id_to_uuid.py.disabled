# Generated custom migration to change user_id from integer to UUID

from django.db import migrations, models


def change_user_id_to_uuid(apps, schema_editor):
    """Forward migration: change user_id from integer to UUID"""
    with schema_editor.connection.cursor() as cursor:
        # Create schema if it doesn't exist
        cursor.execute("CREATE SCHEMA IF NOT EXISTS monitoring;")
        
        # Check if the table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'monitoring' 
                AND table_name = 'developer_sessions'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            # Drop the old column and add the new UUID column
            cursor.execute("ALTER TABLE monitoring.developer_sessions DROP COLUMN IF EXISTS user_id;")
            cursor.execute("ALTER TABLE monitoring.developer_sessions ADD COLUMN user_id UUID NOT NULL;")


def revert_user_id_to_integer(apps, schema_editor):
    """Reverse migration: change user_id from UUID back to integer"""
    with schema_editor.connection.cursor() as cursor:
        # Check if the table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'monitoring' 
                AND table_name = 'developer_sessions'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            # Drop the UUID column and add back the integer column
            cursor.execute("ALTER TABLE monitoring.developer_sessions DROP COLUMN IF EXISTS user_id;")
            cursor.execute("ALTER TABLE monitoring.developer_sessions ADD COLUMN user_id INTEGER NOT NULL;")


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            code=change_user_id_to_uuid,
            reverse_code=revert_user_id_to_integer,
        ),
    ]