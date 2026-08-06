from django.urls import path

from backend.apps.ai.views import AIActionConfirmView, AIConsultantView

urlpatterns = [
    path("ai/consult/", AIConsultantView.as_view(), name="ai-consult"),
    path("ai/actions/<uuid:pk>/confirm/", AIActionConfirmView.as_view(), name="ai-action-confirm"),
]
