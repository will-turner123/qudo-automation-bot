import json
import requests
import random
from datetime import datetime, timedelta
import time
import os
import regex as re

use_proxy = False

global_liked = []
use_global_liked = False
do_log_requests = False

class Account:
    def __init__(self, objectId="", username="", password="", session_token="", **kwargs):
        self.objectId = objectId
        self.username = username
        self.password = password
        self.requests_sent = 0
        self.session_token = session_token
        self.liked = []
        self.banned = False
        self.extra_data = kwargs
        self.profiled = False

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

    def to_dict(self):
        # turn all attributes into dictionary
        return {
            "objectId": self.objectId,
            "username": self.username,
            "password": self.password,
            "http_proxy": self.http_proxy,
            "requests_sent": self.requests_sent,
            "liked": self.liked,
            "banned": self.banned,
            "extra_data": self.extra_data,
            "profiled": self.profiled,
        }

    def save_to_file(self):
        path = os.path.join(os.path.dirname(__file__), f"accounts/{self.session_token}.json")
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def load_from_file(cls, file_name):
        path = os.path.join(os.path.dirname(__file__), f"accounts/{file_name}")
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)

    def get_or_set_proxy(self):
        if not use_proxy:
            return False
        if self.http_proxy:
            return self.http_proxy
        else:
            proxy_file = os.path.join(os.path.dirname(__file__), "proxies.txt")
            with open(proxy_file, 'r') as f:
                proxies = f.readlines()
            return proxies[0].strip() # Returns the first proxy in the list


class AccountManager:
    def __init__(self):
        self.accounts = []

    def load_all_accounts(self):
        # Load all accounts from file
        acc_path = os.path.join(os.path.dirname(__file__), "accounts")
        for file_name in os.listdir(acc_path):
            if file_name.endswith(".json"):
                self.accounts.append(Account.load_from_file(file_name=file_name))
                print(f'Loaded account from {file_name}')

    @staticmethod
    def load_account(objectId):
        return Account.load_from_file(objectId)
    
class AddRequest():
    def __init__(self, object_id, sender_object_id):
        self.object_id = object_id
        self.sender_object_id = sender_object_id


