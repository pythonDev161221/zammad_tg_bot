from django.core.management.base import BaseCommand
from django.conf import settings
from chatbot.models import TelegramBot


class Command(BaseCommand):
    help = 'Setup Telegram bots from environment variables'

    def handle(self, *args, **options):
        """Create or update bot records from settings"""
        tokens = settings.TELEGRAM_BOT_TOKENS
        
        for bot_name, token in tokens.items():
            if not token:
                self.stdout.write(
                    self.style.WARNING(f'No token found for {bot_name}')
                )
                continue
            
            bot, created = TelegramBot.objects.get_or_create(
                token=token,
                defaults={'name': bot_name}
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created bot: {bot_name} ({token[:10]}...)')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Bot already exists: {bot_name} ({token[:10]}...)')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Bot setup completed!')
        )