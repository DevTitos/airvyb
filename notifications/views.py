from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from .models import PushSubscription

@csrf_exempt
def subscribe(request):
    if request.method == "POST" and request.user.is_authenticated:
        data = json.loads(request.body)
        PushSubscription.objects.update_or_create(
            user=request.user,
            endpoint=data["endpoint"],
            defaults={"keys": data.get("keys", {})}
        )
        return JsonResponse({"status": "ok"})
    return JsonResponse({"status": "error"}, status=400)