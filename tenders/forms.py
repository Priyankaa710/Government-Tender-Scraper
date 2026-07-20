from django import forms

from .models import CATEGORY_CHOICES, INDIAN_STATES, STATUS_CHOICES


CATEGORY_FORM_CHOICES = [("", "All categories")] + [(c, c) for c in CATEGORY_CHOICES]
STATE_FORM_CHOICES = [("", "All states")] + [(s, s) for s in INDIAN_STATES]
STATUS_FORM_CHOICES = [("", "Any status")] + [(s, s.replace("_", " ").title()) for s in STATUS_CHOICES]


class TenderFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Search title, department, reference no…"}),
    )
    category = forms.ChoiceField(choices=CATEGORY_FORM_CHOICES, required=False)
    state = forms.ChoiceField(choices=STATE_FORM_CHOICES, required=False)
    status = forms.ChoiceField(choices=STATUS_FORM_CHOICES, required=False)
    min_value = forms.FloatField(required=False, min_value=0)
    max_value = forms.FloatField(required=False, min_value=0)
    deadline_within_days = forms.IntegerField(required=False, min_value=0)
    sort = forms.ChoiceField(
        choices=[
            ("deadline", "Deadline (soonest)"),
            ("-estimated_value", "Value (highest)"),
            ("-publish_date", "Recently published"),
        ],
        required=False,
    )


class TenderWatchForm(forms.Form):
    keyword = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Keyword to watch for"}))
    category = forms.ChoiceField(choices=CATEGORY_FORM_CHOICES, required=False)
    state = forms.ChoiceField(choices=STATE_FORM_CHOICES, required=False)
    min_value = forms.FloatField(required=False, min_value=0)
    max_value = forms.FloatField(required=False, min_value=0)


class AlertPreferenceForm(forms.Form):
    email = forms.EmailField(required=False)
    enabled = forms.BooleanField(required=False)
    remind_days_before = forms.CharField(
        required=False,
        help_text="Comma-separated days before deadline, e.g. 7,3,1",
    )
    categories = forms.MultipleChoiceField(choices=[(c, c) for c in CATEGORY_CHOICES], required=False)
    states = forms.MultipleChoiceField(choices=[(s, s) for s in INDIAN_STATES], required=False)


class TenderCreateForm(forms.Form):
    """Used by the in-app 'Add Tender' page so business users can key in
    a tender manually instead of relying only on the scraper/API/CSV."""

    reference_no = forms.CharField(
        max_length=120,
        help_text="e.g. MH/PWD/2026/10234 — must be unique.",
        widget=forms.TextInput(attrs={"placeholder": "MH/PWD/2026/10234"}),
    )
    title = forms.CharField(max_length=500)
    department = forms.CharField(max_length=300)
    category = forms.ChoiceField(choices=[(c, c) for c in CATEGORY_CHOICES])
    state = forms.ChoiceField(choices=[(s, s) for s in INDIAN_STATES])
    location = forms.CharField(max_length=200, required=False)
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    estimated_value = forms.FloatField(required=False, min_value=0, initial=0)
    emd_amount = forms.FloatField(required=False, min_value=0, initial=0)
    deadline = forms.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        help_text="Bid submission deadline.",
    )
    opening_date = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    source_portal = forms.CharField(max_length=200, required=False, initial="Manual Entry")
    source_url = forms.CharField(max_length=500, required=False)

    def clean_reference_no(self):
        from .models import Tender  # local import to avoid any circular-import risk

        ref = self.cleaned_data["reference_no"].strip().upper()
        if Tender.objects.filter(reference_no=ref).first():
            raise forms.ValidationError("A tender with this reference number already exists.")
        return ref
