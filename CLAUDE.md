# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Django-based Telegram bot system that integrates with Zammad ticketing platform. The system supports **multiple independent Telegram bots** (bot1, bot2, bot3) operating within a single Django application, each with its own token and Zammad group configuration.

## Development Commands

### Setup and Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
cd zammad_tg_bot
python manage.py migrate

# Setup bots from environment variables
python manage.py setup_bots

# Create Django admin superuser
python manage.py createsuperuser
```

### Running the Application
```bash
# Start Django development server
cd zammad_tg_bot
python manage.py runserver
```

### Internationalization
The project supports 3 languages: Kyrgyz (ky - default), English (en), and Russian (ru).

```bash
# Generate message files for translation
python manage.py makemessages -l ky -l en -l ru

# Compile translation files
python manage.py compilemessages
```

## Architecture

### Multi-Bot Architecture
The system uses a **bot-token-based webhook routing** pattern:
- Each bot has a unique webhook URL: `/webhook/<bot_token>/`
- The `telegram_webhook` view validates the token and routes to the correct bot instance
- Bot configuration is stored in the database (`TelegramBot` and `ZammadGroup` models)
- Tokens are configured via environment variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_TOKEN_2`, `TELEGRAM_BOT_TOKEN_3`

### Core Models
- **TelegramBot**: Stores bot name and token
- **ZammadGroup**: One-to-one with TelegramBot; stores Zammad group, customer naming convention (prefix, last_name)
- **Customer**: Represents gas station customers; `first_name` is actually the customer number (integer)
- **OpenTicket**: Tracks active Telegram-to-Zammad ticket mappings
- **Question**: Configurable questions asked during ticket creation; supports text, photo, and choice types

### Ticket Creation Flow
1. User sends contact → customer number selection
2. User enters customer number (e.g., "123" for AZS_123)
3. Issue type selection (7 predefined types, each mapped to a priority)
4. Dynamic question flow (if questions configured)
5. Ticket created in Zammad with all collected data
6. Photos from questions attached to ticket as separate articles

### Webhook Integration
Two webhook endpoints:
- **Telegram**: `/webhook/<bot_token>/` - receives updates from Telegram
- **Zammad**: `/webhook/zammad/` - receives agent responses and ticket closures

Zammad webhook handles:
- Agent article creation → sends to Telegram user
- Ticket state change to "closed" → notifies user and deletes OpenTicket record
- Attachments from Zammad → forwarded to Telegram

### Key Architecture Patterns
- **State Management**: Django cache used for multi-step ticket creation flow (`pending_ticket_{user_id}_{bot_id}`)
- **Message Priority**: `handle_message()` dispatcher checks in order: open ticket updates → question answers → customer number input → commands
- **Class-Based API**: `zammad_api.py` uses manager classes (ZammadTicketManager, ZammadAttachmentManager, ZammadArticleManager) with backward-compatible function wrappers
- **Stale Ticket Cleanup**: Before creating new tickets, checks if existing OpenTicket in DB is actually closed in Zammad

## Environment Variables Required

Create `.env` file in `zammad_tg_bot/` directory:
```
SECRET_KEY=your_django_secret_key
TELEGRAM_BOT_TOKEN=bot1_token_here
TELEGRAM_BOT_TOKEN_2=bot2_token_here
TELEGRAM_BOT_TOKEN_3=bot3_token_here
NGROK_DOMAIN=your_public_domain_or_ngrok_url
ZAMMAD_URL=https://your-zammad-instance.com/
ZAMMAD_TOKEN=your_zammad_api_token
ZAMMAD_AGENT_EMAIL=agent@example.com
```

## Important Implementation Details

### Customer Naming Convention
Customers are created in Zammad using the pattern:
- Email: `{customer_prefix}_{customer_number}.{customer_last_name}@customer.local`
- First name: `{customer_prefix}_{customer_number}` (e.g., "AZS_123")
- Last name: From `ZammadGroup.customer_last_name`

The Customer model's `first_name` field is an IntegerField storing just the number.

### Issue Type to Priority Mapping
Issue types automatically set ticket priority:
- Low (1): Ticket mistake, No internet, Email not working, Questions
- Medium (2): One workplace not works, One fuel pump not works
- High (3): Gas station not works

### Translation Usage
All user-facing strings use Django's `gettext` (`_()` function). The middleware sets language based on user preferences. Default language is Kyrgyz (ky).

## Testing

The project structure includes `chatbot/tests.py` but no tests are currently implemented.
