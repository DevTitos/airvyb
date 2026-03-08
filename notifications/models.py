from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from webpush import send_user_notification
import json

User = get_user_model()

class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.TextField()
    keys = models.JSONField()  # {"p256dh": "...", "auth": "..."}
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email} - {self.endpoint[:40]}..."

class Notification(models.Model):
    title = models.CharField(max_length=100)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)
    send_to_all = models.BooleanField(default=True)  # True = all users, False = manual

    def send(self):
        """Send notification to all users with active subscriptions."""
        subscriptions = PushSubscription.objects.filter(active=True)
        payload = json.dumps({
            "title": self.title,
            "body": self.body
        })
        for sub in subscriptions:
            try:
                send_user_notification(user=sub.user, payload={"title": self.title, "body": self.body}, ttl=1000)
            except Exception as e:
                print(f"Failed to send to {sub.user.email}: {e}")
        self.sent = True
        self.save()

    def __str__(self):
        return f"{self.title} ({'Sent' if self.sent else 'Pending'})"