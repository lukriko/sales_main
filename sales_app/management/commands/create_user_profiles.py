from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from sales_app.models import UserProfile  # Change 'sales_app' to your app name

class Command(BaseCommand):
    help = 'Create user profiles for existing users'
    
    def handle(self, *args, **kwargs):
        created_count = 0
        existing_count = 0
        
        for user in User.objects.all():
            profile, created = UserProfile.objects.get_or_create(user=user)
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Created profile for user: {user.username}')
                )
            else:
                existing_count += 1
                self.stdout.write(
                    self.style.WARNING(f'- Profile already exists for: {user.username}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: {created_count} profiles created, {existing_count} already existed'
            )
        )