from django.db import migrations

class Migration(migrations.Migration):
    atomic = False
    
    dependencies = [
        ("sales_app", "0002_add_performance_indexes"),
    ]
    
    operations = [
        # Set statement timeout to 10 minutes
        migrations.RunSQL(
            'SET statement_timeout = 600000;',
            migrations.RunSQL.noop,
        ),
        
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
        
        # Reset timeout
        migrations.RunSQL(
            'SET statement_timeout = 30000;',
            migrations.RunSQL.noop,
        ),
    ]