import json
import os
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import telegram
from . import zammad_api  # Import our zammad api helper

# Get the bot token from the .env file
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telegram.Bot(token=BOT_TOKEN)


@csrf_exempt  # Important: To allow POST requests from Telegram
def telegram_webhook(request):
    if request.method == "POST":
        update_data = json.loads(request.body.decode('utf-8'))
        update = telegram.Update.de_json(update_data, bot)

        # Check if the update is a command message (like /start)
        if update.message and update.message.text:
            handle_message(update.message)

        # Check if the update is a button press (Callback Query)
        elif update.callback_query:
            handle_callback_query(update.callback_query)

    return HttpResponse("ok")  # Acknowledge receipt of the update


def handle_message(message):
    """Handles regular text messages."""
    chat_id = message.chat.id
    text = message.text

    if text == '/start':
        # Create a button
        keyboard = [
            [telegram.InlineKeyboardButton("Create New Ticket", callback_data='create_ticket')]
        ]
        reply_markup = telegram.InlineKeyboardMarkup(keyboard)

        # Send the message with the button
        bot.send_message(
            chat_id=chat_id,
            text="Welcome! Click the button below to create a new support ticket in Zammad.",
            reply_markup=reply_markup
        )


def handle_callback_query(query):
    """Handles button presses."""
    chat_id = query.message.chat.id
    message_id = query.message.message_id
    user = query.from_user  # The user who clicked the button

    # Check which button was pressed
    if query.data == 'create_ticket':
        # 1. Give instant feedback to the user
        bot.answer_callback_query(callback_query_id=query.id, text="Creating ticket, please wait...")

        # 2. Create the ticket in Zammad
        ticket_title = f"New Ticket from {user.first_name}"
        ticket_body = f"A new ticket was requested by Telegram user: \n" \
                      f"Name: {user.first_name} {user.last_name or ''}\n" \
                      f"Username: @{user.username}\n" \
                      f"User ID: {user.id}"

        ticket = zammad_api.create_zammad_ticket(
            title=ticket_title,
            body=ticket_body,
            customer_telegram_id=user.id,
            customer_telegram_name=user.first_name
        )

        # 3. Edit the original message to show the result
        if ticket and ticket.get('number'):
            ticket_number = ticket.get('number')
            response_text = f"✅ Success! Your ticket has been created.\nTicket Number: **{ticket_number}**"
        else:
            response_text = "❌ Error! Could not create the ticket. Please contact an administrator."

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=response_text,
            parse_mode=telegram.ParseMode.MARKDOWN
        )