# Tender, TenderWatch, AlertPreference, and AlertLog are MongoEngine
# documents, not Django ORM models, so they cannot be registered with
# django.contrib.admin directly (it expects models.Model subclasses backed
# by a relational table).
#
# Instead, Tender Trail ships its own "admin-style" dashboard at "/" built
# with regular Django views + templates (see tenders/views.py) which covers
# search, filtering, CRUD-via-API, and analytics for the Mongo-backed data.
#
# The Django admin at /admin/ remains available for managing the relational
# side of the app: auth Users, Groups, and sessions.
from .models import Tender, TenderWatch, AlertPreference, AlertLog
from django.contrib import admin
#admin.site.register(Tender)