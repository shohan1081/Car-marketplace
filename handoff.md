# Antigravity Session Handoff Context

## Project Overview
This project is a car marketplace application called **Nory** (or **Nory Real Drive**). It consists of two main codebases:
1. **Backend**: A Django REST Framework API (`backend/Car-marketplace`).
2. **Frontend**: A Flutter Mobile App using BLoC for state management and Dio for networking (`nory_mobile_app`).

## What We Have Built So Far

### 1. Video Feed and UI
- Built a TikTok-style vertical scrolling video feed for vehicle reels.
- Implemented `_VideoPlayerWidget` in `VehicleDetailScreen` to correctly frame (`BoxFit.contain`) and autoplay vehicle videos.
- Handled dealer profile pictures falling back to a placeholder gracefully when `null`.

### 2. Messaging & Chat Integration
- **Backend**: Added a `SendMessageView` for REST-based messaging, bypassing the need for immediate WebSocket connections for simplicity and reliability.
- **Frontend**: 
  - Created `ChatRemoteSource` and injected it into `ChatRepository`.
  - Updated `ChatBloc` to fetch real message history when a conversation is opened.
  - Wired the **"Start Chat"** button on the `VehicleDetailScreen` to hit the backend, establish a conversation, and route the user directly to the active chat thread.

### 3. Financing Inquiries (Leads)
- **Backend**: Verified the `VehicleInquiryCreateView` is accepting POST requests to generate leads for dealers.
- **Frontend**:
  - Implemented a fully functional `_showInquiryBottomSheet` in the `VehicleDetailScreen`.
  - Wired the "Submit Inquiry" button to `FeedRepository.submitInquiry()`, sending real payloads (Full Name, Phone, Loan Tenure, Notes, etc.) to the Django backend.
  - Updated the **Dealer Dashboard** (`DealerRemoteSource.getInquiries()`) to fetch real leads/inquiries from the API instead of using mocked data, updating the `DealerRepository`.

### 4. Code & Architecture Standards
- **State Management**: Using `flutter_bloc` with `freezed` for immutable states and events.
- **Dependency Injection**: Using `getIt` inside `injector.dart` for Repositories, Remote Sources, and Blocs.
- **Routing**: Using `go_router`.
- **API Client**: `Dio` configured with `ApiEndpoints` mapping.

## Current State & Next Steps

All code up to this point has been committed and pushed to the respective remote repositories. The mobile app can successfully fetch feeds, view details, start chats, and submit inquiries. The dealer dashboard can fetch real leads.

**Next Immediate Tasks (from our previous task list):**
1. **Verify Chat & Inquiry flows**: Ensure that messages sent via the mobile app are properly stored in the backend and displayed on both ends.
2. **Dealer Leads Screen UI**: Ensure the UI in the Dealer Leads tab perfectly maps to the new `LeadModel` and `FinancingInquiryModel` structures fetched from the real API.
3. **WebSockets (Optional Future)**: The backend currently supports Channels/WebSockets (`consumers.py`). The frontend is currently using HTTP for messaging (`SendMessageView`). If real-time typing/delivery is needed, we will need to implement a WebSocket client in Flutter.

---
**To the new Antigravity Agent:**
Please acknowledge that you have read and understood this context, and ask the user what they would like to tackle first!
