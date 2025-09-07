# Final fix for UUID user_id field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monitoring', '0003_auto_20250906_2057'),
    ]

    operations = [
        # This migration ensures the user_id field is properly set to UUID type
        # It handles both existing databases and fresh test databases
        migrations.RunSQL(
            sql="""
                -- Ensure schema exists
                CREATE SCHEMA IF NOT EXISTS monitoring;
                
                -- Check if table exists and column type is wrong
                DO $$
                BEGIN
                    -- If table exists and user_id is integer, convert it
                    IF EXISTS (SELECT 1 FROM information_schema.tables 
                              WHERE table_schema = 'monitoring' 
                              AND table_name = 'developer_sessions') THEN
                        
                        -- Check if user_id is integer type
                        IF EXISTS (SELECT 1 FROM information_schema.columns 
                                  WHERE table_schema = 'monitoring' 
                                  AND table_name = 'developer_sessions' 
                                  AND column_name = 'user_id' 
                                  AND data_type = 'integer') THEN
                            
                            -- Drop and recreate as UUID
                            ALTER TABLE monitoring.developer_sessions DROP COLUMN user_id;
                            ALTER TABLE monitoring.developer_sessions ADD COLUMN user_id UUID NOT NULL;
                        END IF;
                    END IF;
                END $$;
            """,
            reverse_sql="""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.tables 
                              WHERE table_schema = 'monitoring' 
                              AND table_name = 'developer_sessions') THEN
                        
                        -- Check if user_id is UUID type
                        IF EXISTS (SELECT 1 FROM information_schema.columns 
                                  WHERE table_schema = 'monitoring' 
                                  AND table_name = 'developer_sessions' 
                                  AND column_name = 'user_id' 
                                  AND data_type = 'uuid') THEN
                            
                            -- Drop and recreate as integer
                            ALTER TABLE monitoring.developer_sessions DROP COLUMN user_id;
                            ALTER TABLE monitoring.developer_sessions ADD COLUMN user_id INTEGER NOT NULL;
                        END IF;
                    END IF;
                END $$;
            """
        ),
    ]
