from django.db import migrations

class Migration(migrations.Migration):
    atomic = False
    
    dependencies = [
        ("sales_app", "0003_add_performance_indexes"),
    ]
    
    operations = [
        # Clean up duplicate/unnecessary indexes first
        migrations.RunSQL(
            """
            -- Drop potentially duplicate indexes from 0002/0003
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_un;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prodg;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prod;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_actions;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_idtanam;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_zedd;
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_prodt;
            
            -- Vacuum to reclaim space
            VACUUM ANALYZE sales_main_web;
            """,
            migrations.RunSQL.noop,
        ),
        
        # Now create ONLY the most critical indexes
        migrations.RunSQL(
            'SET statement_timeout = 600000;',
            migrations.RunSQL.noop,
        ),
        
        # Index 1: Year filtering (CRITICAL - used everywhere)
        migrations.RunSQL(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_year 
            ON sales_main_web (EXTRACT(YEAR FROM "CD"), "CD");
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_year;',
        ),
        
        # Index 2: Composite for common filters (replaces idx_sales_cd_composite)
        migrations.RunSQL(
            """
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_composite;
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_un_prodg 
            ON sales_main_web ("CD", "UN", "ProdG") 
            WHERE "UN" NOT IN ('მთავარი საწყობი 2', 'სატესტო');
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_un_prodg;',
        ),
        
        # Index 3: Ticket counting (CRITICAL - optimize the existing one)
        migrations.RunSQL(
            """
            DROP INDEX CONCURRENTLY IF EXISTS idx_sales_zedd_cd;
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_zedd 
            ON sales_main_web ("CD", "Zedd");
            """,
            'DROP INDEX CONCURRENTLY IF EXISTS idx_sales_cd_zedd;',
        ),
        
        migrations.RunSQL(
            'RESET statement_timeout;',
            migrations.RunSQL.noop,
        ),
    ]