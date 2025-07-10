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

    url = f"{zammad_url}/api/v1/tickets/{ticket_id}?expand=true"
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


def add_note_to_ticket(ticket_id, user_name, note_body):
    """Adds a new text article (note) to an existing Zammad ticket."""
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")

    if not all([zammad_url, zammad_token]):
        print("Zammad URL or Token not found.")
        return False

    url = f"{zammad_url}/api/v1/ticket_articles"
    headers = {
        "Authorization": f"Token token={zammad_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "ticket_id": ticket_id,
        "body": f"<b>New message from {user_name} (Telegram):</b><br>{note_body}",
        "type": "note",
        "internal": False,
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        response.raise_for_status()
        print(f"Successfully added note to ticket ID: {ticket_id}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error adding note to ticket: {e}")
        return False


# Add this import at the top of the file
import base64


# ... (other functions are the same) ...


# --- REPLACE THE OLD ATTACHMENT FUNCTION WITH THIS NEW BASE64 VERSION ---
def add_attachment_to_ticket(ticket_id, user_name, file_content, filename, caption=None):
    """
    Adds an attachment to a ticket by updating the ticket itself
    with a Base64 encoded file payload. This is a more reliable method.
    """
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")

    if not all([zammad_url, zammad_token]):
        print("Zammad URL or Token not found.")
        return False

    # IMPORTANT: We are now updating the ticket, not creating a new article directly.
    url = f"{zammad_url}/api/v1/tickets/{ticket_id}"
    headers = {
        "Authorization": f"Token token={zammad_token}",
        "Content-Type": "application/json",
    }

    # 1. Encode the file content into a Base64 string.
    # The .decode('utf-8') is crucial to make it a JSON-serializable string.
    encoded_file = base64.b64encode(file_content).decode('utf-8')

    # 2. Build the JSON payload.
    # Create body text based on whether caption is provided
    if caption:
        body_text = f"<b>New message from {user_name} (Telegram):</b><br>{caption}"
    else:
        body_text = f"User {user_name} sent a file."
    
    payload = {
        # We are adding a new "article" to the ticket
        "article": {
            "subject": "New Attachment from Telegram",
            "body": body_text,
            "internal": False,
            # This is the special structure for Base64 attachments
            "attachments": [
                {
                    "filename": filename,
                    "data": encoded_file,
                    "mime-type": "image/jpeg",  # We can hardcode for photos
                }
            ]
        }
    }

    try:
        print(f"Uploading {filename} via Base64 to ticket {ticket_id}...")
        # IMPORTANT: We use the PUT method to update the ticket
        response = requests.put(url, headers=headers, data=json.dumps(payload), timeout=90)

        if response.status_code >= 400:
            print(f"--- ZAMMAD UPLOAD ERROR (Base64) ---")
            print(f"Status Code: {response.status_code}")
            print(f"Response Body: {response.text}")
            print(f"------------------------------------")
            return False

        print(f"Successfully added Base64 attachment to ticket ID: {ticket_id}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"A network-level error occurred adding Base64 attachment: {e}")
        return False


def get_article_attachments(article_id):
    """
    Fetches attachments for a specific article from Zammad.
    First gets the article details, then extracts attachment info.
    """
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")

    if not all([zammad_url, zammad_token]):
        print("Zammad URL or Token not found.")
        return []

    # Get article details which should include attachment info
    url = f"{zammad_url}api/v1/ticket_articles/{article_id}"
    headers = {"Authorization": f"Token token={zammad_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        article = response.json()
        
        # DEBUG: Print article structure to understand attachment format
        print(f"=== ARTICLE {article_id} DETAILS ===")
        print(json.dumps(article, indent=2, default=str))
        print(f"================================")
        
        # Extract attachments from article data
        attachments = article.get('attachments', [])
        print(f"Found {len(attachments)} attachments for article {article_id}")
        return attachments
    except requests.exceptions.RequestException as e:
        print(f"Error fetching article details: {e}")
        return []


def download_attachment(article_id, attachment_id):
    """
    Downloads a specific attachment from Zammad.
    Returns the file content as bytes or None if failed.
    """
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")

    if not all([zammad_url, zammad_token]):
        print("Zammad URL or Token not found.")
        return None

    # Try different possible attachment download endpoints
    possible_urls = [
        f"{zammad_url}api/v1/ticket_attachment/{article_id}/{attachment_id}",
        f"{zammad_url}api/v1/ticket_articles/{article_id}/attachments/{attachment_id}",
        f"{zammad_url}api/v1/attachments/{attachment_id}"
    ]
    
    headers = {"Authorization": f"Token token={zammad_token}"}

    for url in possible_urls:
        try:
            print(f"Trying attachment download URL: {url}")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            print(f"Successfully downloaded attachment {attachment_id} from {url}")
            return response.content
        except requests.exceptions.RequestException as e:
            print(f"Failed URL {url}: {e}")
            continue
    
    print(f"All attachment download URLs failed for attachment {attachment_id}")
    return None

