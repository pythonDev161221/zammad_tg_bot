import os
import requests
import json
import base64


class ZammadApiClient:
    """Base class for Zammad API operations with common functionality"""
    
    def __init__(self):
        self.zammad_url = os.getenv("ZAMMAD_URL")
        self.zammad_token = os.getenv("ZAMMAD_TOKEN")
        self.agent_email = os.getenv("ZAMMAD_AGENT_EMAIL")
        
        if not all([self.zammad_url, self.zammad_token]):
            raise ValueError("Zammad URL or Token not found in environment variables.")
    
    def get_headers(self):
        """Create standard headers for Zammad API requests"""
        return {
            "Authorization": f"Token token={self.zammad_token}",
            "Content-Type": "application/json",
        }
    
    def handle_response(self, response, operation_name):
        """Handle Zammad API response and check for errors"""
        if response.status_code >= 400:
            print(f"Error {operation_name}! Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            response.raise_for_status()
        return response.json()
    
    def make_request(self, method, url, payload=None, timeout=10):
        """Make HTTP request to Zammad API"""
        headers = self.get_headers()
        
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, timeout=timeout)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)
        elif method.upper() == 'PUT':
            response = requests.put(url, headers=headers, data=json.dumps(payload), timeout=timeout)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        return response


class ZammadTicketManager(ZammadApiClient):
    """Manages Zammad ticket operations"""
    
    def build_ticket_payload(self, title, body, group="Users", customer_email=None, priority=2):
        """Build the payload for creating a new ticket"""
        if not self.agent_email:
            raise ValueError("Agent email not found in environment variables.")
        
        # Use provided customer_email or fall back to agent_email
        customer = customer_email if customer_email else self.agent_email
        
        return {
            "title": title,
            "group_id": int(group) if group.isdigit() else 1,  # Convert to int, default to 1 (Users)
            "customer": customer,
            "priority_id": priority,  # 1=Low, 2=Medium, 3=High
            "article": {
                "subject": title,
                "body": body,
                "type": "note",
                "internal": False,
            }
        }
    
    def build_close_ticket_payload(self, user_name):
        """Build payload for closing a ticket"""
        return {
            "state": "closed",
            "article": {
                "body": f"Ticket closed by user '{user_name}' from Telegram.",
                "internal": True,
            }
        }
    
    def build_note_payload(self, ticket_id, user_name, note_body):
        """Build payload for adding a note to a ticket"""
        return {
            "ticket_id": ticket_id,
            "body": f"<b>New message from {user_name} (Telegram):</b><br>{note_body}",
            "type": "note",
            "internal": False,
        }
    
    def create_or_get_zammad_user(self, first_name, last_name):
        """Create or get Zammad user based on customer name"""
        # Generate email based on names
        email = f"{first_name.lower()}.{last_name.lower()}@customer.local"
        
        # Try to find existing user by email
        search_url = f"{self.zammad_url}/api/v1/users/search?query={email}"
        try:
            response = self.make_request('GET', search_url)
            search_results = self.handle_response(response, "searching for Zammad user")
            
            if search_results and len(search_results) > 0:
                print(f"Found existing Zammad user: {email}")
                return search_results[0]
        except requests.exceptions.RequestException as e:
            print(f"Error searching for Zammad user: {e}")
        
        # Create new Zammad user
        user_data = {
            "firstname": first_name,
            "lastname": last_name,
            "email": email,
            "login": email,
            "roles": ["Customer"]
        }
        
        create_url = f"{self.zammad_url}/api/v1/users"
        try:
            response = self.make_request('POST', create_url, user_data)
            user = self.handle_response(response, "creating Zammad user")
            print(f"Created new Zammad user: {email}")
            return user
        except requests.exceptions.RequestException as e:
            print(f"Error creating Zammad user: {e}")
            return None
    
    def create_ticket(self, title, body, group="Users", customer_first_name=None, customer_last_name=None, priority=2):
        """Creates a new ticket in Zammad with customer as the user"""
        url = f"{self.zammad_url}/api/v1/tickets"
        
        # If customer info provided, create/get Zammad user for customer
        customer_email = None
        if customer_first_name and customer_last_name:
            zammad_user = self.create_or_get_zammad_user(customer_first_name, customer_last_name)
            if zammad_user:
                customer_email = zammad_user['email']
        
        payload = self.build_ticket_payload(title, body, group, customer_email, priority)

        try:
            response = self.make_request('POST', url, payload)
            ticket_data = self.handle_response(response, "creating ticket")
            print(f"Successfully created Zammad ticket: {ticket_data.get('number')}")
            return ticket_data
        except requests.exceptions.RequestException as e:
            print(f"Failed to connect to Zammad for ticket creation: {e}")
            return None
    
    def get_ticket_details(self, ticket_id):
        """Fetches details for a single ticket from Zammad by its ID"""
        url = f"{self.zammad_url}/api/v1/tickets/{ticket_id}?expand=true"
        
        try:
            headers = {"Authorization": f"Token token={self.zammad_token}"}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 404:
                print("Ticket not found in Zammad.")
                return {"error": "not_found"}

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching ticket details: {e}")
            return None
    
    def close_ticket(self, ticket_id, user_name):
        """Updates a ticket in Zammad to set its state to 'closed'"""
        url = f"{self.zammad_url}/api/v1/tickets/{ticket_id}"
        payload = self.build_close_ticket_payload(user_name)

        try:
            response = self.make_request('PUT', url, payload)
            
            if response.status_code >= 400:
                print(f"Error closing ticket! Status: {response.status_code}")
                print(f"Response Body: {response.text}")
                return False

            print(f"Successfully closed ticket ID: {ticket_id}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to Zammad to close ticket: {e}")
            return False
    
    def add_note_to_ticket(self, ticket_id, user_name, note_body):
        """Adds a new text article (note) to an existing Zammad ticket"""
        url = f"{self.zammad_url}/api/v1/ticket_articles"
        payload = self.build_note_payload(ticket_id, user_name, note_body)

        try:
            response = self.make_request('POST', url, payload, timeout=15)
            response.raise_for_status()
            print(f"Successfully added note to ticket ID: {ticket_id}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error adding note to ticket: {e}")
            return False








