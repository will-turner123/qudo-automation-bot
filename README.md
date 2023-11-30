# Qudo Automation Bot

Qudo Automation Bot is a script designed to interact with the Qudo platform, an "add-me" site for finding friends on Snapchat. The Qudo platform is built using Parse on the backend but has identified bugs that can be exploited, as demonstrated by this script.

## Exploiting Qudo Bugs
One notable bug involves the Parse backend, which allows users to update their own attributes. Specifically, when a user is initially created on Qudo, a "featuredAt" attribute is set to the time of registration. The front page of the platform sorts users in descending order based on when they were last featured at. Exploiting the Parse API, this script showcases how one can manipulate the "featuredAt" attribute at will, ensuring a user's constant visibility at the top of the front page.

## Script Functionality
This script manages accounts using session tokens. Qudo/Parse's session tokens remain unchanged unless a user manually logs out, effectively creating static user/password combinations. By populating the session_tokens list with desired tokens, the script periodically sets the associated accounts to featured status and accepts all incoming friend requests on the Qudo app.

## Exploitation Potential
These identified bugs in the Qudo platform could be exploited to generate substantial traffic to a Snapchat account. By consistently featuring an account at the top of the front page and automatically accepting friend requests, this script could be used to increase visibility and engagement on Snapchat.

## Disclaimer

Please note that exploiting platform vulnerabilities may violate terms of service and ethical considerations. Use this script responsibly and ensure compliance with Qudo's terms and conditions. Unauthorized exploitation of vulnerabilities may result in consequences, including the suspension or termination of accounts.