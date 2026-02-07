from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    allowed_locations = models.JSONField(default=list, blank=True)
    # Store as: ["გალერია", "გუდვილი 2", ...]
    
    is_admin = models.BooleanField(default=False)  # Can see all locations
    
    def __str__(self):
        return f"{self.user.username} - {len(self.allowed_locations)} locations"
    
    def can_access_location(self, location_name):
        """Check if user can access a specific location"""
        if self.is_admin:
            return True
        return location_name in self.allowed_locations
    
    def get_allowed_locations(self):
        """Return list of allowed locations for filtering"""
        if self.is_admin:
            return []  # Empty list means all locations
        return self.allowed_locations


class Sales(models.Model):
    # Set idreal1 as the primary key to prevent Django from adding 'id'
    idreal1 = models.BigIntegerField(db_column='IdReal1', primary_key=True)
    
    zedd = models.TextField(db_column='Zedd', blank=True, null=True)
    cd = models.DateTimeField(db_column='CD', blank=True, null=True)
    un = models.TextField(db_column='UN', blank=True, null=True)
    idtanam = models.BigIntegerField(db_column='IdTanam', blank=True, null=True)
    idprod = models.TextField(db_column='IdProd', blank=True, null=True)
    idactions = models.TextField(db_column='IdActions', blank=True, null=True)
    raod = models.FloatField(blank=True, null=True)
    discount_price = models.FloatField(db_column='discount_price',blank=True, null=True)
    sachuqari = models.FloatField(db_column='Sachuqari', blank=True, null=True)
    std_price = models.FloatField(db_column='std_price',blank=True, null=True)
    tanxa = models.FloatField(db_column='Tanxa', blank=True, null=True)
    prod = models.TextField(db_column='Prod', blank=True, null=True)
    idprodt = models.BigIntegerField(db_column='IdProdT', blank=True, null=True)
    idprodg = models.BigIntegerField(db_column='IdProdG', blank=True, null=True)
    desc1 = models.TextField(db_column='Desc1', blank=True, null=True)
    prodt = models.TextField(db_column='ProdT', blank=True, null=True)
    prodg = models.TextField(db_column='ProdG', blank=True, null=True)
    actions = models.TextField(db_column='Actions', blank=True, null=True)
    tanam = models.TextField(db_column='Tanam', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sales_main_web'
        indexes = [
            # Core date + location filters
            models.Index(fields=['cd', 'un'], name='sales_cd_un_idx'),
            models.Index(fields=['cd', 'prodg'], name='sales_cd_prodg_idx'),
            models.Index(fields=['zedd', 'cd'], name='sales_zedd_cd_idx'),
            models.Index(fields=['tanam', 'cd'], name='sales_tanam_cd_idx'),
            models.Index(fields=['prod', 'cd'], name='sales_prod_cd_idx'),
            
            # Employee analytics specific
            models.Index(fields=['tanam', 'cd', 'prodg'], name='sales_emp_date_cat_idx'),
            models.Index(fields=['tanam', 'prodt', 'cd'], name='sales_emp_type_date_idx'),
            models.Index(fields=['zedd', 'tanam'], name='sales_ticket_emp_idx'),
        ]

    def __str__(self):
        return f"Ticket {self.zedd} - {self.un} - ${self.tanxa}"