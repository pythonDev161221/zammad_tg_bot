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


def get_ticket_details(ticket_id):
    """
    Fetches details for a single ticket from Zammad by its ID.
    """
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")

    if not all([zammad_url, zammad_token]):
        print("Zammad URL or Token not found.")
        return None

    url = f"{zammad_url}/api/v1/tickets/{ticket_id}"
    headers = {"Authorization": f"Token token={zammad_token}"}

    try:
        print(f"Fetching details for Zammad ticket ID: {ticket_id}")
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 404:
            print("Ticket not found in Zammad.")
            return {"error": "not_found"}

        response.raise_for_status()  # Raise an error for other bad responses
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error fetching ticket details: {e}")
        return None


def close_zammad_ticket(ticket_id, user_name):
    """
    Updates a ticket in Zammad to set its state to 'closed'.
    Adds a note explaining why it was closed.
    """
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")

    if not all([zammad_url, zammad_token]):
        print("Zammad URL or Token not found.")
        return False

    url = f"{zammad_url}/api/v1/tickets/{ticket_id}"
    headers = {
        "Authorization": f"Token token={zammad_token}",
        "Content-Type": "application/json",
    }

    # The payload to update the ticket
    payload = {
        "state": "closed",  # Set the state to closed
        "article": {  # Add a final note explaining the action
            "body": f"Ticket closed by user '{user_name}' from Telegram.",
            "internal": True,  # Make this an internal note for agents
        }
    }

    try:
        print(f"Attempting to close Zammad ticket ID: {ticket_id}")
        response = requests.put(url, headers=headers, data=json.dumps(payload), timeout=10)

        if response.status_code >= 400:
            print(f"Error closing ticket! Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            return False

        print(f"Successfully closed ticket ID: {ticket_id}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Zammad to close ticket: {e}")
        return False
