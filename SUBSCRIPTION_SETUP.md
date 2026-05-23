# Subscription System Setup Guide (Apple & Google IAP)

To make the subscription feature work in production, you must configure your Apple and Google developer accounts and link them to your backend.

---

## 1. Apple App Store Setup

### A. App Store Connect API Key
1.  Go to [App Store Connect](https://appstoreconnect.apple.com/) > **Users and Access** > **Integrations** > **App Store Server API**.
2.  Generate a new API Key. You will get:
    *   **Issuer ID:** (e.g., `57246542-96fe-1a63-e053-0824d011072a`)
    *   **Key ID:** (e.g., `ABCDEFGHIJ`)
    *   **Private Key (.p8 file):** Download this. Copy the text inside and paste it into your `.env`.
3.  **Bundle ID:** Your app's unique ID (e.g., `com.yourapp.bundle`).

### B. Webhook (Server Notifications V2)
1.  Go to **App Store Connect** > **Apps** > (Your App) > **App Information**.
2.  Scroll to **App Store Server Notifications**.
3.  Set the **Production Server URL** and **Sandbox Server URL** to:
    `https://your-domain.com/api/subscriptions/webhook/apple/`
4.  Ensure **Version 2 Notifications** is selected.

---

## 2. Google Play Store Setup

### A. Google Cloud Service Account
1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a **Service Account** with the role **"Android Publisher"**.
3.  Go to **Keys** > **Add Key** > **Create New Key (JSON)**.
4.  Download the JSON file. You will need to put this file on your server and set the path in your `.env`.

### B. Google Play Console Linking
1.  Go to **Google Play Console** > **API Access**.
2.  Link the Google Cloud project you just used.
3.  Ensure the Service Account has **"Financial Data"** permissions enabled.

### C. Webhook (Real-Time Developer Notifications - RTDN)
1.  Go to **Google Cloud Console** > **Pub/Sub** > **Topics**.
2.  Create a Topic named `iap-notifications`.
3.  In **Google Play Console** > **Monetization Setup**, enter this topic name.
4.  Back in **Google Cloud Console** > **Pub/Sub** > **Subscriptions**, create a "Push" subscription for that topic.
5.  Set the **Push Endpoint URL** to:
    `https://your-domain.com/api/subscriptions/webhook/google/`

---

## 3. Environment Variables (.env)

Add these to your `.env` file on the server:

```env
# APPLE
APPLE_ISSUER_ID=your_issuer_id
APPLE_KEY_ID=your_key_id
APPLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIEv... (entire key here) ...\n-----END PRIVATE KEY-----"
APPLE_BUNDLE_ID=com.your.bundle
APPLE_ENVIRONMENT=production  # Use 'sandbox' for testing

# GOOGLE
GOOGLE_PLAY_PACKAGE_NAME=com.your.package
GOOGLE_SERVICE_ACCOUNT_JSON=/path/to/your/google-key.json
```

---

## 4. How the Backend Receives Events
You asked if you need to set up webhooks: **YES.**

The webhooks are the only way your backend knows **immediately** if a user:
*   Cancels their subscription.
*   Renews their subscription (the store charges them again).
*   Requests a refund.
*   Has a payment failure.

The backend is already prepared with the endpoints:
*   `POST /api/subscriptions/webhook/apple/`
*   `POST /api/subscriptions/webhook/google/`

Once you set these URLs in the Apple/Google consoles as described above, the backend will receive "Live Events" and update the dealer's status instantly.
