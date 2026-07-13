from django.urls import path

from backend.apps.ai.views import AIConsultantView

urlpatterns = [
    path("ai/consult/", AIConsultantView.as_view(), name="ai-consult"),
]