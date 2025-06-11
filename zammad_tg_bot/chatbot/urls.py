from django.urls import path
from . import views

urlpatterns = [
    # This URL will be something like: https://<ngrok_domain>/telegram/webhook/
    path('webhook/', views.telegram_webhook, name='telegram_webhook'),
]