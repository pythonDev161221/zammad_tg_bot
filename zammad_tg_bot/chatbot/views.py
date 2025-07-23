import json
import os
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import gettext as _
import telegram
from . import zammad_api
from .models import OpenTicket, TelegramBot, Customer
from django.core.exceptions import ObjectDoesNotExist
import json


# Bot management
def get_bot_by_token(token):
    """Get or create a bot instance by token"""
    try:
        return TelegramBot.objects.get(token=token)
    except ObjectDoesNotExist:
        return None

def get_telegram_bot_instance(token):
    """Get telegram.Bot instance for a token"""
    return telegram.Bot(token=token)


@csrf_exempt
def telegram_webhook(request, bot_token):
    """Secure webhook handler that validates bot token"""
    if request.method != "POST":
        return HttpResponseBadRequest("Only POST requests allowed")
    
    try:
        # Validate the bot token exists in our database
        bot_record = get_bot_by_token(bot_token)
        if not bot_record:
            return HttpResponseBadRequest("Invalid bot token")
        
        # Create bot instance for this specific token
        bot = get_telegram_bot_instance(bot_token)
        
        # Process the webhook
        update_data = json.loads(request.body.decode('utf-8'))
        update = telegram.Update.de_json(update_data, bot)
        
        if update.message:
            handle_message(update.message, bot, bot_record)
        elif update.callback_query:
            handle_callback_query(update.callback_query, bot, bot_record)
            
    except Exception as e:
        print(f"Error processing webhook for bot {bot_token}: {e}")
        return HttpResponseBadRequest("Error processing webhook")

    return HttpResponse("ok")


# --- Constants (Good Practice) ---
# Define Zammad open states in one place for easy maintenance.
ZAMMAD_OPEN_STATES = ['new', 'open', 'pending reminder', 'pending close']


# --- Helper Functions (Each does one specific job) ---
def _closed_with_agent(message, user, bot_record):
    try:
        ticket_in_db = OpenTicket.objects.get(telegram_id=user.id, bot=bot_record)
        ticket_details = zammad_api.get_ticket_details(ticket_in_db.zammad_ticket_id)

        if ticket_details and ticket_details.get('state', 'unknown').lower() in ZAMMAD_OPEN_STATES:
            return
        else:
            # The ticket is closed or invalid in Zammad, so clean up our local DB.
            print(f"Stale ticket #{ticket_in_db.zammad_ticket_number} found. Cleaning up local DB.")
            ticket_in_db.delete()
    except ObjectDoesNotExist:
        # No ticket in our DB, we can proceed.
        pass

def _handle_open_ticket_update(bot, message, user, bot_record):
    _closed_with_agent(message, user, bot_record)
    """
    Checks if the user has an open ticket. If so, handles their message
    as an update (note or photo) to that ticket.

    Returns:
        bool: True if the message was handled, False otherwise.
    """
    try:
        open_ticket = OpenTicket.objects.get(telegram_id=user.id, bot=bot_record)

        # Determine if this message is an update (text or photo)
        is_text_update = message.text and not message.text.startswith('/')
        is_photo_update = bool(message.photo)

        if not (is_text_update or is_photo_update):
            # It's a command or something else, let the main handler deal with it.
            return False

        # --- Handle the update ---
        success = False
        if is_text_update:
            bot.send_message(chat_id=message.chat.id, text=_("Adding your note to the ticket..."))
            success = zammad_api.add_note_to_ticket(
                open_ticket.zammad_ticket_id, user.first_name, message.text
            )
        elif is_photo_update:
            bot.send_message(chat_id=message.chat.id, text=_("Uploading your photo..."))
            photo_file_id = message.photo[-1].file_id
            file = bot.get_file(photo_file_id)
            file_content = file.download_as_bytearray()
            # Include photo caption if present
            photo_caption = message.caption if message.caption else "Photo attachment"
            success = zammad_api.add_attachment_to_ticket(
                open_ticket.zammad_ticket_id, user.first_name, file_content, f"photo_{photo_file_id}.jpg", photo_caption
            )

        if success:
            bot.send_message(chat_id=message.chat.id, text=_("✅ Successfully updated your ticket."))
        else:
            # Let the user know if the update failed.
            bot.send_message(chat_id=message.chat.id, text=_("❌ Sorry, there was an error updating your ticket."))

        return True  # Crucially, we signal that the message was handled.

    except ObjectDoesNotExist:
        # User does not have an open ticket, so this handler has nothing to do.
        return False


