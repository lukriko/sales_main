from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Seeds initial users for locations'

    def handle(self, *args, **kwargs):
        USERS = [
            ("batumi_metro", "batumi_metro_2000", ["ბათუმი მეტრო მოლი"]),
            ("batumi_grandi", "batumi_grandi_2001", ["ბათუმი გრანდ მოლი"]),
            ("vake", "vake_200_2002", ["ვაკე 1"]),
            ("plexanovi", "plexanovi_200_2003", ["პლეხანოვი"]),
            ("gudvili2", "gudvili2_200_2004", ["გუდვილი 2"]),
            ("gldani", "gldani_200_2005", ["გლდანი"]),
            ("rustavi", "rustavi_201_2000", ["რუსთავი"]),
            ("gori", "gori_201_2001", ["გორი"]),
            ("gudvili", "gudvili_200_2006", ["გუდვილი"]),
            ("gldani_siti", "gldani_siti_200_2007", ["გლდანი სითი მოლი"]),
            ("galerea", "galerea_200_2008", ["გალერია"]),
            ("east_point", "east_point_200_2009", ["ისტ პოინტი"]),
            ("merani", "merani_200_2010", ["მერანი"]),
            ("pekini", "pekini_200_2011", ["პეკინი"]),
        ]

        for username, password, locations in USERS:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f'✓ Created user: {username}'))
            else:
                self.stdout.write(self.style.WARNING(f'- User already exists: {username}'))

        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully processed {len(USERS)} users'))