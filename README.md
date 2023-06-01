# Google Workspace Contacts Synchronization Script

**Github project link**：https://github.com/sheep52031/GWS_direactory_contacts

## Overview
此程式將使用者聯絡方式從 `Google Workspace Directory` 複製到 `Google Contacts`中
專為希望將Google Workspace Directory 中的成員聯絡方式匯入至每個成員帳號中的Google Contacts的組織而設計。
在 `Google Workspace Directory` 中**添加或刪除成員**後，運行此程式會自動更新`Google Contacts` 資料 。


## Requirements 
* Python 3.7 or later
* Google Workspace Admin account with access to `Directory and Contact APIs`
* Google Cloud Platform (GCP) project with the `Admin SDK` and `People API` enabled
* Service Account with `domain-wide authority` in the GCP project


## Set up
* google-auth, google-auth-httplib2, and google-auth-oauthlib for authentication
* google-api-python-client for interacting with Google APIs
* google-auth-oauthlib for OAuth 2.0 client-side flow


1. **Enable** the `Admin SDK` and `People API` in your GCP project.
2. **Create** a `Service Account` in your GCP project and generate a JSON key.
3. `Delegate domain-wide authority` to the Service Account.(**The next chapter has teaching**)
4. **Install the required dependencies**.

You can install these dependencies using pip:

```bash=
pip install --upgrade google-auth google-auth-httplib2 google-auth-oauthlib google-api-python-client python-dotenv
```
or in project root folder use
```bash=
pip install -r requirements.txt
```

5. Set up your `.env` file for sensitive data:

Create a file named .env in the root directory of the project. This file will be used to store sensitive data such as the path to your Service Account key file, your Google Workspace customer ID, and your Google Workspace admin email.

The `.env` file should have the following structure:
```.env
GCP_SEVERICE_ACCOUNT_KYE=YOUR_XXX.json
YOUR_CUSTOMER_ID=YOUR_ID_XXX
YOUR_ADMIN_EMAIL=YOUR_ADMIN_XXX@DOMAIN
```
**`GCP_SEVERICE_ACCOUNT_KYE.json` 將服務帳號憑證放專案資料夾 
`YOUR_CUSTOMER_ID`要放GWS Customer ID
`YOUR_ADMINISTATOR_EMAIL`要放GWS管理員的帳號**
![](https://hackmd.io/_uploads/HJVub9ZUn.png)

## Service Account Creation and Delegation
### To create a service account and delegate it domain-wide authority:

1. In the GCP Console, go to the **IAM & Admin** > **Service accounts** page.
2. Click on Create **Service Account** at the top of the page.
3. In the Service account name field, enter a name. The console automatically fills in the **`Service account ID`** field based on this name.
4. In the Service account description field, enter a description.
5. Click **Create**.
6. The Service account permissions section appears. Click on **Continue**.
7. Click on **Done** to finish creating the service account.
8. Click on the newly created service account to view its details.
9. On the service account **KEYS** page, click on **Add Key, and select JSON**.

### To delegate domain-wide authority to the service account:
1. Sign in to your Google Workspace admin account.
2. Go to the **Admin console**. 
3. Go to **Security > Access and data control > API controls**.
4. In the **Domain-wide delegation** pane, select Manage Domain-Wide Delegation.
5. Click on Add new.
6. In the Client ID field, enter the **service account's client ID**.
7. In the OAuth Scopes field, enter the required OAuth scopes  (https://www.googleapis.com/auth/admin.directory.user, https://www.googleapis.com/auth/contacts) 
    Click on Authorize.
![](https://hackmd.io/_uploads/HJNbHFWUh.png =400x200)
![](https://hackmd.io/_uploads/By_HStZU2.png =300x200)


## Run Script
在專案根目錄中執行`app.py`則全部匯入
```python=
python app.py
```

執行`app_test.py`則可選擇測試人數
Ex:當輸入提示"1"則將Directory成員全部寫入至第一位成員的Contacts中
```python=
python app_test.py
```

---
## Explanation of the code
1. 先透過Admin管理員資格得到Diectory名單

 ```python
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
```
2. 得到當前用戶的Contacts內容
* ` user_creds`: 得到當前用戶憑證資格做更新
* `contact_list`: 當前用戶的Contacts清單
* `contact_emails`: 只提取e-mail部分做比對，沒寫入的就補寫，過時的名單之後做刪除
```python
            # Delegating authority to the service account to impersonate the current user
            user_creds = creds.with_subject(user['primaryEmail'])
            service = build('people', 'v1', credentials=user_creds)

            # Get the user's contact list
            connections = service.people().connections().list(resourceName='people/me',\
                 personFields='names,emailAddresses,occupations,organizations,phoneNumbers').execute()
            contact_list = connections.get('connections', [])

            # Get the email addresses of all contacts
            contact_emails = [contact.get('emailAddresses', [{}])[0].get('value') for contact in contact_list]

```

 

3. 是否該寫入的辨別機制

* `user['primaryEmail']` 是Directory中的成員，`contact['primaryEmail']`是Contacts中的成員，2者比對後還沒寫入的就利用`contact_info`搜集好資訊
透過`service.people().createContact(body=contact_info).execute()`寫入到Contacts中

* `for attempt in range(5):` 預防寫入時發生問題，可能為寫入頻率受限或是Google Server端問題，若寫入失敗最多嘗試5次，失敗就跳過log記錄起來

```python
            # For each other user
            for contact in users:
                if contact['primaryEmail'] != user['primaryEmail']:
                    # Prepare contact info
                    contact_info = {
                        'names': [{'givenName': contact['name']['fullName']}],
                        'emailAddresses': [{'value': contact['primaryEmail']}],
                    }
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
```


4. 刪除(更新)Contacts成員的機制

* `u['primaryEmail']` Directory中已經沒有此成員，而Contacts還有，就要刪除成員避免成為幽靈聯絡人
* 透過
`service.people().deleteContact(resourceName=contact['resourceName']).execute()`  People API刪除
```python
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
```
