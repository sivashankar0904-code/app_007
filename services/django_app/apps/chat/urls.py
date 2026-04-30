from django.urls import path
from .views import BotMessageView

app_name = "chat"

urlpatterns = [
    # Internal only — called by FastAPI after AI generates a summary
    path("bot-message/", BotMessageView.as_view(), name="bot-message"),
]
