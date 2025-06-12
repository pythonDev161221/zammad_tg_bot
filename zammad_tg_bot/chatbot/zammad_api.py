import os
import requests
import json


# --- Helper function to find or create a user ---
def find_or_create_customer(telegram_id, telegram_name, phone_number=None):
    """
    Checks if a Zammad user exists. If not, creates one.
    Now includes an optional phone number.
    """
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")

    login_name = f"telegram_user_{telegram_id}"
    search_url = f"{zammad_url}/api/v1/users/search?query=login:{login_name}"
    headers = {
        "Authorization": f"Token token={zammad_token}",
        "Content-Type": "application/json"
    }

    try:
        # 1. Search for the user
        print(f"Searching for Zammad user: {login_name}")
        search_response = requests.get(search_url, headers=headers, timeout=10)
        search_response.raise_for_status()

        if len(search_response.json()) > 0:
            print("User already exists.")
            return login_name

        # 2. If not found, create the user
        print(f"User not found. Creating new user: {login_name}")
        create_url = f"{zammad_url}/api/v1/users"

        create_payload = {
            "login": login_name,
            "firstname": telegram_name,
            "lastname": "(Telegram)",
            "email": f"{login_name}@telegram.bot.local",
            "roles": ["Customer"],
            "active": True
        }

        # *** NEW: Add phone number to payload if it exists ***
        if phone_number:
            create_payload['phone'] = phone_number
            print(f"Adding phone number to new user: {phone_number}")

        print(f"DEBUG: Sending this payload to Zammad: {json.dumps(create_payload, indent=2)}")
        create_response = requests.post(
            create_url,
            headers=headers,
            data=json.dumps(create_payload),
            timeout=10
        )

        if create_response.status_code >= 400:
            print(f"Error creating user! Status: {create_response.status_code}")
            print(f"Response Body: {create_response.text}")
            create_response.raise_for_status()

        print("Successfully created new user.")
        return login_name

    except requests.exceptions.RequestException as e:
        print(f"An error occurred in find_or_create_customer: {e}")
        return None


# --- Main function to create the ticket ---
def create_zammad_ticket(title, body, customer_telegram_id, customer_telegram_name, phone_number=None):
    """
    Creates a new ticket in Zammad. Now accepts an optional phone number.
    """
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")

    if not zammad_url or not zammad_token:
        print("Zammad URL or Token not found in environment variables.")
        return None

    # Step 1: Ensure the customer exists, passing the phone number along
    customer_login = find_or_create_customer(customer_telegram_id, customer_telegram_name, phone_number)
    if not customer_login:
        print("Failed to find or create customer. Aborting ticket creation.")
        return None

    # Step 2: Create the ticket
    url = f"{zammad_url}/api/v1/tickets"
    headers = {
        "Authorization": f"Token token={zammad_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "title": title,
        "group": "Users",
        "customer": customer_login,
        "article": {
            "subject": title,
            "body": body,
            "type": "note",
            "internal": False,
        }
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)

        if response.status_code >= 400:
            print(f"Error creating ticket! Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            response.raise_for_status()

        ticket_data = response.json()
        print(f"Successfully created Zammad ticket: {ticket_data.get('number')}")
        return ticket_data

    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to Zammad for ticket creation: {e}")
        return None