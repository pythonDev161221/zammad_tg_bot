from django.contrib import admin
from .models import TelegramBot, ZammadGroup, Customer, OpenTicket, Question, QuestionTranslation


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


class QuestionTranslationInline(admin.TabularInline):
    model = QuestionTranslation
    extra = 3  # Show 3 empty forms (for ky, ru, en)
    max_num = 3  # Maximum 3 languages
    fields = ('language', 'text')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('order', 'get_question_preview', 'question_type', 'is_active', 'created_at')
    list_filter = ('question_type', 'is_active')
    readonly_fields = ('created_at',)
    ordering = ('order',)
    inlines = [QuestionTranslationInline]

    def get_question_preview(self, obj):
        """Show Kyrgyz translation as preview"""
        text = obj.get_text('ky')
        return text[:50] + "..." if len(text) > 50 else text
    get_question_preview.short_description = 'Question (Kyrgyz)'


@admin.register(QuestionTranslation)
class QuestionTranslationAdmin(admin.ModelAdmin):
    list_display = ('question', 'language', 'get_text_preview')
    list_filter = ('language', 'question')
    search_fields = ('text', 'question__order')
    ordering = ('question__order', 'language')

    def get_text_preview(self, obj):
        """Show truncated text preview"""
        return obj.text[:100] + "..." if len(obj.text) > 100 else obj.text
    get_text_preview.short_description = 'Text Preview'


@admin.register(OpenTicket)
class OpenTicketAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'bot', 'customer', 'zammad_ticket_number', 'priority', 'created_at')
    list_filter = ('bot', 'priority', 'created_at')
    search_fields = ('telegram_id', 'zammad_ticket_number')
    readonly_fields = ('created_at',)