def _handle_start_command(bot, message):
    """Handles the /start command, showing a welcome message and keyboard."""
    keyboard = [
        [telegram.KeyboardButton(_("Create New Ticket 📝"), request_contact=True)],
        [telegram.KeyboardButton("/status")]
    ]
    reply_markup = telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    bot.send_message(
        chat_id=message.chat.id,
        text=_("Welcome! To create a ticket, please share your contact information by clicking the button below."),
        reply_markup=reply_markup
    )


def _handle_status_command(bot, message, user, bot_record):
    """Handles the /status command, showing the user's open ticket or lack thereof."""
    try:
        open_ticket = OpenTicket.objects.get(telegram_id=user.id, bot=bot_record)
        response_text = _(
            "You have an open ticket: **#{ticket_number}**.\n\n"
            "An agent will attend to it as soon as possible. You can add notes or photos "
            "by sending them directly to this chat."
        ).format(ticket_number=open_ticket.zammad_ticket_number)
        bot.send_message(
            chat_id=message.chat.id,
            text=response_text,
            parse_mode=telegram.ParseMode.MARKDOWN
        )
    except ObjectDoesNotExist:
        response_text = _("You do not have any open tickets. Use /start to create one.")
        bot.send_message(chat_id=message.chat.id, text=response_text)




def _handle_contact_message(bot, message, user, bot_record):
    """Handles a shared contact to create a new Zammad ticket."""
    chat_id = message.chat.id
    # 1. Prevent creating a new ticket if one is already open
    try:
        ticket_in_db = OpenTicket.objects.get(telegram_id=user.id, bot=bot_record)
        ticket_details = zammad_api.get_ticket_details(ticket_in_db.zammad_ticket_id)

        if ticket_details and ticket_details.get('state', 'unknown').lower() in ZAMMAD_OPEN_STATES:
            bot.send_message(
                chat_id=chat_id,
                text=_("❌ You already have an open ticket: #{ticket_number}. Please wait for it to be resolved.").format(ticket_number=ticket_in_db.zammad_ticket_number)
            )
            return
        else:
            # The ticket is closed or invalid in Zammad, so clean up our local DB.
            print(f"Stale ticket #{ticket_in_db.zammad_ticket_number} found. Cleaning up local DB.")
            ticket_in_db.delete()
    except ObjectDoesNotExist:
        # No ticket in our DB, we can proceed.
        pass

    # 2. Show customer selection
    phone_number = message.contact.phone_number
    show_customer_selection(bot, chat_id, user, bot_record, phone_number)


def show_customer_selection(bot, chat_id, user, bot_record, phone_number):
    """Ask user to enter customer number for ticket creation"""
    # Get all customers for this bot to check if any exist
    customers = Customer.objects.filter(telegram_bot=bot_record)
    
    if not customers.exists():
        # No customers available, show error
        bot.send_message(
            chat_id=chat_id,
            text=_("❌ No customers available. Please contact an administrator to add customers first.")
        )
        return
    
    # Store phone number in user session (we'll use a simple approach with user state)
    # Store pending ticket creation state
    from django.core.cache import cache
    cache_key = f"pending_ticket_{user.id}_{bot_record.id}"
    cache.set(cache_key, {
        'phone_number': phone_number,
        'chat_id': chat_id,
        'user_id': user.id
    }, timeout=300)  # 5 minutes timeout
    
    # Show available customer numbers for reference
    customer_numbers = [str(c.first_name) for c in customers]
    customer_list = ", ".join(customer_numbers)
    
    bot.send_message(
        chat_id=chat_id,
        text=_("Please enter the customer number:\n\nAvailable customers: {customer_list}").format(customer_list=customer_list)
    )


# Customer selection callback is no longer used since we switched to text input
# def handle_customer_selection_callback(callback_query, bot, bot_record):
#     """Handle customer selection callback and create ticket"""
#     # This function is deprecated - we now use text input for customer numbers


