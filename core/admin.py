from django.contrib import admin
from .models import (
    Venture, VentureDocument, Investment, Dividend, AuditLog, UserPortfolio, Notification
)

@admin.register(Venture)
class VentureAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'venture_type', 'status', 'total_value', 'percentage_funded']
    list_filter = ['venture_type', 'status', 'risk_level']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['price_per_share', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'name', 'description', 'venture_type', 'status')
        }),
        ('Financial Details', {
            'fields': ('total_value', 'minimum_investment', 'shares_available', 'shares_issued')
        }),
        ('Governance', {
            'fields': ('governance_board', 'risk_level')
        }),
        ('Timeline', {
            'fields': ('start_date', 'expected_end_date')
        }),
        ('System', {
            'fields': ('price_per_share', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    list_display = ['reference', 'investor', 'venture', 'shares', 'amount_invested', 'status']
    list_filter = ['status', 'venture__venture_type']
    search_fields = ['reference', 'investor__email', 'venture__name']
    readonly_fields = ['share_price_at_purchase', 'invested_at', 'confirmed_at']
    raw_id_fields = ['investor', 'venture']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['user__email', 'model_name']
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False

admin.site.register(VentureDocument)
admin.site.register(Dividend)
admin.site.register(UserPortfolio)
admin.site.register(Notification)