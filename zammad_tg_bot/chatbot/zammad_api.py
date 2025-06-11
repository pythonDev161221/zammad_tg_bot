import os
import requests
import json


def create_zammad_ticket(title, body, customer_telegram_id, customer_telegram_name):
    """
    Creates a new ticket in Zammad.
    """
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")

    if not zammad_url or not zammad_token:
        print("Zammad URL or Token not found in environment variables.")
        return None

    url = f"{zammad_url}/api/v1/tickets"
    headers = {
        "Authorization": f"Token token={zammad_token}",
        "Content-Type": "application/json",
    }

    # The customer is identified by their Telegram ID.
    # Zammad will create a new user if one with this login doesn't exist.
    customer_id = f"telegram_user_{customer_telegram_id}"

    payload = {
        "title": title,
        "group": "Users",  # Change this to a valid group in your Zammad
        "customer": customer_id,
        "article": {
            "subject": title,
            "body": body,
            "type": "note",
            "internal": False,
        }
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        response.raise_for_status()  # This will raise an error for bad responses (4xx or 5xx)

        ticket_data = response.json()
        print(f"Successfully created Zammad ticket: {ticket_data.get('number')}")
        return ticket_data

    except requests.exceptions.RequestException as e:
        print(f"Error creating Zammad ticket: {e}")
        # You might want to log the response content for debugging
        # print(f"Response content: {e.response.text}")
        return None