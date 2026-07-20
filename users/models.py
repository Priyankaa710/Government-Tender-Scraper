# Tender Trail uses Django's built-in auth.User for accounts/sessions/JWT.
# Per-user domain data (watchlists, alert preferences) lives in MongoDB —
# see tenders.models.TenderWatch / AlertPreference, keyed by user_id.
