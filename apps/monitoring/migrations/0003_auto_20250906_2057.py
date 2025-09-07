# Manual migration to fix Django ORM sync with database schema

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0002_alter_developersession_user_id_to_uuid'),
    ]

    operations = [
        # This ensures Django's internal state matches the database
        migrations.RunSQL(
            sql="SELECT 1;",  # No-op SQL
            reverse_sql="SELECT 1;",
            state_operations=[
                migrations.AlterField(
                    model_name='developersession',
                    name='user_id',
                    field=models.UUIDField(help_text="Reference to auth.users.id"),
                ),
            ],
        ),
    ]
