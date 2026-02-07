# sales_app/migrations/0XXX_add_performance_indexes.py
from django.db import migrations


class Migration(migrations.Migration):
    
    dependencies = [
        ('sales_app', '0001_initial'),  # ← Change this to your last migration
    ]

    operations = [
        # Date-based indexes (CRITICAL for your date filters)
        migrations.RunSQL(
            sql="""
            -- Index on CD field (used in almost every query)
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd 
            ON sales_main_web (CD);
            
            -- Index on CD + UN (location + date combination - VERY COMMON)
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_cd_un 
            ON sales_main_web (CD, UN);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_sales_cd;
            DROP INDEX IF EXISTS idx_sales_cd_un;
            """
        ),
        
        # Location and category indexes
        migrations.RunSQL(
            sql="""
            -- Index on UN (location filter)
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_un 
            ON sales_main_web (UN);
            
            -- Index on ProdG (category filter)
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prodg 
            ON sales_main_web (ProdG);
            
            -- Index on Prod (product filter)
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prod 
            ON sales_main_web (Prod);
            
            -- Index on Actions (campaign filter)
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_actions 
            ON sales_main_web (Actions);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_sales_un;
            DROP INDEX IF EXISTS idx_sales_prodg;
            DROP INDEX IF EXISTS idx_sales_prod;
            DROP INDEX IF EXISTS idx_sales_actions;
            """
        ),
        
        # Employee and ticket indexes
        migrations.RunSQL(
            sql="""
            -- Index on Tanam (employee name for analytics)
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_tanam 
            ON sales_main_web (Tanam);
            
            -- Index on Zedd (ticket ID for grouping)
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_zedd 
            ON sales_main_web (Zedd);
            
            -- Index on ProdT (selling item filter)
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sales_prodt 
            ON sales_main_web (ProdT);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_sales_tanam;
            DROP INDEX IF EXISTS idx_sales_zedd;
            DROP INDEX IF EXISTS idx_sales_prodt;
            """
        ),
    ]