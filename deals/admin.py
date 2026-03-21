from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum
from .models import (
    Deal, DealCategory, DealOptIn, DealRevenue, 
    DealCost, DealProfitDistribution, DealReport, DealUpdate
)

class DealOptInInline(admin.TabularInline):
    """Inline for deal opt-ins"""
    model = DealOptIn
    extra = 0
    readonly_fields = ['reference', 'amount', 'status', 'paid_at', 'created_at']
    fields = ['user', 'reference', 'amount', 'status', 'paid_at']
    can_delete = False
    max_num = 0


class DealRevenueInline(admin.TabularInline):
    """Inline for deal revenues"""
    model = DealRevenue
    extra = 1
    fields = ['period_start', 'period_end', 'amount', 'description']


class DealCostInline(admin.TabularInline):
    """Inline for deal costs"""
    model = DealCost
    extra = 1
    fields = ['cost_type', 'period_start', 'period_end', 'amount', 'description']


class DealUpdateInline(admin.TabularInline):
    """Inline for deal updates"""
    model = DealUpdate
    extra = 1
    fields = ['title', 'content', 'is_important', 'created_at']
    readonly_fields = ['created_at']


@admin.register(DealCategory)
class DealCategoryAdmin(admin.ModelAdmin):
    """Admin for deal categories"""
    list_display = ['name', 'icon_display', 'order', 'is_active', 'deals_count']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'description']
    
    def icon_display(self, obj):
        return format_html('<i class="fas fa-{}" style="font-size: 1.2rem;"></i>', obj.icon)
    icon_display.short_description = 'Icon'
    
    def deals_count(self, obj):
        return obj.deals.count()
    deals_count.short_description = 'Deals'


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    """Admin for deals"""
    list_display = [
        'reference', 'title', 'category', 'status', 'risk_level',
        'opt_in_amount_display', 'total_opted_in', 'progress_percentage_display',
        'created_at'
    ]
    list_filter = ['status', 'risk_level', 'category', 'created_at']
    search_fields = ['title', 'reference', 'objective', 'description']
    prepopulated_fields = {'slug': ['title']}
    readonly_fields = [
        'reference', 'total_opted_in', 'total_collected', 'created_at', 'updated_at',
        'progress_display', 'financial_summary'
    ]
    fieldsets = [
        ('Basic Information', {
            'fields': [
                'title', 'slug', 'reference', 'category', 'cover_image'
            ]
        }),
        ('Deal Details', {
            'fields': [
                'objective', 'description', 'expected_operations'
            ]
        }),
        ('Financial Settings', {
            'fields': [
                'opt_in_amount', 'total_capital_required',
                'min_opt_in_members', 'max_opt_in_members',
                'management_fee_percent', 'performance_carry_percent'
            ]
        }),
        ('Risk & Duration', {
            'fields': [
                'risk_level', 'duration_months'
            ]
        }),
        ('Timeline', {
            'fields': [
                'disclosed_at', 'opt_in_start', 'opt_in_end', 'launched_at', 'closed_at'
            ]
        }),
        ('Status', {
            'fields': [
                'status', 'created_by'
            ]
        }),
        ('Statistics', {
            'fields': [
                'total_opted_in', 'total_collected', 'progress_display', 'financial_summary'
            ]
        }),
        ('Metadata', {
            'fields': [
                'created_at', 'updated_at'
            ],
            'classes': ['collapse']
        }),
    ]
    inlines = [DealOptInInline, DealRevenueInline, DealCostInline, DealUpdateInline]
    actions = ['mark_as_active', 'mark_as_opt_in_open', 'generate_report']
    
    def opt_in_amount_display(self, obj):
        return format_html('Ksh {}', '{:,}'.format(obj.opt_in_amount))
    opt_in_amount_display.short_description = 'Opt-In Amount'
    
    def progress_percentage_display(self, obj):
        progress = obj.progress_percentage
        color = '#00c853' if progress >= 100 else '#ffc107' if progress >= 50 else '#ff4444'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, int(progress)
        )
    progress_percentage_display.short_description = 'Progress'
    
    def progress_display(self, obj):
        progress = int(obj.progress_percentage)
        return format_html("""
            <div style="width: 100%; background: rgba(255,255,255,0.1); border-radius: 5px;">
                <div style="width: {}%; background: linear-gradient(90deg, #ff006e, #ffb300); 
                            height: 20px; border-radius: 5px; text-align: center; color: white; 
                            font-size: 12px; line-height: 20px;">
                    {}%
                </div>
            </div>
            <div style="margin-top: 10px;">
                <strong>Opted In:</strong> {} | <strong>Collected:</strong> Ksh {}
            </div>
        """, 
            progress, 
            progress, 
            obj.total_opted_in, 
            '{:,}'.format(obj.total_collected)
        )
    progress_display.short_description = 'Progress Details'
    
    def financial_summary(self, obj):
        total_revenue = obj.revenues.aggregate(Sum('amount'))['amount__sum'] or 0
        total_costs = obj.costs.aggregate(Sum('amount'))['amount__sum'] or 0
        net_profit = total_revenue - total_costs
        
        return format_html("""
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 10px;">
                <div style="background: rgba(0,200,83,0.1); padding: 10px; border-radius: 5px; text-align: center;">
                    <div style="color: #00c853; font-size: 12px;">REVENUE</div>
                    <div style="font-weight: bold;">Ksh {}</div>
                </div>
                <div style="background: rgba(255,0,110,0.1); padding: 10px; border-radius: 5px; text-align: center;">
                    <div style="color: #ff006e; font-size: 12px;">COSTS</div>
                    <div style="font-weight: bold;">Ksh {}</div>
                </div>
                <div style="background: rgba(255,193,7,0.1); padding: 10px; border-radius: 5px; text-align: center;">
                    <div style="color: #ffc107; font-size: 12px;">NET PROFIT</div>
                    <div style="font-weight: bold;">Ksh {}</div>
                </div>
            </div>
        """, 
            '{:,}'.format(total_revenue),
            '{:,}'.format(total_costs),
            '{:,}'.format(net_profit)
        )
    financial_summary.short_description = 'Financial Summary'
    
    def mark_as_active(self, request, queryset):
        queryset.update(status='active')
    mark_as_active.short_description = "Mark selected deals as Active"
    
    def mark_as_opt_in_open(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            status='opt_in_open',
            opt_in_start=timezone.now(),
            opt_in_end=timezone.now() + timezone.timedelta(days=30)
        )
    mark_as_opt_in_open.short_description = "Open for opt-in (30 days)"
    
    def generate_report(self, request, queryset):
        # This would redirect to a report generation page
        self.message_user(request, "Report generation feature coming soon.")
    generate_report.short_description = "Generate Report"
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by and not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DealOptIn)
class DealOptInAdmin(admin.ModelAdmin):
    """Admin for deal opt-ins"""
    list_display = ['reference', 'user_email', 'deal_title', 'amount_display', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['reference', 'user__email', 'user__username', 'deal__title']
    readonly_fields = ['reference', 'created_at', 'updated_at', 'ip_address', 'user_agent']
    fieldsets = [
        ('Basic Information', {
            'fields': ['reference', 'user', 'deal']
        }),
        ('Financial', {
            'fields': ['amount', 'status', 'paid_at']
        }),
        ('Transaction', {
            'fields': ['transaction']
        }),
        ('Metadata', {
            'fields': ['ip_address', 'user_agent', 'created_at', 'updated_at'],
            'classes': ['collapse']
        }),
    ]
    actions = ['confirm_opt_ins', 'refund_opt_ins']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def deal_title(self, obj):
        return obj.deal.title
    deal_title.short_description = 'Deal'
    deal_title.admin_order_field = 'deal__title'
    
    def amount_display(self, obj):
        return format_html('Ksh {}', '{:,}'.format(obj.amount))
    amount_display.short_description = 'Amount'
    
    def confirm_opt_ins(self, request, queryset):
        from django.utils import timezone
        for opt_in in queryset.filter(status='pending'):
            opt_in.status = 'confirmed'
            opt_in.paid_at = timezone.now()
            opt_in.save()
        self.message_user(request, f"{queryset.count()} opt-ins confirmed.")
    confirm_opt_ins.short_description = "Confirm selected opt-ins"
    
    def refund_opt_ins(self, request, queryset):
        queryset.update(status='refunded')
        self.message_user(request, f"{queryset.count()} opt-ins marked as refunded.")
    refund_opt_ins.short_description = "Mark as refunded"


@admin.register(DealRevenue)
class DealRevenueAdmin(admin.ModelAdmin):
    """Admin for deal revenues"""
    list_display = ['deal', 'period', 'amount_display', 'description']
    list_filter = ['deal', 'period_start']
    search_fields = ['deal__title', 'description']
    
    def period(self, obj):
        return f"{obj.period_start} - {obj.period_end}"
    period.short_description = 'Period'
    
    def amount_display(self, obj):
        return format_html('Ksh {}', '{:,}'.format(obj.amount))
    amount_display.short_description = 'Amount'


@admin.register(DealCost)
class DealCostAdmin(admin.ModelAdmin):
    """Admin for deal costs"""
    list_display = ['deal', 'cost_type', 'period', 'amount_display', 'description']
    list_filter = ['deal', 'cost_type', 'period_start']
    search_fields = ['deal__title', 'description']
    
    def period(self, obj):
        return f"{obj.period_start} - {obj.period_end}"
    period.short_description = 'Period'
    
    def amount_display(self, obj):
        return format_html('Ksh {}', '{:,}'.format(obj.amount))
    amount_display.short_description = 'Amount'


@admin.register(DealProfitDistribution)
class DealProfitDistributionAdmin(admin.ModelAdmin):
    """Admin for profit distributions"""
    list_display = ['deal', 'period', 'net_profit_display', 'members_share_display', 'per_member_display', 'total_members']
    list_filter = ['deal', 'period_start']
    
    def period(self, obj):
        return f"{obj.period_start} - {obj.period_end}"
    period.short_description = 'Period'
    
    def net_profit_display(self, obj):
        return format_html('Ksh {}', '{:,}'.format(obj.net_profit))
    net_profit_display.short_description = 'Net Profit'
    
    def members_share_display(self, obj):
        return format_html('Ksh {}', '{:,}'.format(obj.members_share))
    members_share_display.short_description = 'Members Share'
    
    def per_member_display(self, obj):
        return format_html('Ksh {}', '{:,}'.format(obj.distribution_per_member))
    per_member_display.short_description = 'Per Member'
    
    fieldsets = [
        ('Deal Information', {
            'fields': ['deal', 'period_start', 'period_end']
        }),
        ('Financial Breakdown', {
            'fields': [
                'total_revenue', 'total_costs', 'net_profit',
                'management_fee', 'performance_carry', 'members_share'
            ]
        }),
        ('Distribution', {
            'fields': ['distribution_per_member', 'total_members', 'distributed_at']
        }),
    ]
    readonly_fields = ['distributed_at']


@admin.register(DealReport)
class DealReportAdmin(admin.ModelAdmin):
    """Admin for deal reports"""
    list_display = ['deal', 'title', 'period', 'net_profit_display', 'status_update', 'created_at']
    list_filter = ['deal', 'status_update', 'period']
    search_fields = ['deal__title', 'title', 'summary']
    
    def net_profit_display(self, obj):
        return format_html('Ksh {}', '{:,}'.format(obj.net_profit))
    net_profit_display.short_description = 'Net Profit'
    
    fieldsets = [
        ('Report Information', {
            'fields': ['deal', 'title', 'period', 'pdf_report']
        }),
        ('Financial Summary', {
            'fields': ['aml_share', 'net_profit']
        }),
        ('Report Content', {
            'fields': ['summary', 'revenue_details', 'cost_details']
        }),
        ('Status', {
            'fields': ['status_update', 'next_steps']
        }),
        ('Metadata', {
            'fields': ['created_at'],
            'classes': ['collapse']
        }),
    ]
    readonly_fields = ['created_at']


@admin.register(DealUpdate)
class DealUpdateAdmin(admin.ModelAdmin):
    """Admin for deal updates"""
    list_display = ['deal', 'title', 'is_important', 'created_at']
    list_filter = ['deal', 'is_important', 'created_at']
    search_fields = ['deal__title', 'title', 'content']
    
    fieldsets = [
        ('Update Information', {
            'fields': ['deal', 'title', 'content', 'is_important']
        }),
        ('Metadata', {
            'fields': ['created_at'],
            'classes': ['collapse']
        }),
    ]
    readonly_fields = ['created_at']