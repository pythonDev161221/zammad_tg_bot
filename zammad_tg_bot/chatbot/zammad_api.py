import os
import requests
import json


def create_zammad_ticket(title, body):
    """
    Creates a new ticket in Zammad as a predefined Agent.
    """
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")
    agent_email = os.getenv("ZAMMAD_AGENT_EMAIL")  # Get the agent's email

    if not all([zammad_url, zammad_token, agent_email]):
        print("Zammad URL, Token, or Agent Email not found in environment variables.")
        return None

    url = f"{zammad_url}/api/v1/tickets"
    headers = {
        "Authorization": f"Token token={zammad_token}",
        "Content-Type": "application/json",
    }

    # The customer is now our predefined Agent
    payload = {
        "title": title,
        "group": "Users",
        "customer": agent_email,  # <-- THE KEY CHANGE!
        "article": {
            "subject": title,
            "body": body,
            "type": "note",
            "internal": False,
        }
    }

    try:
        print(f"Creating ticket as agent: {agent_email}")
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)

        if response.status_code >= 400:
            print(f"Error creating ticket! Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            response.raise_for_status()

        ticket_data = response.json()
        print(f"Successfully created Zammad ticket: {ticket_data.get('number')}")
        return ticket_data

    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to Zammad: {e}")
        return None