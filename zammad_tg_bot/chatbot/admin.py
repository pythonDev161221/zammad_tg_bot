from django.contrib import admin
from .models import TelegramBot, ZammadGroup, Customer, OpenTicket


@admin.register(TelegramBot)
class TelegramBotAdmin(admin.ModelAdmin):
    list_display = ('name', 'token')
    search_fields = ('name', 'token')
    readonly_fields = ('token',)


@admin.register(ZammadGroup)
class ZammadGroupAdmin(admin.ModelAdmin):
    list_display = ('telegram_bot', 'zammad_group', 'customer_last_name', 'customer_prefix')
    list_filter = ('zammad_group', 'customer_prefix')
    search_fields = ('telegram_bot__name', 'zammad_group', 'customer_last_name')


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'telegram_bot')
    list_filter = ('telegram_bot',)
    search_fields = ('first_name',)


@admin.register(OpenTicket)
class OpenTicketAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'bot', 'customer', 'zammad_ticket_number', 'created_at')
    list_filter = ('bot', 'created_at')
    search_fields = ('telegram_id', 'zammad_ticket_number')
    readonly_fields = ('created_at',)
