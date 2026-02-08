from django.db import migrations

class Migration(migrations.Migration):
    atomic = False
    
    dependencies = [
        ("sales_app", "0002_auto_20250208_0647"),  # Update to your last migration
    ]
    
    operations = [
        # Most critical index - date filtering
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_composite ON sales_main_web (cd, un, prodg);',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_composite;',
        ),
        
        # Zedd for DISTINCT counts (critical for performance)
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_zedd_cd ON sales_main_web (zedd, cd);',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_zedd_cd;',
        ),
    ]