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

        elif update.callback_query:
            handle_callback_query(update.callback_query)

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

            # --- ADD THE CANCEL BUTTON ---
            keyboard = [[
                telegram.InlineKeyboardButton(
                    "Cancel This Ticket ❌",
                    callback_data=f"cancel_ticket_{open_ticket.zammad_ticket_id}"
                )
            ]]
            reply_markup = telegram.InlineKeyboardMarkup(keyboard)

            # 2. If found, use the information we already have.
            response_text = (
                f"You have an open ticket: **#{open_ticket.zammad_ticket_number}**.\n\n"
                f"An agent will attend to it as soon as possible. "
                f"You can cancel it by clicking the button below."
            )

            bot.send_message(
                chat_id=chat_id,
                text=response_text,
                parse_mode=telegram.ParseMode.MARKDOWN,
                reply_markup=reply_markup  # Attach the button
            )




        except ObjectDoesNotExist:

            # 3. If no ticket is found in our database, inform the user.

            response_text = "You do not have any open tickets. Use /start to create one."

            bot.send_message(chat_id=chat_id, text=response_text)

        # bot.send_message(chat_id=chat_id, text=response_text, parse_mode=telegram.ParseMode.MARKDOWN)
    # The 'elif' is at the same level as 'if'
    # elif message.contact:
    #     # Everything inside the 'elif' is indented once
    #     try:
    #         existing_ticket = OpenTicket.objects.get(telegram_id=user.id)
    #         bot.send_message(
    #             chat_id=chat_id,
    #             text=f"❌ You already have an open ticket: #{existing_ticket.zammad_ticket_number}. Please wait for an agent to respond."
    #         )
    #         return
    #     except ObjectDoesNotExist:
    #         pass
        # --- REPLACE THE OLD try...except BLOCK WITH THIS NEW ONE ---
    elif message.contact:
        # Everything inside the 'elif' is indented once
        try:
            # 1. Check our local DB first
            ticket_in_db = OpenTicket.objects.get(telegram_id=user.id)

            # 2. If found, ask Zammad for the real status
            print(
                f"User has a tracked ticket. Checking real status of Zammad ticket ID {ticket_in_db.zammad_ticket_id}...")
            ticket_details = zammad_api.get_ticket_details(ticket_in_db.zammad_ticket_id)

            if ticket_details:
                # state_obj = ticket_details.get('state', {})
                # current_state = state_obj.get('name', 'unknown')
                current_state = ticket_details.get('state', 'unknown')

                # List of states we consider "open"
                open_states = ['new', 'open', 'pending reminder', 'pending close']

                if current_state.lower() in open_states:
                    # The ticket is genuinely still open, so we stop the user
                    bot.send_message(
                        chat_id=chat_id,
                        text=f"❌ You already have an open ticket: #{ticket_in_db.zammad_ticket_number}. Please wait for it to be resolved."
                    )
                    return  # <-- IMPORTANT: Stop here
                # else:
                #     # The ticket is closed in Zammad! Our DB is out of date.
                #     print(
                #         f"Ticket #{ticket_in_db.zammad_ticket_number} is '{current_state}' in Zammad. Cleaning up local DB.")
                #     ticket_in_db.delete()
                #     # Let the code continue to create a new ticket...
                    # --- REPLACE IT WITH THIS ---
                else:
                    # The ticket is closed in Zammad! Our DB is out of date.
                    print(
                        f"Ticket #{ticket_in_db.zammad_ticket_number} is '{current_state}' in Zammad. Cleaning up local DB.")
                    ticket_in_db.delete()
                    # Inform the user and STOP.
                    bot.send_message(
                        chat_id=chat_id,
                        text="It looks like your previous ticket was recently closed. Please share your contact again to create a new one."
                    )
                    return  # <-- THE CRITICAL MISSING PIECE
            else:
                # We couldn't get details from Zammad, it's safer to stop
                bot.send_message(chat_id=chat_id,
                                 text="Could not verify status of previous ticket. Please try again in a moment.")
                return  # <-- IMPORTANT: Stop here

        except ObjectDoesNotExist:
            # User has no open ticket in our DB. We can proceed.
            pass

        # --- THE REST OF YOUR elif message.contact: BLOCK STAYS EXACTLY THE SAME ---
        phone_number = message.contact.phone_number
        # ... and so on ...

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


# --- ADD THIS ENTIRE NEW FUNCTION ---
def handle_callback_query(query):
    """Handles all button presses."""
    user = query.from_user
    chat_id = query.message.chat.id
    message_id = query.message.message_id

    # Check if the button pressed is our cancel button
    if query.data.startswith('cancel_ticket_'):
        # Give instant feedback to the user
        bot.answer_callback_query(callback_query_id=query.id, text="Processing your cancellation...")

        # Get the ticket ID from the button's data
        ticket_id = int(query.data.split('_')[-1])

        # 1. Tell Zammad to close the ticket
        success = zammad_api.close_zammad_ticket(ticket_id, user.first_name)

        if success:
            # 2. If Zammad confirmed, delete the ticket from our local database
            OpenTicket.objects.filter(zammad_ticket_id=ticket_id).delete()
            response_text = "✅ Your ticket has been successfully canceled."
        else:
            response_text = "❌ There was an error canceling your ticket in Zammad. Please contact an administrator."

        # 3. Edit the original message to show the final result
        bot.edit_message_text(text=response_text, chat_id=chat_id, message_id=message_id)
