from django.contrib import admin
from users.models import ClientProfile, ProviderProfile, Property


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'phone', 'city', 'id_number', 'created_at')
    list_filter = ('city', 'country', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'phone', 'id_number')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Personal Information', {
            'fields': ('phone', 'id_number')
        }),
        ('Address', {
            'fields': ('address', 'city', 'country', 'postal_code')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_full_name.short_description = 'Name'


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'company_name', 'phone', 'city', 'created_at')
    list_filter = ('city', 'country', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'phone', 'company_name', 'tax_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Company Information', {
            'fields': ('company_name', 'tax_id')
        }),
        ('Contact Information', {
            'fields': ('phone',)
        }),
        ('Address', {
            'fields': ('address', 'city', 'country', 'postal_code')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    get_full_name.short_description = 'Name'


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'property_type', 'bedrooms', 'bathrooms', 'monthly_price', 'is_active', 'created_at')
    list_filter = ('property_type', 'city', 'is_active', 'created_at')
    search_fields = ('name', 'address', 'city', 'provider__user__first_name', 'provider__user__last_name')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('provider', 'name', 'description', 'property_type')
        }),
        ('Features', {
            'fields': ('bedrooms', 'bathrooms', 'square_meters')
        }),
        ('Address', {
            'fields': ('address', 'city', 'country', 'postal_code')
        }),
        ('Pricing', {
            'fields': ('monthly_price',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

