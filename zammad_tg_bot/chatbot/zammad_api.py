import os
import requests
import json

def create_zammad_ticket(title, body):
    """
    Creates a new ticket in Zammad using the single agent token.
    The customer is NOT a Zammad user, their info is in the ticket body.
    """
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")
    agent_email = os.getenv("ZAMMAD_AGENT_EMAIL") # We'll add this to .env

    if not all([zammad_url, zammad_token, agent_email]):
        print("Zammad URL, Token, or Agent Email not found in environment variables.")
        return None

    url = f"{zammad_url}/api/v1/tickets"
    headers = {
        "Authorization": f"Token token={zammad_token}",
        "Content-Type": "application/json",
    }

    # The customer for the ticket is now the agent themselves.
    # The actual user's info is inside the ticket body.
    payload = {
        "title": title,
        "group": "Users",  # Or your correct group name
        "customer": agent_email,
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