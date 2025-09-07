# Generated custom migration to change user_id from integer to UUID

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            # Drop and recreate the column as UUID since table is empty
            sql=[
                "ALTER TABLE monitoring.developer_sessions DROP COLUMN user_id;",
                "ALTER TABLE monitoring.developer_sessions ADD COLUMN user_id UUID NOT NULL;",
            ],
            reverse_sql=[
                "ALTER TABLE monitoring.developer_sessions DROP COLUMN user_id;", 
                "ALTER TABLE monitoring.developer_sessions ADD COLUMN user_id INTEGER NOT NULL;",
            ]
        ),
    ]