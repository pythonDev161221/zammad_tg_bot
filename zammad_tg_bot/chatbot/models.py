from django.db import models


class OpenTicket(models.Model):
    """
    A simple model to track which Telegram user has an open ticket.
    """
    # The user's unique Telegram ID. This is our primary key.
    telegram_id = models.BigIntegerField(primary_key=True, unique=True)

    # The internal ID of the ticket in Zammad's database.
    zammad_ticket_id = models.IntegerField(unique=True)

    # The user-facing ticket number (e.g., "46071").
    zammad_ticket_number = models.CharField(max_length=50)

    # Automatically records when this entry was created.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"User {self.telegram_id} - Ticket #{self.zammad_ticket_number}"