class Session:
    def __init__(self, session_token=None):
        self.account = Account(
            session_token=session_token
        )
        # Set up http session with proxies and headers...
        # self.proxy = account.get_or_set_proxy()

        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "*/*",
            "X-Parse-Application-Id": "95994238-7e17-41c7-b404-5d054fb5ce71",
            "X-Parse-Client-Key": "6AC7E91A-0729-4F45-960E-055E96487F9D",
            "X-Parse-Installation-Id": "7dbd67f1-062e-4917-80dd-aececb280a10",#"9de29e41-bf5d-4f29-9e17-54d7675bbc54",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Parse-OS-Version": "15.6.1 (19G82)",
            "Accept-Encoding": "gzip, deflate, br",
            "X-Parse-Client-Version": "i1.19.3",
            "User-Agent": "Qudo/8 CFNetwork/1335.0.3 Darwin/21.6.0",
            "Connection": "keep-alive",
            "X-Parse-App-Build-Version": "8",
            "X-Parse-App-Display-Version": "1.3",
            "X-Parse-Session-Token": session_token,
        }

        self.session = requests.Session()
        # self.proxy = "http://customer-willproxy:Vanilla123@us-pr.oxylabs.io:10001"
        self.proxy = False
        if self.proxy:
            print(f'Using proxy {self.proxy}')
            self.session.proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
        else:
            print(f'Not setting proxy for now')

        self.rate_limit_remaining = "300"
        self.rate_limit_reset = "0"

        self.to_like = []
        self.pending_requests = []

        self.requests_accepted = 0


    def login(self):
        url = "https://api.qudo-app.com/parse/login"
        
        data = {
            "_method": "GET",
            "username": self.account.username,
            "password": self.account.password
        }
        
        print(f'Logging in with {self.account.username}:{self.account.password}')       
        response = self.session.post(url, headers=self.headers, json=data)
        
        self.process_response(url, data, response)

        response_data = response.json()

        print(f'We have logged in. We are updating our liked users')
        self.account.liked = response_data["liked"]
        try:
            self.account.balance_object_id = response_data["balance"]["objectId"]
        except:
            pass
        self.headers["X-Parse-Session-Token"] = response_data["sessionToken"]
        self.headers.update({"X-Parse-Session-Token": response_data["sessionToken"]})

        print(f'We logged in with session token {response_data["sessionToken"]}')
        time.sleep(1)


    def test_proxy(self):
        url = "http://httpbin.org/ip"
        response = self.session.get(url)
        self.process_response(url, {}, response)

    def append_output(self, output):
        output_file_path = os.path.join(os.path.dirname(__file__), "output.txt")
        with open(output_file_path, 'a') as f:
            f.write(output + '\n')

    def process_response(self, url, data_sent, response, headers_sent=None):
        if do_log_requests:
            self.log_response(url, data_sent, response, headers_sent=headers_sent)

        # Attempt to capture rate limits and other useful data from response
        if "Ratelimit-Remaining" in response.headers:
            print(f"Rate Limit Remaining: {response.headers['Ratelimit-Remaining']}")        
            self.rate_limit_remaining = response.headers['Ratelimit-Remaining']
        if "Ratelimit-Reset" in response.headers:
            print(f"Rate Limit Reset: {response.headers['Ratelimit-Reset']}")
            self.rate_limit_reset = response.headers['Ratelimit-Reset']
        
        if response.status_code == 500:
            print(f'Looks like we got banned. Stopping the script')
            self.account.banned = True
    
    def log_response(self, url, data_sent, response, headers_sent=None):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        output = f"{timestamp}\n"
        output += f"URL: {url}\n"
        output += str(response.status_code) + "\n"
        output += f"Data Sent: {json.dumps(data_sent, indent=4)}\n"
        if headers_sent:
            output += f"Headers Sent: {json.dumps(dict(headers_sent), indent=4)}\n"
        output += f"Response Headers: {json.dumps(dict(response.headers), indent=4)}\n"
        try:
            output += f"Response Data: {json.dumps(response.json(), indent=4)}\n"
        except:
            output += f"Response Data: {response.text}\n"
        output += "-"*50 + "\n"
        self.append_output(output)

    def set_snapchat_username(self, username):
        url = f"https://api.qudo-app.com/parse/classes/_User/{self.account.objectId}"
        data = {
            "SCUserName": username
        }
        response = self.session.put(url, headers=self.headers, json=data)
        self.process_response(url, data, response)
        print(f'Set snapchat username to {username}')
    
    def get_users(self, limit=16):
        url = "https://api.qudo-app.com/parse/classes/_User"
        
        data = {
            "limit": str(limit),
            "order": "-featuredAt",
            "_method": "GET",
            "where": {
                "gender": 1,
                "featuredAt": {
                    "$lt": {
                        "__type": "Date",
                        #"iso": "2023-09-14T01:13:44.771Z"
                        "iso": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.771Z")
                    }
                },
                "objectId": {
                    "$nin": [self.account.objectId]
                },
                "age": {
                    "$lte": 80,
                    "$gte": 18
                },
                "status": 2,
                "hidden": {
                    "$ne": True
                }
            }
        }
        print(f'Searching for users...')
        response = self.session.post(url, headers=self.headers, json=data)
        self.process_response(url, data, response)

        results = response.json()["results"]

        print(f'Found {len(results)} users')
        for user in results:
            if user["objectId"] not in self.account.liked:
                self.to_like.append(user["objectId"])
        print(f'Found {len(self.to_like)} users to like')
    
    def send_add_request_request(self, other_user_object_id):
        url = 'https://api.qudo-app.com/parse/classes/Request'

        data = {
            "receiver": {
                "__type": "Pointer",
                "className": "_User",
                "objectId": other_user_object_id,
            },
            "version": "1.3",
            "accepted": False,
            "sender": {
                "__type": "Pointer",
                "className": "_User",
                "objectId": self.account.objectId,
            },
            "ACL": {
                "*": {
                    "read": True
                },
                self.account.objectId: {
                    "write": True
                },
                other_user_object_id: {
                    "write": True
                },
            },
        }

        print(f'Sending add request to {other_user_object_id}')

        response = self.session.post(url, headers=self.headers, json=data)
        self.process_response(url, data, response)
        if response.status_code == 201:
            print(f'Got 201 response. Our balance is probably out')
            self.account.banned = True

    def update_user_data_with_like(self, other_user_object_id):
        self.account.liked.append(other_user_object_id)
        global_liked.append(other_user_object_id)
        self.account.requests_sent += 1
        
        url = f'https://api.qudo-app.com/parse/classes/_User/{self.account.objectId}'
        data = {"liked": self.account.liked}

        print(f'Making request to update account data with like...')
        response = self.session.put(url, headers=self.headers, json=data)

        self.account.save_to_file()
        self.process_response(url, data, response)
    
    def claim_daily_reward(self):
        url = "https://api.qudo-app.com/parse/functions/claimDailyReward"
        data = {}
        response = self.session.post(url, headers=self.headers, json=data)
        self.process_response(url, data, response)
        print(f'Claimed daily reward')

    def put_balance(self, balance=1000):
        url = f"https://api.qudo-app.com/parse/classes/Balance/{self.account.balance_object_id}"
        data = {
            "stars": balance
        }
        response = self.session.put(url, headers=self.headers, json=data)
        self.process_response(url, data, response)
        print(f'Put balance')

    def send_add_request(self, other_user_object_id):
        if other_user_object_id in self.account.liked:
            print(f'We have already liked {other_user_object_id}')
            return False
        if use_global_liked:
            if other_user_object_id in global_liked:
                print(f'We have already liked {other_user_object_id}')
                return False
        self.send_add_request_request(other_user_object_id)
        time.sleep(2)
        self.update_user_data_with_like(other_user_object_id)

        print(f'Sent message to {other_user_object_id} and updated account data')
        print(f'We have sent {self.account.requests_sent} requests so far')
        try:
            self.to_like.remove(other_user_object_id)
        except: 
            pass
        return True

    def set_profile_image(self):
        url = "https://api.qudo-app.com/parse/files/profileImage.jpg"
        img_path = os.path.join(os.path.dirname(__file__), "profileImage.jpg")
        print(f'Uploading profile image... {img_path}')
        hdrs = self.headers.copy()
        hdrs['Content-Type'] = 'application/octet-stream'
        with open(img_path, 'rb') as f:
            response = self.session.post(url, headers=hdrs, data=f)

        self.process_response(url, {}, response, headers_sent=hdrs)

        self.account.img_data = response.json()
        # self.account.

    def log_requests_accepted(self, objectId):
        now = datetime.now()
        csv_str = f'{now.strftime("%Y-%m-%d %H:%M:%S")},{objectId},{self.account.SCUserName},{self.account.objectId}'
        file_path = os.path.join(os.path.dirname(__file__), "accepted.csv")
        with open(file_path, 'a') as f:
            f.write(csv_str + '\n')

    def get_requests(self):
        # This query gets all requests that have been accepted by us, or have not been accepted or declined by us
        url = "https://api.qudo-app.com/parse/classes/Request"
        data = {
            "limit": "200", # default 10
            "include": "receiver,sender",
            "order": "-d",
            "_method": "GET",
            "where": {
                "$or": [
                    {
                        "accepted": True,
                        "sender": {
                            "__type": "Pointer",
                            "className": "_User",
                            "objectId": self.account.objectId
                        }
                    },
                    {
                        "declined": {"$ne": True},
                        "accepted": {"$ne": True},
                        "receiver": {
                            "__type": "Pointer",
                            "className": "_User",
                            "objectId": self.account.objectId
                        }
                    }
                ]
            }
        }

        response = self.session.post(url, headers=self.headers, json=data)
        self.process_response(url, data, response)

        pending_requests = []

        print(f'Got {len(response.json()["results"])} requests')
        for request in response.json()["results"]:
            if request["accepted"]:
                print(f'Got accepted request from {request["sender"]["objectId"]}')
            else:
                try:
                    print(f'Got a pending request')
                    if request["receiver"]["objectId"] == self.account.objectId:
                        if not request.get("sender"):
                            if request.get('senderReceiver'):
                                for user in request['senderReceiver']:
                                    if user['objectId'] != self.account.objectId:
                                        pending_request = AddRequest(
                                            object_id=request["objectId"],
                                            sender_object_id=user['objectId'],
                                        )
                                        pending_requests.append(pending_request)
                                else:
                                    print(f'Well, heres a condition I havent thought of.')
                                    print(f'I should revisit this and set log requests to True and then see what caused this')
                        else:
                            pending_request = AddRequest(
                                object_id=request["objectId"],
                                sender_object_id=request["sender"]["objectId"],
                            )
                            pending_requests.append(pending_request)

                except KeyError as e: 
                    print(f'I think we have encountered an edge case where we have sent a request to ourself')
                    print(f'This only happened cuz I was messing around with their API')
                    print(f'Exception: {e}')
                    print('\n'*5)
        self.pending_requests = pending_requests

        return pending_requests

    def accept_request(self, pending_request: AddRequest):
        url = f"https://api.qudo-app.com/parse/classes/Request/{pending_request.object_id}"
        data = {
            "acceptedAt": {
                "__type": "Date",
                "iso": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.771Z")
            },
            "accepted": True,
            }
        
        response = self.session.put(url, headers=self.headers, json=data)
        self.process_response(url, data, response)
        print(f'Accepted request from {pending_request.sender_object_id}')
        print(f'Updating account data...')

        time.sleep(2)
        self.pending_requests.remove(pending_request)
        print(len(self.account.liked))
        self.account.liked.append(pending_request.sender_object_id)
        print(f'We have accepted a request from {pending_request.sender_object_id} as {self.account.objectId} ({self.account.displayName})')
        print(f'Updating account data...', len(self.account.liked))
       
        url = f'https://api.qudo-app.com/parse/classes/_User/{self.account.objectId}'
        data = {"liked": self.account.liked}
        r = self.session.put(url, headers=self.headers, json=data)
        self.process_response(url, data, r)
       
        print(f'Updated account data')
        self.log_requests_accepted(pending_request.sender_object_id)
       
        time.sleep(2)

    def get_account_data(self):
        url = f"https://api.qudo-app.com/parse/users/me"
        response = self.session.get(url, headers=self.headers)
        self.process_response(url, {}, response, headers_sent=self.headers)
        print(f'Got account data')

        self.account = Account(
            session_token=response.json()["sessionToken"],
            objectId=response.json()["objectId"],
        )

        self.liked = response.json()["liked"]
        for like in self.liked:
            global_liked.append(like)
        self.objectId = response.json()["objectId"]
        self.account.objectId = response.json()["objectId"]
        self.account.liked = response.json()["liked"]
        self.account.SCUserName = response.json()["SCUserName"]
        self.account.displayName = response.json()["displayName"]
        
    def get_and_accept_all_requests(self):
        pending_requests = self.get_requests()
        print(f'Got {len(pending_requests)} pending requests')
        time.sleep(5)
        already_liked_counter = 0
        for pending_request in self.pending_requests:
            if use_global_liked:
                if pending_request.sender_object_id in global_liked:
                    already_liked_counter += 1
                    print(f'We have already liked {pending_request.sender_object_id} [{already_liked_counter}/100]')
                    continue
            print(f'Accepting request from {pending_request.sender_object_id}')
            self.accept_request(pending_request)
            self.requests_accepted += 1
            global_liked.append(pending_request.sender_object_id)

            print(f'Accepted {self.requests_accepted} requests so far')

            time.sleep(3)

    def profile_account(self, debug=False):
        if not self.account.profiled:

            time.sleep(1)
            self.create_installation()
            time.sleep(3)
            if debug is False:
                self.set_profile_image()
            img = self.account.img_data
            self.account.profiled = True

            time.sleep(5)

            url = f"https://api.qudo-app.com/parse/classes/_User/{self.account.objectId}"
            data = {
                "about": "yomama",
                "age": 18,
                "displayName": "urmom",
                "filterMaxAge": 99,
                "filterMinAge": 18,
                "firstPhotoFile": {
                    "__type": "File",
                    "name": img["name"],
                    "url": img["url"]
                },
                "gender": 2,
                "prefGender": 3,
                "SCUserName": "dsiajidosa",
                "status": 1,
                "version": "1.3",
            }
            # print(f'our X-Parse-Session-Token is {self.session.headers["X-Parse-Session-Token"]}')
            response = self.session.put(url, headers=self.headers, json=data)
            self.process_response(url, data, response, headers_sent=self.headers)


            self.account.save_to_file()
            print(f'Profiled account')
    
    def query_other_user(self, other_user_object_id):
        url = f"https://api.qudo-app.com/parse/classes/_User/{other_user_object_id}"

    def log_in_with_session_token(self, session_token=""):
        # Upon first login, we get a session token which is only killed we hit their logout endpoint I BELIEVE
        if not session_token:
            if self.account.session_token:
                session_token = self.account.session_token
            else:
                print(f'No session token provided')
                raise Exception("No session token provided")
        
        self.headers["X-Parse-Session-Token"] = session_token
        print(f'Set session token')

    def create_installation(self):
        url = f"https://api.qudo-app.com/parse/classes/_Installation/{self.account.objectId}"
        time.sleep(1)

        data = {
            "badge": 12,
            "user": {
                "__type": "Pointer",
                "className": "_User",
                "objectId": self.account.objectId
            }
        }
        response = self.session.put(url, headers=self.headers, json=data)
        self.process_response(url, data, response)
        print(f'Created installation')

    def set_featured_at(self):
        url = f"https://api.qudo-app.com/parse/classes/_User/{self.account.objectId}"
        data = {
            "featuredAt": {
                "__type": "Date",
                "iso": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.771Z")
            }
        }
        response = self.session.put(url, headers=self.headers, json=data)
        self.process_response(url, data, response)
        print(f'Set featured at')


    def register_account(self):
        register_session = requests.Session()
        register_session.headers = {
            "X-Client-Version": "iOS/FirebaseSDK/8.15.0/FirebaseUI-iOS",
            "X-Firebase-Client": "apple-platform/ios apple-sdk/19C51 appstore/true deploy/cocoapods device/iPhone14,5 fire-analytics/8.15.0 fire-auth/8.15.0 fire-fcm/8.15.0 fire-install/8.15.0 fire-ios/8.15.0 os-version/15.6.1 xcode/13C90",
            "X-Firebase-Client-Log-Type": "3",
            "X-Ios-Bundle-Identifier": "com.fritjofdittner.amos",
            "Accept-Language": "en",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "*/*",
            "X-Firebase-GMPID": "1:536220320702:ios:5ccbf5eff30de2dc98efef",
        }
        register_session.proxies = {
            'http': self.proxy,
            'https': self.proxy
        }