def _handle_customer_number_input(bot, message, user, bot_record):
    """Handle customer number input for pending ticket creation"""
    if not message.text or message.text.startswith('/'):
        return False
    
    from django.core.cache import cache
    cache_key = f"pending_ticket_{user.id}_{bot_record.id}"
    pending_data = cache.get(cache_key)
    
    if not pending_data:
        return False  # No pending ticket creation
    
    try:
        # Try to convert input to integer (customer number)
        customer_number = int(message.text.strip())
        
        # Find customer with this number for this bot
        customer = Customer.objects.get(first_name=customer_number, telegram_bot=bot_record)
        
        # Clear the pending state
        cache.delete(cache_key)
        
        # Create ticket with found customer
        create_ticket_with_customer(
            bot, 
            message.chat.id, 
            user, 
            bot_record, 
            customer, 
            pending_data['phone_number']
        )
        
        return True
        
    except ValueError:
        # Invalid number format
        bot.send_message(
            chat_id=message.chat.id,
            text=_("❌ Please enter a valid customer number (digits only).")
        )
        return True
        
    except Customer.DoesNotExist:
        # Customer not found
        customers = Customer.objects.filter(telegram_bot=bot_record)
        customer_numbers = [str(c.first_name) for c in customers]
        customer_list = ", ".join(customer_numbers)
        
        bot.send_message(
            chat_id=message.chat.id,
            text=_("❌ Customer number {customer_number} not found.\n\nAvailable customers: {customer_list}").format(
                customer_number=customer_number,
                customer_list=customer_list
            )
        )
        return True
        
    except Exception as e:
        # General error
        bot.send_message(
            chat_id=message.chat.id,
            text=_("❌ Error finding customer. Please try again.")
        )
        print(f"Error handling customer number input: {e}")
        return True


def create_ticket_with_customer(bot, chat_id, user, bot_record, customer, phone_number):
    """Create ticket with the selected customer"""
    bot.send_message(chat_id=chat_id, text=_("Thank you! Creating your ticket. Please wait..."))

    ticket_title = _("New Ticket from Telegram User: {user_name}").format(user_name=user.first_name)
    ticket_body = _(
        "A new ticket was requested by Telegram user:\n\n"
        "**Name:** {full_name}\n"
        "**Username:** @{username}\n"
        "**Telegram User ID:** {user_id}\n"
        "**Phone Number:** {phone_number}\n"
        "**Selected Customer:** {customer_name}"
    ).format(
        full_name=f"{user.first_name} {user.last_name or ''}",
        username=user.username,
        user_id=user.id,
        phone_number=phone_number,
        customer_name=f"{getattr(bot_record.zammad_config, 'customer_prefix', 'AZS')}{str(customer.first_name)} {getattr(bot_record.zammad_config, 'customer_last_name', '') or ''}"
    )

    # Use bot's zammad_group or default to "Users" 
    group_name = getattr(bot_record.zammad_config, 'zammad_group', None) or "Users"
    ticket_data = zammad_api.create_zammad_ticket(
        title=ticket_title, 
        body=ticket_body, 
        group=group_name,
        customer_first_name=f"{getattr(bot_record.zammad_config, 'customer_prefix', 'AZS')}{str(customer.first_name)}",
        customer_last_name=getattr(bot_record.zammad_config, 'customer_last_name', None)
    )

    if ticket_data and ticket_data.get('id'):
        OpenTicket.objects.create(
            telegram_id=user.id,
            bot=bot_record,
            customer=customer,
            zammad_ticket_id=ticket_data.get('id'),
            zammad_ticket_number=ticket_data.get('number')
        )
        response_text = _("✅ Success! Your ticket has been created.\nTicket Number: **{ticket_number}**\nCustomer: **{customer_name}**").format(
            ticket_number=ticket_data.get('number'),
            customer_name=f"{getattr(bot_record.zammad_config, 'customer_prefix', 'AZS')}{str(customer.first_name)} {getattr(bot_record.zammad_config, 'customer_last_name', '') or ''}"
        )
    else:
        response_text = _("❌ Error! Could not create the ticket. Please check the server logs.")

    bot.send_message(chat_id=chat_id, text=response_text, parse_mode=telegram.ParseMode.MARKDOWN)


# --- Main Dispatcher Function ---

def handle_message(message, bot, bot_record):
    """
    The main message handler. It acts as a dispatcher, routing the message
    to the appropriate helper function based on its content.
    """
    user = message.from_user
    # PRIORITY 1: Check if this is an update to an existing ticket.
    # The helper returns True if it handled the message, so we can stop.
    if _handle_open_ticket_update(bot, message, user, bot_record):
        return

    # PRIORITY 2: Check if user is entering customer number for pending ticket
    if _handle_customer_number_input(bot, message, user, bot_record):
        return

    # PRIORITY 3: Handle specific commands and message types.
    if message.text:
        if message.text == '/start':
            _handle_start_command(bot, message)
        elif message.text == '/status':
            _handle_status_command(bot, message, user, bot_record)
        else:
            # This is text that isn't a command and the user has no open ticket.
            bot.send_message(
                chat_id=message.chat.id,
                text=_("I'm sorry, I don't understand. Please use /start to create a ticket.")
            )
    elif message.contact:
        _handle_contact_message(bot, message, user, bot_record)
    else:
        # This catches anything else (photos, stickers, etc.) when the user
        # does NOT have an open ticket.
        print("message_have_not_contact")
        bot.send_message(
            chat_id=message.chat.id,
            text=_("I'm sorry, I don't understand. Please use /start to create a ticket.")
        )


