from django.apps import AppConfig


class TendersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tenders"
    verbose_name = "Tenders"
    
    if __name__ == "__main__":
        app.run(host="0.0.0.0", debug=True)