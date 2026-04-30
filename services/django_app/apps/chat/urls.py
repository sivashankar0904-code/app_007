from django.urls import path
from .views import BotMessageView, ShareMessageView

app_name = "chat"

urlpatterns = [
    # Internal — called by FastAPI after AI generates a response
    path("bot-message/", BotMessageView.as_view(), name="bot-message"),
    # Frontend — called when user clicks "Share" on a private bot reply
    path("share-message/", ShareMessageView.as_view(), name="share-message"),
]
