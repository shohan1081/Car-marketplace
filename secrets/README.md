Service-account JSON files live here on the server. Docker mounts this
directory read-only into the Django containers at /run/secrets.

Expected files (only the ones you actually use):

  firebase.json     ->  FIREBASE_CREDENTIALS_PATH=/run/secrets/firebase.json
  google-play.json  ->  GOOGLE_SERVICE_ACCOUNT_JSON=/run/secrets/google-play.json

Nothing else in this directory is ever committed -- see .gitignore.
