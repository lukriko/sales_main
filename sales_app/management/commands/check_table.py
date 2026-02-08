# sales_app/management/commands/check_table.py
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE '%sales%'
            """)
            tables = cursor.fetchall()
            self.stdout.write(f"Sales tables: {tables}")
            
            # Check indexes
            cursor.execute("""
                SELECT indexname, tablename 
                FROM pg_indexes 
                WHERE tablename LIKE '%sales%'
            """)
            indexes = cursor.fetchall()
            self.stdout.write(f"\nIndexes: {indexes}")