#         data = {"appToken": "66BE141E2DCF1C3C687FB39F9A5BCD9591BD2A897DF3C6E5F037A9A8984D1BB6"}
#         url = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyClient?key=AIzaSyBa705Jq7mm89qQHM7xExiNGFOKCnQt1tg"
#         response = register_session.post(url, headers=register_session.headers, json=data)
        
#         self.process_response(url, data, response, headers_sent=register_session.headers)

#         receipt = response.json()["receipt"]

#         time.sleep(1)

#         # now we do smspva stuff
#         smspva_api_key = "Hi0yRdjSqg2ceZY9zaXxdqI0n8nFSP"
#         sms = smsPvaAPI(smspva_api_key)
#         bal = sms.get_balance("vk")
#         print(f'Balance: ${bal["balance"]}')
#         service_code = "opt19"
#         country_code = "UK" # US, UK, RU, CN, etc
#         country_mappings = {
#             "UK": "+44",
#             "US": "+1",
#             "DE": "+49",
#         }
# #        number = sms.get_number(country_code, service_code)
#         number = {"number": "7443962511", "id": "test"}
#         print(f'Got number: {number["number"]}')
#         sms_id = number["id"]


#         url = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/sendVerificationCode?key=AIzaSyBa705Jq7mm89qQHM7xExiNGFOKCnQt1tg"

