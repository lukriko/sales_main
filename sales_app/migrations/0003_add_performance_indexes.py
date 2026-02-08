from django.db import migrations

class Migration(migrations.Migration):
    atomic = False
    
    dependencies = [
        ("sales_app", "0002_add_performance_indexes"),  # ← Changed from 0001_initial
    ]
    
    operations = [
        # Composite index for common filter patterns
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_composite ON sales_main_web ("CD", "UN", "ProdG");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_composite;',
        ),
        
        # Index for ticket counting (zedd + cd)
        migrations.RunSQL(
            'CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_zedd_cd ON sales_main_web ("Zedd", "CD");',
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_zedd_cd;',
        ),
    ]