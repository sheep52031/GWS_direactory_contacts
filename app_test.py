import os 
from dotenv import load_dotenv
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from time import sleep
import random

# load .env
load_dotenv()

# Configure logging
logging.basicConfig(filename='app.log', filemode='w', level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

# Suppress INFO-level logs for googleapiclient.discovery_cache
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)

def process_users(users, creds, limit):
    for i, user in enumerate(users):
        if i >= limit:
            break
        try:
            # Delegating authority to the service account to impersonate the current user
            user_creds = creds.with_subject(user['primaryEmail'])
            service = build('people', 'v1', credentials=user_creds)

            # Get the user's contact list
            connections = service.people().connections().list(resourceName='people/me',\
                 personFields='names,emailAddresses,occupations,organizations,phoneNumbers').execute()
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
                    if not any(c.get('emailAddresses', [{}])[0].get('value') == contact['primaryEmail'] for c in contact_list):
                        for attempt in range(5):
                            try:
                                # Add to user's contact list
                                service.people().createContact(body=contact_info).execute()
                                # Log successful contact creation
                                logging.info(f"Added contact: {contact['primaryEmail']} to {user['primaryEmail']}")
                                break  # If the API call was successful, we break the loop
                            except googleapiclient.errors.HttpError as e:
                                if e.resp.status == 503 and attempt < 4:  # If it's a 503 error and we have attempts left
                                    wait_time = (2 ** attempt) + random.random()  # Exponential backoff with jitter
                                    logging.error(f"HttpError 503, retrying in {wait_time} seconds")
                                    time.sleep(wait_time)
                                else:
                                    logging.error(f"Failed to add contact {contact['primaryEmail']} to {user['primaryEmail']}: {e}")
                                    break


            # For each contact email
            for contact_email in contact_emails:
                # If the contact email does not exist in the Directory
                if not any(u['primaryEmail'] == contact_email for u in users):
                    # Find the contact in the contact list
                    contact = next((c for c in contact_list if c.get('emailAddresses', [{}])[0].get('value') == contact_email), None)
                    if contact:
                        # Delete the contact
                        service.people().deleteContact(resourceName=contact['resourceName']).execute()
                        # Log successful contact deletion
                        logging.info(f"Deleted contact: {contact_email} from {user['primaryEmail']}")


        except Exception as e:
            logging.error(f"Failed to process user {user['primaryEmail']}: {e}")
            continue

def main():
    # Path to your Service Account key file
    key_file_path = os.getenv('GCP_SEVERICE_ACCOUNT_KYE')

    # Load the Service Account credentials
    creds = service_account.Credentials.from_service_account_file(
        key_file_path,
        scopes=['https://www.googleapis.com/auth/admin.directory.user', 'https://www.googleapis.com/auth/contacts'])

    # Create a service object for the admin user
    admin_email = os.getenv('YOUR_ADMIN_EMAIL') 
    admin_creds = creds.with_subject(admin_email)  # Replace with your Google Workspace admin user
    service_admin = build('admin', 'directory_v1', credentials=admin_creds)

    # Get all users
    customer_id = os.getenv('YOUR_CUSTOMER_ID')
    results = service_admin.users().list(customer=customer_id).execute()
    users = results.get('users', [])

    print(f"Total number of users: {len(users)}")

    test_limit = int(input("Enter the number of users you want to process for testing: "))
    
    process_users(users, creds, test_limit)

if __name__ == "__main__":
    main()
