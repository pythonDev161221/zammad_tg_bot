import json
import os
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import telegram
from . import zammad_api
from .models import OpenTicket  # <-- Add this import at the top
from django.core.exceptions import ObjectDoesNotExist

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telegram.Bot(token=BOT_TOKEN)


@csrf_exempt
def telegram_webhook(request):
    if request.method == "POST":
        update_data = json.loads(request.body.decode('utf-8'))
        update = telegram.Update.de_json(update_data, bot)
        if update.message:
            handle_message(update.message)
    return HttpResponse("ok")


def handle_message(message):
    chat_id = message.chat.id
    user = message.from_user

    # The 'if' block starts here
    if message.text == '/start':
        # Everything inside the 'if' is indented once
        keyboard = [[telegram.KeyboardButton("Create Ticket (Share Phone Number)", request_contact=True)]]
        reply_markup = telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        bot.send_message(
            chat_id=chat_id,
            text="Welcome! To create a ticket, please share your contact information by clicking the button below.",
            reply_markup=reply_markup
        )


    elif message.text == '/status':

        try:

            # 1. Check our local database ONLY. No API call.

            open_ticket = OpenTicket.objects.get(telegram_id=user.id)

            # 2. If found, use the information we already have.

            response_text = (

                f"You have an open ticket: **#{open_ticket.zammad_ticket_number}**.\n\n"

                f"An agent will attend to it as soon as possible. "

                f"You will be able to create a new ticket once this one is closed."

            )


        except ObjectDoesNotExist:

            # 3. If no ticket is found in our database, inform the user.

            response_text = "You do not have any open tickets. Use /start to create one."

        bot.send_message(chat_id=chat_id, text=response_text, parse_mode=telegram.ParseMode.MARKDOWN)
    # The 'elif' is at the same level as 'if'
    elif message.contact:
        # Everything inside the 'elif' is indented once
        try:
            existing_ticket = OpenTicket.objects.get(telegram_id=user.id)
            bot.send_message(
                chat_id=chat_id,
                text=f"❌ You already have an open ticket: #{existing_ticket.zammad_ticket_number}. Please wait for an agent to respond."
            )
            return
        except ObjectDoesNotExist:
            pass

        phone_number = message.contact.phone_number
        bot.send_message(chat_id=chat_id, text=f"Thank you! Creating your ticket. Please wait...")

        ticket_title = f"New Ticket from Telegram User: {user.first_name}"
        ticket_body = (
            f"A new ticket was requested by Telegram user:\n\n"
            f"**Name:** {user.first_name} {user.last_name or ''}\n"
            f"**Username:** @{user.username}\n"
            f"**Telegram User ID:** {user.id}\n"
            f"**Phone Number:** {phone_number}"
        )

        ticket_data = zammad_api.create_zammad_ticket(
            title=ticket_title,
            body=ticket_body
        )

        if ticket_data and ticket_data.get('id'):
            OpenTicket.objects.create(
                telegram_id=user.id,
                zammad_ticket_id=ticket_data.get('id'),
                zammad_ticket_number=ticket_data.get('number')
            )
            response_text = f"✅ Success! Your ticket has been created.\nTicket Number: **{ticket_data.get('number')}**"
        else:
            response_text = "❌ Error! Could not create the ticket. Please check the server logs."

        bot.send_message(chat_id=chat_id, text=response_text, parse_mode=telegram.ParseMode.MARKDOWN)

    # The 'else' is at the same level as 'if' and 'elif'
    else:
        # Everything inside the 'else' is indented once
        bot.send_message(
            chat_id=chat_id,
            text="I'm sorry, I don't understand. Please use the /start command to begin."
        )



@csrf_exempt
def zammad_webhook(request):
    if request.method == "POST":
        try:
            payload = json.loads(request.body)
            ticket_info = payload.get('ticket', {})
            ticket_id = ticket_info.get('id')
            ticket_state = ticket_info.get('state')

            print(f"Received Zammad webhook for ticket {ticket_id}, new state is {ticket_state}")

            # Check if the ticket's new state is 'closed'
            if ticket_id and ticket_state == 'closed':
                # Find the ticket in our local DB and delete it
                try:
                    ticket_to_close = OpenTicket.objects.get(zammad_ticket_id=ticket_id)
                    print(f"Closing tracked ticket for user {ticket_to_close.telegram_id}")
                    ticket_to_close.delete()
                except ObjectDoesNotExist:
                    print(f"Received close event for untracked ticket {ticket_id}")

        except Exception as e:
            print(f"Error processing Zammad webhook: {e}")

    return HttpResponse("ok")
