import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import re


# Placeholder function to initialize Gmail API service
def get_gmail_service(user_id='me'):
    # Load OAuth 2.0 credentials and initialize the Gmail API service
    # This should handle loading credentials securely, refreshing tokens as needed
    credentials = Credentials(...)  # Load your credentials here
    service = build('gmail', 'v1', credentials=credentials)
    return service


def get_label_id(service, user_id, label_name):
    """
    Check if a label exists in the user's account and return its ID.

    :param service: Authorized Gmail API service instance.
    :param user_id: User's email address or 'me' for the authenticated user.
    :param label_name: Name of the label to search for.
    :return: The ID of the label if it exists, None otherwise.
    """
    try:
        labels = service.users().labels().list(userId=user_id).execute()
        for label in labels['labels']:
            if label['name'] == label_name:
                return label['id']
    except Exception as e:
        print(f"An error occurred: {e}")
    return None


def ensure_label_exists(service, user_id, label_name):
    """
    Ensure a label exists in the user's account. Create it if it doesn't.

    :param service: Authorized Gmail API service instance.
    :param user_id: User's email address or 'me' for the authenticated user.
    :param label_name: Name of the label to ensure exists.
    :return: The ID of the existing or newly created label.
    """
    label_id = get_label_id(service, user_id, label_name)
    if label_id is None:
        label_id = create_label(service, user_id, label_name)
    return label_id


def extract_info(email_body):
    # Update regex to also try to extract names and mailing addresses if feasible
    # This part is highly dependent on the format of your emails
    emails = re.findall(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', email_body)
    names = ["Extracted Name"]  # Implement your logic for name extraction
    # Add logic for extracting mailing addresses
    addresses = ["Extracted Address"]
    return names, emails, addresses


def process_emails(service, user_id='me', processed_label_id=None):
    processed_label_name = "HS_PROCESSED"
    processed_label_id = ensure_label_exists(
        service, user_id, processed_label_name)

    # Fetch a list of emails that do not have the 'processed' label
    query = f"-label:{processed_label_id}"
    results = service.users().messages().list(userId=user_id, q=query).execute()
    messages = results.get('messages', [])

    for message in messages:
        msg = service.users().messages().get(
            userId=user_id, id=message['id'], format='full').execute()

        # Extract the email body, considering the possibility of different parts
        email_body = ''
        if 'parts' in msg['payload']:
            for part in msg['payload']['parts']:
                if part['mimeType'] == 'text/plain' or part['mimeType'] == 'text/html':
                    email_body += base64.urlsafe_b64decode(
                        part['body']['data']).decode('utf-8')
        else:
            email_body = base64.urlsafe_b64decode(
                msg['payload']['body']['data']).decode('utf-8')

        names, emails, addresses = extract_info(email_body)
        send_to_hubspot(names, emails, addresses)

        # Mark the email as processed by adding the custom label
        service.users().messages().modify(
            userId=user_id, id=message['id'],
            body={'addLabelIds': [processed_label_id]}).execute()


def create_label(service, user_id, label_name):
    label_body = {
        'name': label_name,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show'
    }
    label = service.users().labels().create(
        userId=user_id, body=label_body).execute()
    return label['id']


def send_to_hubspot(names, emails, addresses):
    """
    Send extracted data to HubSpot's Contacts API.

    :param names: List of extracted names from emails
    :param emails: List of extracted email addresses from emails
    :param addresses: List of extracted mailing addresses from emails
    """
    HUBSPOT_API_KEY = "YOUR_HUBSPOT_API_KEY"
    HUBSPOT_ENDPOINT = f"https://api.hubapi.com/contacts/v1/contact/createOrUpdate/email/"

    headers = {
        "Content-Type": "application/json"
    }

    for name, email, address in zip(names, emails, addresses):
        # Construct the request payload according to HubSpot's API requirements
        # This is a basic example; customize the properties as needed
        data = {
            "properties": [
                {"property": "email", "value": email},
                {"property": "firstname", "value": name},
                {"property": "address", "value": address}
            ]
        }

        # Append the email to the endpoint as per API documentation for upsert functionality
        url = f"{HUBSPOT_ENDPOINT}{email}/?hapikey={HUBSPOT_API_KEY}"

        # Make the request to HubSpot's API
        response = requests.post(url, json=data, headers=headers)

        # Handle the response
        if response.status_code == 200:
            print(f"Successfully updated/created contact for {email}.")
        else:
            print(
                f"Failed to update/create contact for {email}. Response: {response.text}")

# This function could be your Cloud Function's entry point if triggering based on a schedule


def scheduled_function(event, context):
    service = get_gmail_service()
    process_emails(service)
