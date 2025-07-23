from django.db import models


class TelegramBot(models.Model):
    """Stores Telegram bot configuration"""
    name = models.CharField(max_length=100, unique=True)
    token = models.CharField(max_length=200, unique=True)
    
    def __str__(self):
        return f"Bot: {self.name}"


class ZammadGroup(models.Model):
    """Stores Zammad group configuration"""
    telegram_bot = models.OneToOneField(TelegramBot, on_delete=models.CASCADE, related_name='zammad_config')
    zammad_group = models.CharField(max_length=100, unique=True, null=True, blank=True)
    customer_last_name = models.CharField(max_length=100, blank=True, null=True)
    customer_prefix = models.CharField(max_length=64, default="AZS")
    
    def __str__(self):
        return f"Zammad Config for {self.telegram_bot.name}"


class Customer(models.Model):
    """Stores customer information"""
    first_name = models.IntegerField()
    telegram_bot = models.ForeignKey(TelegramBot, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ['first_name', 'telegram_bot']
    
    def __str__(self):
        return f"{self.first_name} ({self.telegram_bot.name})"


class OpenTicket(models.Model):
    """Enhanced to support multiple bots"""
    telegram_id = models.BigIntegerField()
    bot = models.ForeignKey(TelegramBot, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, default=1)
    zammad_ticket_id = models.IntegerField()
    zammad_ticket_number = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['telegram_id', 'bot']
    
    def __str__(self):
        return f"{self.bot.name}: {self.telegram_id} - Ticket #{self.zammad_ticket_number}"