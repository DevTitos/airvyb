from django.contrib import admin
from .models import PushSubscription, Notification

@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "endpoint_truncated", "created_at", "active")
    list_filter = ("active",)
    search_fields = ("user__email", "endpoint")

    def endpoint_truncated(self, obj):
        return obj.endpoint[:50] + "..."
    endpoint_truncated.short_description = "Endpoint"

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at", "sent", "send_to_all")
    actions = ["send_selected_notifications"]

    def send_selected_notifications(self, request, queryset):
        for notification in queryset:
            if not notification.sent:
                notification.send()
        self.message_user(request, "Selected notifications sent successfully!")
    send_selected_notifications.short_description = "Send selected notifications"