class WebhookHandler:
    """Handles Zammad webhook processing and payload parsing"""
    
    def __init__(self):
        self.agent_handler = AgentResponseHandler()
    
    def parse_payload(self, request):
        """Parse and normalize webhook payload from different formats"""
        if request.content_type == 'application/json':
            payload = json.loads(request.body)
        else:
            # Handle form-encoded data from Zammad triggers
            payload = dict(request.POST)
            # Convert lists to single values
            payload = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in payload.items()}
        
        return payload
    
    def extract_ticket_and_article_info(self, payload):
        """Extract ticket and article information from webhook payload"""
        if 'ticket' in payload and 'article' in payload:
            # Full webhook payload format
            ticket_info = payload.get('ticket', {})
            article_info = payload.get('article', {})
            ticket_id = ticket_info.get('id')
            ticket_state = ticket_info.get('state')
        else:
            # Simplified trigger format - extract from flat structure
            ticket_id = payload.get('ticket_id') or payload.get('id')
            ticket_state = payload.get('ticket_state') or payload.get('state')
            article_info = {
                'id': payload.get('article_id') or payload.get('id'),
                'type': payload.get('article_type') or payload.get('type'),
                'sender': payload.get('article_sender') or payload.get('sender'),
                'internal': payload.get('article_internal') or payload.get('internal'),
                'body': payload.get('article_body') or payload.get('body', ''),
                'subject': payload.get('article_subject') or payload.get('subject', '')
            }
            ticket_info = {'id': ticket_id, 'state': ticket_state}
        
        return ticket_info, article_info
    
    def process_agent_article(self, ticket_id, article_info):
        """Process new article from agent if it meets criteria"""
        if not (article_info and article_info.get('body')):
            return
        
        article_type = article_info.get('type')
        article_sender = article_info.get('sender')
        article_internal = str(article_info.get('internal', '')).lower() in ['true', '1', 'yes']
        
        if article_type in ['web', 'email', 'phone', 'note'] and article_sender != 'Customer' and not article_internal:
            self.agent_handler.handle_agent_response(ticket_id, article_info)
    
    def process_ticket_closure(self, ticket_id, ticket_state):
        """Handle ticket closure notification"""
        if not (ticket_id and ticket_state == 'closed'):
            return
        
        try:
            ticket_to_close = OpenTicket.objects.get(zammad_ticket_id=ticket_id)
            # Get the bot instance for this ticket
            bot = get_telegram_bot_instance(ticket_to_close.bot.token)
            bot.send_message(
                chat_id=ticket_to_close.telegram_id,
                text=_("✅ Your ticket has been resolved and closed by our support team.")
            )
            ticket_to_close.delete()
        except ObjectDoesNotExist:
            pass


@csrf_exempt
def zammad_webhook(request):
    """Main webhook handler for Zammad notifications"""
    if request.method != "POST":
        return HttpResponse("ok")
    
    try:
        webhook_handler = WebhookHandler()
        
        payload = webhook_handler.parse_payload(request)
        ticket_info, article_info = webhook_handler.extract_ticket_and_article_info(payload)
        
        ticket_id = ticket_info.get('id')
        ticket_state = ticket_info.get('state')
        
        webhook_handler.process_agent_article(ticket_id, article_info)
        webhook_handler.process_ticket_closure(ticket_id, ticket_state)
        
    except Exception as e:
        print(f"Error processing Zammad webhook: {e}")
    
    return HttpResponse("ok")



