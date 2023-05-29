import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Configure logging
logging.basicConfig(filename='app.log', filemode='w', level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

# Path to your Service Account key file
key_file_path = 'directory-test-387900-a9df781feda6.json'

# Load the Service Account credentials
creds = service_account.Credentials.from_service_account_file(
    key_file_path,
    scopes=['https://www.googleapis.com/auth/admin.directory.user', 'https://www.googleapis.com/auth/contacts'])

# Create a service object for the admin user
admin_creds = creds.with_subject('YOUR_Service_Account_KEY.json')  # Replace with your Google Workspace admin user
service_admin = build('admin', 'directory_v1', credentials=admin_creds)

# Get all users
results = service_admin.users().list(customer='YOUR_CUSTOMER_ID').execute()
users = results.get('users', [])

# For each user
for user in users:
    # Delegating authority to the service account to impersonate the current user
    user_creds = creds.with_subject(user['primaryEmail'])
    service = build('people', 'v1', credentials=user_creds)

    # Get the user's contact list
    connections = service.people().connections().list(resourceName='people/me', personFields='names,emailAddresses,occupations,organizations,phoneNumbers').execute()
    contact_list = connections.get('connections', [])

    # Get the email addresses of all contacts
    contact_emails = [contact.get('emailAddresses', [{}])[0].get('value') for contact in contact_list]

    # For each other user
    for contact in users:
        if contact['primaryEmail'] != user['primaryEmail']:
            # Prepare contact info
            contact_info = {
                'names': [{'givenName': contact['name']['fullName']}],
                'emailAddresses': [{'value': contact['primaryEmail']}],
            }

            '''
            此部分Contacts中的Job title & company 沒有寫入成功
            '''
            # if 'organizations' in contact and contact['organizations']:
            #     if 'title' in contact['organizations'][0]:
            #         contact_info['organizations'] = [{'title': contact['organizations'][0]['title']}]
            #     if 'orgUnitPath' in contact:
            #         if contact_info.get('organizations'):
            #             contact_info['organizations'][0]['name'] = contact['orgUnitPath']
            #         else:
            #             contact_info['organizations'] = [{'name': contact['orgUnitPath']}]

            if 'phones' in contact and contact['phones']:
                contact_info['phoneNumbers'] = [{'value': contact['phones'][0]['value']}]

            # Check if the contact already exists in the user's contact list
            if not any(c for c in contact_list if c.get('emailAddresses', [{}])[0].get('value') == contact['primaryEmail']):
                # Add to user's contact list
                service.people().createContact(body=contact_info).execute()
                # Log successful contact creation
                logging.info(f"Added contact: {contact['primaryEmail']} to {user['primaryEmail']}")

    # For each contact email
    for contact_email in contact_emails:
        # If the contact email does not exist in the Directory
        if not any(u for u in users if u['primaryEmail'] == contact_email):
            # Find the contact in the contact list
            contact = next((c for c in contact_list if c.get('emailAddresses', [{}])[0].get('value') == contact_email), None)
            if contact:
                # Delete the contact
                service.people().deleteContact(resourceName=contact['resourceName']).execute()
                # Log successful contact deletion
                logging.info(f"Deleted contact: {contact_email} from {user['primaryEmail']}")