class ZammadAttachmentManager(ZammadApiClient):
    """Manages Zammad attachment operations"""
    
    def encode_file_to_base64(self, file_content):
        """Encode file content to Base64 string"""
        return base64.b64encode(file_content).decode('utf-8')
    
    def build_attachment_body_text(self, user_name, caption):
        """Build body text for attachment based on caption"""
        if caption:
            return f"<b>New message from {user_name} (Telegram):</b><br>{caption}"
        else:
            return f"User {user_name} sent a file."
    
    def build_attachment_payload(self, user_name, filename, encoded_file, caption):
        """Build payload for adding attachment to ticket"""
        body_text = self.build_attachment_body_text(user_name, caption)
        
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
    
    def generate_attachment_urls(self, article_id, attachment_id):
        """Generate possible attachment download URLs"""
        return [
            f"{self.zammad_url}api/v1/ticket_attachment/{article_id}/{attachment_id}",
            f"{self.zammad_url}api/v1/ticket_articles/{article_id}/attachments/{attachment_id}",
            f"{self.zammad_url}api/v1/attachments/{attachment_id}"
        ]
    
    def try_download_from_url(self, url):
        """Try to download attachment from a specific URL"""
        headers = {"Authorization": f"Token token={self.zammad_token}"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.content
    
    def attempt_attachment_download(self, possible_urls):
        """Attempt to download attachment from multiple possible URLs"""
        for url in possible_urls:
            try:
                return self.try_download_from_url(url)
            except requests.exceptions.RequestException:
                continue
        return None
    
    def add_attachment_to_ticket(self, ticket_id, user_name, file_content, filename, caption=None):
        """Adds an attachment to a ticket with Base64 encoded file payload"""
        url = f"{self.zammad_url}/api/v1/tickets/{ticket_id}"
        
        encoded_file = self.encode_file_to_base64(file_content)
        payload = self.build_attachment_payload(user_name, filename, encoded_file, caption)

        try:
            response = self.make_request('PUT', url, payload, timeout=90)

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
    
    def download_attachment(self, article_id, attachment_id):
        """Downloads a specific attachment from Zammad"""
        possible_urls = self.generate_attachment_urls(article_id, attachment_id)
        file_content = self.attempt_attachment_download(possible_urls)
        
        if file_content is None:
            print(f"Error: Could not download attachment {attachment_id}")
        
        return file_content


class ZammadArticleManager(ZammadApiClient):
    """Manages Zammad article operations"""
    
    def fetch_article_details(self, article_id):
        """Fetch article details from Zammad API"""
        url = f"{self.zammad_url}api/v1/ticket_articles/{article_id}"
        headers = {"Authorization": f"Token token={self.zammad_token}"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    
    def extract_attachments_from_article(self, article_data):
        """Extract attachments list from article data"""
        return article_data.get('attachments', [])
    
    def get_article_attachments(self, article_id):
        """Fetches attachments for a specific article from Zammad"""
        try:
            article_data = self.fetch_article_details(article_id)
            attachments = self.extract_attachments_from_article(article_data)
            return attachments
        except requests.exceptions.RequestException as e:
            print(f"Error fetching article details: {e}")
            return []


# Create global instances for backward compatibility
ticket_manager = ZammadTicketManager()
attachment_manager = ZammadAttachmentManager()
article_manager = ZammadArticleManager()


# Backward compatibility functions
def create_zammad_ticket(title, body, group="Users", customer_first_name=None, customer_last_name=None, priority=2):
    """Creates a new ticket in Zammad (backward compatibility)"""
    return ticket_manager.create_ticket(title, body, group, customer_first_name, customer_last_name, priority)


def get_ticket_details(ticket_id):
    """Fetches details for a single ticket (backward compatibility)"""
    return ticket_manager.get_ticket_details(ticket_id)


def close_zammad_ticket(ticket_id, user_name):
    """Closes a ticket in Zammad (backward compatibility)"""
    return ticket_manager.close_ticket(ticket_id, user_name)


def add_note_to_ticket(ticket_id, user_name, note_body):
    """Adds a note to a ticket (backward compatibility)"""
    return ticket_manager.add_note_to_ticket(ticket_id, user_name, note_body)


def add_attachment_to_ticket(ticket_id, user_name, file_content, filename, caption=None):
    """Adds an attachment to a ticket (backward compatibility)"""
    return attachment_manager.add_attachment_to_ticket(ticket_id, user_name, file_content, filename, caption)


def get_article_attachments(article_id):
    """Gets attachments for an article (backward compatibility)"""
    return article_manager.get_article_attachments(article_id)


def download_attachment(article_id, attachment_id):
    """Downloads an attachment (backward compatibility)"""
    return attachment_manager.download_attachment(article_id, attachment_id)

