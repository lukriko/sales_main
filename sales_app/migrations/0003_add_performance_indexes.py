from django.db import migrations

class Migration(migrations.Migration):
    atomic = False
    
    dependencies = [
        ("sales_app", "0001_initial"),  # ← Change this to match your actual last migration
    ]
    
    operations = [
        # Composite index for common filter patterns
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_composite ON sales_main_web (cd, un, prodg);',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_composite;',
        ),
        
        # Index for ticket counting
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_zedd_cd ON sales_main_web (zedd, cd);',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_zedd_cd;',
        ),
    ]