#         formatted_num = f"{country_mappings[country_code]}{number['number']}"
#         print(f'Formatted number: {formatted_num}')
#         data = {
#             "iosReceipt": receipt,
#             "iosSecret": "qT1E0wdXuzE1i1cd",
#             "phoneNumber": f"{country_mappings[country_code]}{number['number']}",
#         }

#         register_session.headers['User-Agent'] = 'FirebaseAuth.iOS/8.15.0 com.fritjofdittner.amos/1.3 iPhone/15.6.1 hw/iPhone14_5'

#         response = register_session.post(url, headers=register_session.headers, json=data)
#         self.process_response(url, data, response, headers_sent=register_session.headers)


#         session_info = response.json()["sessionInfo"]

#         timeout = 600
#         code = None
#         while timeout > 0:
#             sms_code = sms.get_sms(country_code, service_code, number["id"])
#             if sms_code["sms"] is not None:
#                 # set code to a regex match that gets just numeric characters
#                 code = re.search(r'\d+', sms_code["sms"]).group()
#                 print(f'Got sms code: {sms_code}')
#                 break
#             print(f'Waiting for sms code...')

#             time.sleep(5)
#             timeout -= 5
#         if code is None:
#             print(f'sms timed out. giving up.')
#             return
        
#         url = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPhoneNumber?key=AIzaSyB-705Jq7mm89qQHM7xExiNGFOKCnQt1tg"
#         data = {
#             "sessionInfo": session_info,
#             "code": code,
#             "operation": "SIGN_UP_OR_IN"
#         }

