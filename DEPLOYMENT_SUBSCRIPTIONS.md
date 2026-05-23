# Production Subscription Setup Guide (RevenueCat)

This document details the final steps to connect your Django backend with RevenueCat for a unified subscription system.

---

## 1. RevenueCat Configuration

1.  **Create Project:** Go to the [RevenueCat Dashboard](https://app.revenuecat.com/) and create a new project.
2.  **Add Apps:** Add your iOS and Android apps to the project.
3.  **Products & Offerings:** Configure your products (matching the `apple_product_id` and `google_product_id` in your Django `SubscriptionPackage` model).

---

## 2. Webhook Setup (Crucial)

This is how RevenueCat tells your backend about purchases, renewals, and cancellations.

1.  **URL:** In the RevenueCat Dashboard, go to **Project Settings** > **Webhooks**.
2.  **Add Webhook:**
    *   **URL:** `https://your-api-domain.com/api/subscriptions/webhook/revenuecat/`
    *   **Authorization Token:** Generate a random string (e.g., `rc_secret_123`) and save it.
3.  **Backend Config:** Add this token to your `.env` as `REVENUECAT_WEBHOOK_AUTH_TOKEN`.

---

## 3. Environment Variables Summary (.env)

```env
# --- RevenueCat ---
REVENUECAT_WEBHOOK_AUTH_TOKEN="your_generated_token"

# --- Stores (Required by RevenueCat, but backend only needs these for optional fallback) ---
APPLE_BUNDLE_ID="com.your.app"
GOOGLE_PLAY_PACKAGE_NAME="com.your.app"
```

---

## 4. Verification Flow

1.  **Flutter App:** Uses the RevenueCat SDK to make a purchase.
2.  **RevenueCat:** Verifies the purchase directly with Apple/Google.
3.  **Webhook:** RevenueCat sends a unified event to your Django backend.
4.  **Backend:** The backend extracts the `app_user_id` (which should be the Django User ID) and updates the `DealerSubscription` record.
