# Flutter Developer Guide: RevenueCat Integration

This guide explains how to connect the Flutter `purchases_flutter` package with the Django backend.

---

## 1. SDK Initialization (Crucial)

When initializing the RevenueCat SDK, you **must** provide the Django `user_id` as the `appUserID`. This is the primary key from the backend login/profile response. This allows the backend to link store events to the correct dealer.

```dart
import 'package:purchases_flutter/purchases_flutter.dart';

// Call this after the user logs in successfully
Future<void> initPlatformState(int djangoUserId) async {
  await Purchases.setLogLevel(LogLevel.debug);

  PurchasesConfiguration configuration;
  if (Platform.isAndroid) {
    configuration = PurchasesConfiguration("goog_api_key_here");
  } else {
    configuration = PurchasesConfiguration("appl_api_key_here");
  }
  
  // Link the RevenueCat user to our Django User ID
  configuration.appUserID = djangoUserId.toString();
  
  await Purchases.configure(configuration);
}
```

---

## 2. API Endpoints

| Purpose | Method | Endpoint |
| :--- | :--- | :--- |
| **Get Packages** | `GET` | `/api/subscriptions/packages/` |
| **User Profile** | `GET` | `/api/users/profile/` |
| **RC Webhook** | `POST` | `/api/subscriptions/webhook/revenuecat/` (Handled by RC) |

---

## 3. Implementation Workflow

### Step 1: Display Packages
Fetch packages from the backend `/api/subscriptions/packages/` to show prices and descriptions.

### Step 2: Make a Purchase
Use the `purchases_flutter` SDK to handle the payment.

```dart
try {
  CustomerInfo customerInfo = await Purchases.purchasePackage(package);
  if (customerInfo.entitlements.all["premium"]?.isActive ?? false) {
    // Unlock features locally if needed
  }
} on PlatformException catch (e) {
  // Handle error
}
```

### Step 3: Server Sync (Automated)
You **do not** need to call any "verify" endpoint manually. RevenueCat will automatically send a webhook to our backend. 

### Step 4: Refresh UI
After a successful purchase, call the backend `/api/users/profile/` endpoint to get the updated subscription status.

---

## 4. Understanding the Backend Response

When you fetch the user's profile, the `subscription` object will look like this:

```json
"subscription": {
    "status": "active",
    "package_name": "Premium Monthly",
    "current_period_end": "2024-12-31T23:59:59Z",
    "is_valid": true,
    "auto_renew": true
}
```

### Important Statuses:
*   `active`: Access granted.
*   `canceled`: Access granted until `current_period_end` (User turned off auto-renew).
*   `past_due`: Access might be restricted; payment failed in store.
*   `expired`: Access restricted.

---

## 5. Testing
1.  Use **Sandbox** accounts (Apple Sandbox / Google License Testers).
2.  Set renewal periods to "Every 5 minutes" in store consoles to test the automatic backend updates.
3.  Check the **RevenueCat Webhook Debugger** to ensure events are reaching the backend.
