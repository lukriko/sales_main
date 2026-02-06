from django.contrib import admin
from .models import Sales

@admin.register(Sales)
class SalesAdmin(admin.ModelAdmin):
    # This controls which columns show up in the dashboard
    list_display = ('un', 'tanxa', 'cd')
    
    # This adds a filter sidebar for the year 2026
    list_filter = ('cd', 'un')
    
    # This adds a search bar for the 'un' field
    search_fields = ('un',)

# admin.py
from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_admin', 'location_count', 'locations_preview']
    list_filter = ['is_admin']
    search_fields = ['user__username', 'user__email']
    
    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Access Control', {
            'fields': ('is_admin', 'allowed_locations'),
            'description': 'Admins can see all locations. Regular users only see their assigned locations.'
        }),
    )
    
    def location_count(self, obj):
        if obj.is_admin:
            return "All"
        return len(obj.allowed_locations)
    location_count.short_description = 'Locations'
    
    def locations_preview(self, obj):
        if obj.is_admin:
            return "Full Access"
        if len(obj.allowed_locations) <= 3:
            return ", ".join(obj.allowed_locations)
        return f"{', '.join(obj.allowed_locations[:3])}... (+{len(obj.allowed_locations)-3} more)"
    locations_preview.short_description = 'Assigned Locations'