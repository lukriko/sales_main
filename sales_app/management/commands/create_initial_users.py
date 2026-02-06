from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from sales_app.models import UserProfile  # Change to your app name

class Command(BaseCommand):
    help = 'Create initial users with their profiles'
    
    def handle(self, *args, **kwargs):
        # Create admin user
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_user(
                username='admin',
                email='admin@example.com',
                password='admin123'  # Change this!
            )
            admin_user.is_staff = True  # Can access Django admin
            admin_user.is_superuser = True  # Full permissions
            admin_user.save()
            
            UserProfile.objects.create(user=admin_user, is_admin=True)
            self.stdout.write(self.style.SUCCESS('✓ Created admin user'))
        else:
            self.stdout.write(self.style.WARNING('- Admin user already exists'))
        
        # Create location-specific users
        users_data = [
            {
                'username': 'batumi_manager',
                'email': 'batumi@example.com',
                'password': 'batumi123',
                'locations': ['ბათუმი მეტრო მოლი', 'ბათუმი გრანდ მოლი', 'ბათუმი1']
            },
            {
                'username': 'tbilisi_manager',
                'email': 'tbilisi@example.com',
                'password': 'tbilisi123',
                'locations': ['გალერია', 'ისტ პოინტი', 'გლდანი', 'ვაკე 1']
            },
            {
                'username': 'gldani_user',
                'email': 'gldani@example.com',
                'password': 'gldani123',
                'locations': ['გლდანი', 'გლდანი სითი მოლი']
            },
        ]
        
        for user_data in users_data:
            if not User.objects.filter(username=user_data['username']).exists():
                user = User.objects.create_user(
                    username=user_data['username'],
                    email=user_data['email'],
                    password=user_data['password']
                )
                UserProfile.objects.create(
                    user=user,
                    allowed_locations=user_data['locations']
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created {user_data['username']} with {len(user_data['locations'])} locations"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"- {user_data['username']} already exists")
                )
        
        self.stdout.write(self.style.SUCCESS('\n✓ Initial users setup complete!'))
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('  Admin: admin / admin123')
        self.stdout.write('  Batumi: batumi_manager / batumi123')
        self.stdout.write('  Tbilisi: tbilisi_manager / tbilisi123')
        self.stdout.write('  Gldani: gldani_user / gldani123')
        self.stdout.write(self.style.WARNING('\n⚠ CHANGE THESE PASSWORDS IN PRODUCTION!'))