#         response = register_session.post(url, headers=register_session.headers, json=data)
#         self.process_response(url, data, response)

#         id_token = response.json()["idToken"]
#         local_id = response.json()["localId"]
#         refresh_token = response.json()["refreshToken"]

#         time.sleep(1)

#         url = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/getAccountInfo?key=AIzaSyBa705Jq7mm89qQHM7xExiNGFOKCnQt1tg"
#         data = {
#             "idToken": id_token
#         }

#         response = register_session.post(url, headers=register_session.headers, json=data)
#         self.process_response(url, data, response)

#         user_id = response.json()["users"][0]["localId"]
        url = "https://api.qudo-app.com/parse/users"
        random_password = ''.join([random.choice('0123456789ABCDEF') for i in range(32)])

        # set user id to random 10 letter string
        user_id = ''.join([random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz') for i in range(10)])

        data = {
           # "photos": ["https://qudo-images.s3.amazonaws.com/d519e7195b4620cee6a5bfe6e01648f6_profileImage.jpg"],
          #  "firstImageURL": "https://qudo-images.s3.amazonaws.com/d519e7195b4620cee6a5bfe6e01648f6_profileImage.jpg",
            "password": random_password,
            "firebaseUID": user_id,
            "verified": False, 
            "username": user_id,
            "liked":[],
            "disliked": [],
            "photos": [],
            #"KKID": "26BFF1B4-7FC0-4691-B032-BB8AE4C5620C",
            # random uuid string
            "KKID": ''.join([random.choice('0123456789ABCDEF') for i in range(32)]),
        }

        new_headers = {
            "Accept": "*/*",
            "X-Parse-Application-Id": "95994238-7e17-41c7-b404-5d054fb5ce71",
            "X-Parse-Client-Key": "6AC7E91A-0729-4F45-960E-055E96487F9D",
            "X-Parse-Installation-Id": "7dbd67f1-062e-4917-80dd-aececb280a10",#"9de29e41-bf5d-4f29-9e17-54d7675bbc54",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Parse-OS-Version": "15.6.1 (19G82)",
            "Accept-Encoding": "gzip, deflate, br",
            "X-Parse-Client-Version": "i1.19.3",
        }

        time.sleep(1)

        response = register_session.post(url, headers=new_headers, json=data)

        self.process_response(url, data, response, headers_sent=new_headers)

        session_token = response.json()["sessionToken"]
        self.headers["X-Parse-Session-Token"] = session_token

        acc = Account(
            objectId=user_id,
            username=user_id,
            password=random_password,
            http_proxy=self.proxy,
        )

        acc.save_to_file()

        time.sleep(5)

def pretty_time(bracks=True):
    now = datetime.now()
    if bracks:
        return f'[{now.strftime("%Y-%m-%d %H:%M:%S")}]'
    else:
        return now.strftime("%Y-%m-%d %H:%M:%S")



session_tokens = [
    "",
]
sessions = []

for session_token in session_tokens:
    session = Session(session_token=session_token)
#    session.log_in_with_session_token(session_token)

    session.get_account_data()
    sessions.append(session)
    time.sleep(4)

while True:
    for session in sessions:
        try:
            print(f'{pretty_time()} Setting featured at... (session {session.account.displayName}))')
            session.set_featured_at()
            time.sleep(5)
            print(f'{pretty_time()} Getting requests for {session.account.objectId} ({session.account.displayName}))')
            session.get_and_accept_all_requests()
            time.sleep(2)
        except Exception as e:
            print(f'Got an error: {e}')
            retries = 3 
            for retry in range(retries):
                print(f'Retrying ({retry + 1}/{retries})...')
                try:
                    session.get_account_data()
                    break
                except Exception as e:
                    print(f'Retry failed: {e}')
                time.sleep(5)
            else:
                print(f'Exceeded maximum retries for session {session.account.displayName}')
        time.sleep(60)