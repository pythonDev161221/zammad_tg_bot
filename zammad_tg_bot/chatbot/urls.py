from django.urls import path
from . import views

urlpatterns = [
    # Bot-specific webhook URL: https://<ngrok_domain>/telegram/webhook/<bot_token>/
    path('webhook/<str:bot_token>/', views.telegram_webhook, name='telegram_webhook'),
    path('webhook/zammad/', views.zammad_webhook, name='zammad_webhook'),
]