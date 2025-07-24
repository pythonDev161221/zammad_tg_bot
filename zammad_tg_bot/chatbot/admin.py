from django.contrib import admin
from .models import TelegramBot, ZammadGroup, Customer, OpenTicket, Question


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


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('order', 'question_text', 'question_type', 'is_active', 'created_at')
    list_filter = ('question_type', 'is_active')
    search_fields = ('question_text',)
    readonly_fields = ('created_at',)
    ordering = ('order',)


@admin.register(OpenTicket)
class OpenTicketAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'bot', 'customer', 'zammad_ticket_number', 'priority', 'created_at')
    list_filter = ('bot', 'priority', 'created_at')
    search_fields = ('telegram_id', 'zammad_ticket_number')
    readonly_fields = ('created_at',)
