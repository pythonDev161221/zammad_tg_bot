import os
import requests
import json
import base64


def _get_zammad_credentials():
    """Get Zammad credentials from environment variables"""
    zammad_url = os.getenv("ZAMMAD_URL")
    zammad_token = os.getenv("ZAMMAD_TOKEN")
    agent_email = os.getenv("ZAMMAD_AGENT_EMAIL")
    
    if not all([zammad_url, zammad_token]):
        print("Zammad URL or Token not found in environment variables.")
        return None, None, None
    
    return zammad_url, zammad_token, agent_email


def _create_zammad_headers(zammad_token):
    """Create standard headers for Zammad API requests"""
    return {
        "Authorization": f"Token token={zammad_token}",
        "Content-Type": "application/json",
    }


def _build_ticket_payload(title, body, agent_email):
    """Build the payload for creating a new ticket"""
    return {
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


def _handle_zammad_response(response, operation_name):
    """Handle Zammad API response and check for errors"""
    if response.status_code >= 400:
        print(f"Error {operation_name}! Status: {response.status_code}")
        print(f"Response Body: {response.text}")
        response.raise_for_status()
    return response.json()


def create_zammad_ticket(title, body):
    """
    Creates a new ticket in Zammad using the single agent token.
    The customer is NOT a Zammad user, their info is in the ticket body.
    """
    zammad_url, zammad_token, agent_email = _get_zammad_credentials()
    
    if not all([zammad_url, zammad_token, agent_email]):
        print("Zammad URL, Token, or Agent Email not found in environment variables.")
        return None

    url = f"{zammad_url}/api/v1/tickets"
    headers = _create_zammad_headers(zammad_token)
    payload = _build_ticket_payload(title, body, agent_email)

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        ticket_data = _handle_zammad_response(response, "creating ticket")
        print(f"Successfully created Zammad ticket: {ticket_data.get('number')}")
        return ticket_data

    except requests.exceptions.RequestException as e:
        print(f"Failed to connect to Zammad for ticket creation: {e}")
        return None


def get_ticket_details(ticket_id):
    """
    Fetches details for a single ticket from Zammad by its ID.
    """
    zammad_url, zammad_token, _ = _get_zammad_credentials()
    
    if not all([zammad_url, zammad_token]):
        return None

    url = f"{zammad_url}/api/v1/tickets/{ticket_id}?expand=true"
    headers = {"Authorization": f"Token token={zammad_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 404:
            print("Ticket not found in Zammad.")
            return {"error": "not_found"}

        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error fetching ticket details: {e}")
        return None


def _build_close_ticket_payload(user_name):
    """Build payload for closing a ticket"""
    return {
        "state": "closed",
        "article": {
            "body": f"Ticket closed by user '{user_name}' from Telegram.",
            "internal": True,
        }
    }


def close_zammad_ticket(ticket_id, user_name):
    """
    Updates a ticket in Zammad to set its state to 'closed'.
    Adds a note explaining why it was closed.
    """
    zammad_url, zammad_token, _ = _get_zammad_credentials()
    
    if not all([zammad_url, zammad_token]):
        return False

    url = f"{zammad_url}/api/v1/tickets/{ticket_id}"
    headers = _create_zammad_headers(zammad_token)
    payload = _build_close_ticket_payload(user_name)

    try:
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


def _build_note_payload(ticket_id, user_name, note_body):
    """Build payload for adding a note to a ticket"""
    return {
        "ticket_id": ticket_id,
        "body": f"<b>New message from {user_name} (Telegram):</b><br>{note_body}",
        "type": "note",
        "internal": False,
    }


def add_note_to_ticket(ticket_id, user_name, note_body):
    """Adds a new text article (note) to an existing Zammad ticket."""
    zammad_url, zammad_token, _ = _get_zammad_credentials()
    
    if not all([zammad_url, zammad_token]):
        return False

    url = f"{zammad_url}/api/v1/ticket_articles"
    headers = _create_zammad_headers(zammad_token)
    payload = _build_note_payload(ticket_id, user_name, note_body)

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
        response.raise_for_status()
        print(f"Successfully added note to ticket ID: {ticket_id}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error adding note to ticket: {e}")
        return False


def _encode_file_to_base64(file_content):
    """Encode file content to Base64 string"""
    return base64.b64encode(file_content).decode('utf-8')


def _build_attachment_body_text(user_name, caption):
    """Build body text for attachment based on caption"""
    if caption:
        return f"<b>New message from {user_name} (Telegram):</b><br>{caption}"
    else:
        return f"User {user_name} sent a file."


def _build_attachment_payload(user_name, filename, encoded_file, caption):
    """Build payload for adding attachment to ticket"""
    body_text = _build_attachment_body_text(user_name, caption)
    
    return {
        "article": {
            "subject": "New Attachment from Telegram",
            "body": body_text,
            "internal": False,
            "attachments": [
                {
                    "filename": filename,
                    "data": encoded_file,
                    "mime-type": "image/jpeg",
                }
            ]
        }
    }


def add_attachment_to_ticket(ticket_id, user_name, file_content, filename, caption=None):
    """
    Adds an attachment to a ticket by updating the ticket itself
    with a Base64 encoded file payload. This is a more reliable method.
    """
    zammad_url, zammad_token, _ = _get_zammad_credentials()
    
    if not all([zammad_url, zammad_token]):
        return False

    url = f"{zammad_url}/api/v1/tickets/{ticket_id}"
    headers = _create_zammad_headers(zammad_token)
    
    encoded_file = _encode_file_to_base64(file_content)
    payload = _build_attachment_payload(user_name, filename, encoded_file, caption)

    try:
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


def _fetch_article_details(article_id, zammad_url, headers):
    """Fetch article details from Zammad API"""
    url = f"{zammad_url}api/v1/ticket_articles/{article_id}"
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def _extract_attachments_from_article(article_data):
    """Extract attachments list from article data"""
    return article_data.get('attachments', [])


def get_article_attachments(article_id):
    """
    Fetches attachments for a specific article from Zammad.
    First gets the article details, then extracts attachment info.
    """
    zammad_url, zammad_token, _ = _get_zammad_credentials()
    
    if not all([zammad_url, zammad_token]):
        return []

    headers = {"Authorization": f"Token token={zammad_token}"}

    try:
        article_data = _fetch_article_details(article_id, zammad_url, headers)
        attachments = _extract_attachments_from_article(article_data)
        return attachments
    except requests.exceptions.RequestException as e:
        print(f"Error fetching article details: {e}")
        return []


def _generate_attachment_urls(zammad_url, article_id, attachment_id):
    """Generate possible attachment download URLs"""
    return [
        f"{zammad_url}api/v1/ticket_attachment/{article_id}/{attachment_id}",
        f"{zammad_url}api/v1/ticket_articles/{article_id}/attachments/{attachment_id}",
        f"{zammad_url}api/v1/attachments/{attachment_id}"
    ]


def _try_download_from_url(url, headers):
    """Try to download attachment from a specific URL"""
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.content


def _attempt_attachment_download(possible_urls, headers):
    """Attempt to download attachment from multiple possible URLs"""
    for url in possible_urls:
        try:
            return _try_download_from_url(url, headers)
        except requests.exceptions.RequestException:
            continue
    return None


def download_attachment(article_id, attachment_id):
    """
    Downloads a specific attachment from Zammad.
    Returns the file content as bytes or None if failed.
    """
    zammad_url, zammad_token, _ = _get_zammad_credentials()
    
    if not all([zammad_url, zammad_token]):
        return None

    possible_urls = _generate_attachment_urls(zammad_url, article_id, attachment_id)
    headers = {"Authorization": f"Token token={zammad_token}"}
    
    file_content = _attempt_attachment_download(possible_urls, headers)
    
    if file_content is None:
        print(f"Error: Could not download attachment {attachment_id}")
    
    return file_content

