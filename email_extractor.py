"""
Module: email_extractor.py

This module provides functionality to extract email addresses, names, and mailing addresses
from Gmail emails and send the extracted data to HubSpot CRM.

The module uses the Gmail API to fetch emails and extract relevant information. It also
integrates with the HubSpot API to create or update contacts based on the extracted data.

Functions:
    - get_gmail_service(): Initializes the Gmail API service.
    - get_label_id(): Retrieves the label ID for a given label name.
    - ensure_label_exists(): Ensures that a label exists in Gmail, creating it if necessary.
    - extract_info(): Extracts names, email addresses, and mailing addresses from an email body.
    - process_emails(): Processes unread emails, extracts data, and sends it to HubSpot.
    - create_label(): Creates a new label in Gmail.
    - send_to_hubspot(): Sends the extracted data to HubSpot CRM to create or update contacts.
    - write_to_csv(): Writes the extracted data to a CSV file.
    - scheduled_function(): Entry point for the Cloud Function to process emails on a schedule.

Dependencies:
    - googleapiclient: Google API client library for accessing Gmail API.
    - google-auth: Google authentication library for handling credentials.
    - requests: HTTP library for making requests to the HubSpot API.
    - csv: CSV library for writing data to CSV files.
    - logging: Logging library for logging messages.
    - re: Regular expression library for pattern matching.
    - os: Operating system library for file and path handling.

"""
from nameparser.parser import HumanName
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.api_core.exceptions import GoogleAPICallError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import csv
import logging
import os
import re
import json
import email
import base64
import requests
import nltk

nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('maxent_ne_chunker')
nltk.download('words')


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print(os.getenv('AUTHORIZATION_CODE'))

EXCLUDE_LIST = [
    "Google Account",
    "Ampitheatre Parkway",
    "St",
    "Rd",
    "Dr",
    "Android",
    "Google",
    "Mountain",
    "Discover",
]


