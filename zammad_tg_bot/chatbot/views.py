import json
import os
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import telegram
from . import zammad_api

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telegram.Bot(token=BOT_TOKEN)


@csrf_exempt
def telegram_webhook(request):
    if request.method == "POST":
        update_data = json.loads(request.body.decode('utf-8'))
        update = telegram.Update.de_json(update_data, bot)

        # We now only need to handle messages, not callback queries
        if update.message:
            handle_message(update.message)

    return HttpResponse("ok")


def handle_message(message):
    """Handles all incoming messages."""
    chat_id = message.chat.id
    user = message.from_user

    # --- Scenario 1: User sends the /start command ---
    if message.text == '/start':
        # This button replaces the keyboard and asks for the phone number
        keyboard = [
            [telegram.KeyboardButton("Create Ticket (Share Phone Number)", request_contact=True)]
        ]
        # This makes the keyboard appear and then disappear after one use
        reply_markup = telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

        bot.send_message(
            chat_id=chat_id,
            text="Welcome! To create a ticket, please share your contact information by clicking the button below.",
            reply_markup=reply_markup
        )

    # --- Scenario 2: User shares their contact information ---
    elif message.contact:
        phone_number = message.contact.phone_number
        bot.send_message(chat_id=chat_id,
                         text=f"Thank you! Creating a ticket with your phone number: {phone_number}. Please wait...")

        # Create the ticket in Zammad, now with the phone number
        ticket_title = f"New Ticket from {user.first_name}"
        ticket_body = (
            f"A new ticket was requested by Telegram user: \n"
            f"Name: {user.first_name} {user.last_name or ''}\n"
            f"Username: @{user.username}\n"
            f"User ID: {user.id}\n"
            f"Phone: {phone_number}"
        )

        ticket = zammad_api.create_zammad_ticket(
            title=ticket_title,
            body=ticket_body,
            customer_telegram_id=user.id,
            customer_telegram_name=user.first_name,
            phone_number=phone_number  # Pass the phone number here!
        )


        if ticket and ticket.get('number'):
            ticket_number = ticket.get('number')
            response_text = f"✅ Success! Your ticket has been created.\nTicket Number: **{ticket_number}**"
        else:
            response_text = "❌ Error! Could not create the ticket. Please contact an administrator."

        bot.send_message(
            chat_id=chat_id,
            text=response_text,
            parse_mode=telegram.ParseMode.MARKDOWN
        )
        # --- ADD THIS NEW BLOCK ---
    else:
        # If the message is not /start, send a help message
        bot.send_message(
            chat_id=chat_id,
            text="I'm sorry, I don't understand that command. Please use /start to create a new ticket."
        )