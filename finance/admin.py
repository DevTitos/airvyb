from django.contrib import admin
from .models import Transaction, Wallet


# Register your models here.
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['reference', 'user', 'transaction_type', 'amount', 'status', 'initiated_at']
    list_filter = ['transaction_type', 'status', 'initiated_at']
    search_fields = ['reference', 'user__email', 'description']
    readonly_fields = ['initiated_at', 'completed_at']

admin.site.register(Wallet)