def exchange_code_for_token_and_save():
    """_summary_

    Returns:
        _type_: _description_
    """
    token_url = "https://oauth2.googleapis.com/token"
    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    token_data = {
        "code": os.getenv('AUTHORIZATION_CODE'),
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "http://localhost:8080",
        "grant_type": "authorization_code",
        "access_type": "offline"
    }
    try:
        response = requests.post(token_url, data=token_data, timeout=10)
        response.raise_for_status()  # This will raise an exception for HTTP error responses
        tokens = response.json()  # Return the parsed JSON response

        # Prepare the data to be saved, including the client_id and client_secret for future refreshes
        save_data = {
            "refresh_token": tokens.get("refresh_token"),
            "client_id": client_id,
            "client_secret": client_secret,
            "token_uri": token_url,
            "scopes": "https://www.googleapis.com/auth/gmail.modify"
        }

        # Save the credentials for the next run
        with open('creds.json', 'w', encoding='utf-8') as file:
            json.dump(save_data, file)

        print("Tokens saved to creds.json")
        return tokens
    except requests.exceptions.HTTPError as e:
        # HTTP error occurred
        print(f"HTTP Error: {e.response.status_code} {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        # Other errors (e.g., network issues)
        print(f"Request Exception: {e}")
        return None


le_tokens = exchange_code_for_token_and_save()
print("TOKENS", le_tokens)


def get_credentials():
    """Initialize Google API credentials from saved tokens and client info."""
    # Load the saved tokens and client info
    with open('./creds.json', 'r', encoding='utf-8') as file:
        token_info = json.load(file)

    creds = Credentials(
        token=token_info.get("access_token"),
        refresh_token=token_info.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token_info.get("client_id"),
        client_secret=token_info.get("client_secret"),
        scopes=['https://www.googleapis.com/auth/gmail.modify']
    )

    return creds


def get_gmail_service():
    """Initialize the Gmail API service with OAuth 2.0 credentials."""
    creds = get_credentials()
    if not creds.valid:
        creds.refresh(Request())

    service = build('gmail', 'v1', credentials=creds)
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
    except GoogleAPICallError as e:
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


def get_human_names(text):
    tokens = nltk.tokenize.word_tokenize(text)
    pos = nltk.pos_tag(tokens)
    sentt = nltk.ne_chunk(pos, binary=False)
    person_list = []
    for subtree in sentt.subtrees(filter=lambda t: t.label() == 'PERSON'):
        person = []
        for leaf in subtree.leaves():
            person.append(leaf[0])
        # Check if any part of the name is in the EXCLUDE_LIST
        if not any(part in EXCLUDE_LIST for part in person):
            name = ' '.join(person)
            if len(person) > 1 and name not in person_list:  # avoid grabbing lone surnames
                person_list.append(name)
    return person_list


def format_names(names):
    """Format names in 'LAST, FIRST' order."""
    formatted_names = []
    for name in names:
        human_name = HumanName(name)
        last_first = f"{human_name.last}, {human_name.first}".strip(', ')
        formatted_names.append(last_first)
    return formatted_names


def extract_info(email_body):
    """Extracts names, email addresses, mailing addresses, and phone numbers from the email body.

    Args:
        email_body (str): The body of the email from which to extract information.

    Returns:
        tuple: A tuple containing lists of names, emails, addresses, and phone numbers extracted from the email body.
    """
    # Regular expression patterns
    email_pattern = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    phone_pattern = re.compile(
        r'\b(?:\+?(\d{1,3}))?[-. ]?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b')
    # This is a simplistic pattern and may need refinement.
    address_pattern = re.compile(r'\d+\s[A-Za-z]+\s[A-Za-z]+')

    # Extracting information
    emails = email_pattern.findall(email_body)
    phones = phone_pattern.findall(email_body)
    names = get_human_names(email_body)
    addresses = address_pattern.findall(email_body)

    # Log the extracted information
    logger.info("Extracted %d names: %s", len(names), names)
    logger.info("Extracted %d emails: %s", len(emails), emails)
    logger.info("Extracted %d addresses: %s", len(addresses), addresses)
    logger.info("Extracted %d phone numbers: %s", len(phones), phones)

    return names, emails, addresses, phones


def get_mime_message(service, user_id, message_id):
    """Get a MIME Message for a given message ID using the Gmail API."""
    try:
        message = service.users().messages().get(
            userId=user_id, id=message_id, format='raw').execute()
        msg_raw = base64.urlsafe_b64decode(message['raw'].encode('ASCII'))
        mime_msg = email.message_from_bytes(msg_raw)
        return mime_msg
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


def get_email_body(mime_msg):
    """Recursively extract the email body from a MIME Message."""
    if mime_msg.is_multipart():
        for part in mime_msg.get_payload():
            body = get_email_body(part)
            if body:
                return body
    else:
        content_type = mime_msg.get_content_type()
        if content_type == 'text/plain' or content_type == 'text/html':
            return mime_msg.get_payload(decode=True).decode()
    return ""


def process_emails(service, user_id='me', processed_label_id=None):
    """_summary_

    Args:
        service (_type_): _description_
        user_id (str, optional): _description_. Defaults to 'me'.
        processed_label_id (_type_, optional): _description_. Defaults to None.
    """
    processed_label_name = "HS_PROCESSED"
    processed_label_id = ensure_label_exists(
        service, user_id, processed_label_name)

    query = f"-label:{processed_label_id}"
    all_data = []  # Initialize a list to collect data from all emails
    try:
        results = service.users().messages().list(userId=user_id, q=query).execute()
        messages = results.get('messages', [])
        logger.info("Found %d unprocessed emails.", len(messages))

        for message in messages:
            mime_msg = get_mime_message(service, user_id, message['id'])
            email_body = get_email_body(mime_msg)

            # Continue with extraction code for emails, addresses, and phone numbers
            names, emails, addresses, phones = extract_info(email_body)

            # Check if there's at least one name before adding to all_data
            if names:
                all_data.append({
                    'names': names,
                    'emails': emails,
                    'addresses': addresses,
                    'phones': phones
                })
            # Mark the email as processed
            # service.users().messages().modify(userId=user_id, id=message['id'], body={
            #     'addLabelIds': [processed_label_id]}).execute()
            # logger.info("Marked email %s as processed.", message['id'])

    except GoogleAPICallError as e:
        logger.error("GoogleAPICallError: %s", e)
    except HttpError as e:
        logger.error("HttpError: %s", e)
    write_to_csv(all_data)


def create_label(service, user_id, label_name):
    """_summary_

    Args:
        service (_type_): _description_
        user_id (_type_): _description_
        label_name (_type_): _description_

    Returns:
        _type_: _description_
    """
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
    hubspot_api_key = "YOUR_HUBSPOT_API_KEY"
    hubspot_endpoint = "https://api.hubapi.com/contacts/v1/contact/createOrUpdate/email/"

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
        url = f"{hubspot_endpoint}{email}/?hapikey={hubspot_api_key}"

        # Make the request to HubSpot's API with a timeout of 10 seconds
        response = requests.post(url, json=data, headers=headers, timeout=10)

        # Handle the response
        if response.status_code == 200:
            print(f"Successfully updated/created contact for {email}.")
        else:
            print(
                f"Failed to update/create contact for {email}. Response: {response.text}")


def write_to_csv(all_data):
    print("ALL DATA", all_data)
    # Determine maximum counts for dynamic column headers
    max_names = max((len(data.get('names', []))
                    for data in all_data), default=0)
    max_emails = max((len(data.get('emails', []))
                     for data in all_data), default=0)
    max_addresses = max((len(data.get('addresses', []))
                        for data in all_data), default=0)
    max_phones = max((len(data.get('phones', []))
                     for data in all_data), default=0)

    headers = []
    headers.extend([f"Name {i+1}" for i in range(max_names)])
    headers.extend([f"Email {i+1}" for i in range(max_emails)])
    headers.extend([f"Address {i+1}" for i in range(max_addresses)])
    headers.extend([f"Phone {i+1}" for i in range(max_phones)])

    with open('extracted_data.csv', mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(headers)

        for data in all_data:
            row = []
            # Append names, emails, addresses, and phones, filling missing values with ''
            row.extend(data.get('names', []) + [''] *
                       (max_names - len(data.get('names', []))))
            row.extend(data.get('emails', []) + [''] *
                       (max_emails - len(data.get('emails', []))))
            row.extend(data.get('addresses', []) + [''] *
                       (max_addresses - len(data.get('addresses', []))))
            row.extend(data.get('phones', []) + [''] *
                       (max_phones - len(data.get('phones', []))))

            writer.writerow(row)

    logger.info("Extracted data written to %s", 'extracted_data.csv')


def scheduled_function():
    """_summary_

    Args:
        event (_type_): _description_
        context (_type_): _description_
    """
    service = get_gmail_service()
    process_emails(service)


if __name__ == '__main__':
    scheduled_function()
