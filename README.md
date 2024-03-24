# SunPeach Solar Gmail to Hubspot Integration

This project is a Python script that extracts email addresses, names, and mailing addresses from Gmail emails and syncs them with HubSpot CRM. It helps in automating the process of adding or updating contacts in HubSpot based on the information extracted from Gmail emails.

## Features

- Fetches unprocessed emails from a specified Gmail account
- Extracts email addresses, names, and mailing addresses from email bodies
- Creates or updates contacts in HubSpot CRM with the extracted information
- Marks processed emails with a custom label in Gmail
- Writes the extracted data to a CSV file for backup or further processing

## Prerequisites

Before running the script, make sure you have the following:

- Python 3.x installed
- A Gmail account with API access enabled
- A HubSpot account with API access enabled

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/gmail-to-hubspot-sync.git

2. Install the required dependencies:

    ```bash
    pip install -r requirements.txt

### Set up the Gmail API:
- Enable the Gmail API in the Google Cloud Console
- Create a service account and download the JSON key file
- Place the JSON key file in the project directory

### Set up the HubSpot API:
- Create a HubSpot API key in your HubSpot account settings
- Update the HUBSPOT_API_KEY variable in the email_extractor.py file with your API key
Configuration
- Open the email_extractor.py file in a text editor.
- Update the following variables with your own values:
- SERVICE_ACCOUNT_FILE: Path to the Gmail API service account JSON key file
- HUBSPOT_API_KEY: Your HubSpot API key
- Customize the extract_info function to match the format of your email bodies and extract the desired information.
Usage