class TelegramMessageHandler:
    """Handles sending messages and attachments to Telegram"""
    
    def __init__(self, bot_token):
        self.bot = get_telegram_bot_instance(bot_token)
    
    def clean_html_text(self, html_text):
        """Remove HTML tags from text"""
        import re
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        return clean_text.strip()
    
    def send_agent_text_message(self, telegram_chat_id, message_text):
        """Send agent text message to Telegram"""
        if not message_text:
            return
        
        self.bot.send_message(
            chat_id=telegram_chat_id,
            text=_("💬 **Support Agent Response:**\n\n{message_text}").format(message_text=message_text),
            parse_mode=telegram.ParseMode.MARKDOWN
        )
    
    def send_attachment_to_telegram(self, telegram_chat_id, file_content, filename, mime_type):
        """Send a single attachment to Telegram"""
        try:
            if mime_type.startswith('image/'):
                # Send as photo
                self.bot.send_photo(
                    chat_id=telegram_chat_id,
                    photo=file_content,
                    caption=_("📎 Agent sent: {filename}").format(filename=filename)
                )
            else:
                # Send as document
                self.bot.send_document(
                    chat_id=telegram_chat_id,
                    document=file_content,
                    filename=filename,
                    caption=_("📎 Agent sent: {filename}").format(filename=filename)
                )
        except Exception as send_error:
            print(f"Error sending attachment {filename} to Telegram: {send_error}")
            # Fallback: send as document if photo fails
            try:
                self.bot.send_document(
                    chat_id=telegram_chat_id,
                    document=file_content,
                    filename=filename,
                    caption=_("📎 Agent sent: {filename}").format(filename=filename)
                )
            except Exception as fallback_error:
                print(f"Fallback also failed for {filename}: {fallback_error}")
    
    def send_article_attachments_to_telegram(self, article_id, telegram_chat_id):
        """Download and send attachments from Zammad article to Telegram"""
        try:
            # Get list of attachments for this article
            attachments = zammad_api.get_article_attachments(article_id)
            
            if not attachments:
                return
                
            for attachment in attachments:
                attachment_id = attachment.get('id')
                filename = attachment.get('filename', 'attachment')
                mime_type = attachment.get('preferences', {}).get('Mime-Type', '')
                
                if not attachment_id:
                    continue
                    
                # Download the attachment content
                file_content = zammad_api.download_attachment(article_id, attachment_id)
                if not file_content:
                    continue
                    
                # Send the attachment
                self.send_attachment_to_telegram(telegram_chat_id, file_content, filename, mime_type)
                        
        except Exception as e:
            print(f"Error processing attachments for article {article_id}: {e}")


class AgentResponseHandler:
    """Handles agent responses from Zammad to Telegram"""
    
    def handle_agent_response(self, ticket_id, article_info):
        """Send agent response from Zammad to Telegram user"""
        try:
            # Find the ticket in our local DB
            open_ticket = OpenTicket.objects.get(zammad_ticket_id=ticket_id)
            
            # Create telegram handler for this specific bot
            telegram_handler = TelegramMessageHandler(open_ticket.bot.token)
            
            # Handle text content
            response_body = article_info.get('body', '')
            clean_text = telegram_handler.clean_html_text(response_body)
            telegram_handler.send_agent_text_message(open_ticket.telegram_id, clean_text)
            
            # Handle attachments
            article_id = article_info.get('id')
            if article_id:
                telegram_handler.send_article_attachments_to_telegram(article_id, open_ticket.telegram_id)
            
        except ObjectDoesNotExist:
            pass
        except Exception as e:
            print(f"Error sending agent response to Telegram: {e}")


# --- ADD THIS ENTIRE NEW FUNCTION ---
def handle_callback_query(query, bot, bot_record):
    """Handles all button presses."""
    user = query.from_user
    chat_id = query.message.chat.id
    message_id = query.message.message_id

    # Customer selection callback is no longer used - we switched to text input
    # if query.data.startswith('cust_'):
    #     handle_customer_selection_callback(query, bot, bot_record)
    #     return

    # Check if the button pressed is our cancel button
    if query.data.startswith('cancel_ticket_'):
        # Give instant feedback to the user
        bot.answer_callback_query(callback_query_id=query.id, text=_("Processing your cancellation..."))

        # Get the ticket ID from the button's data
        ticket_id = int(query.data.split('_')[-1])

        # 1. Tell Zammad to close the ticket
        success = zammad_api.close_zammad_ticket(ticket_id, user.first_name)

        if success:
            # 2. If Zammad confirmed, delete the ticket from our local database
            OpenTicket.objects.filter(zammad_ticket_id=ticket_id).delete()
            response_text = _("✅ Your ticket has been successfully canceled.")
        else:
            response_text = _("❌ There was an error canceling your ticket in Zammad. Please contact an administrator.")

        # 3. Edit the original message to show the final result
        bot.edit_message_text(text=response_text, chat_id=chat_id, message_id=message_id)

