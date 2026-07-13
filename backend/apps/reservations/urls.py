from django.urls import path

from backend.apps.reservations.views import (
    RentalApplicationDecisionLogView,
    RentalApplicationDetailView,
    RentalApplicationEvaluateView,
    RentalApplicationListCreateView,
    RentalCancelView,
    RentalExtendView,
    RentalListCreateView,
    RentalReturnView,
)

urlpatterns = [
    path("rentals/", RentalListCreateView.as_view(), name="rental-list-create"),
    path("rentals/<int:pk>/cancel/", RentalCancelView.as_view(), name="rental-cancel"),
    path("rentals/<int:pk>/return/", RentalReturnView.as_view(), name="rental-return"),
    path("rentals/<int:pk>/extend/", RentalExtendView.as_view(), name="rental-extend"),
    path(
        "rental-applications/",
        RentalApplicationListCreateView.as_view(),
        name="rental-application-list",
    ),
    path(
        "rental-applications/<int:pk>/",
        RentalApplicationDetailView.as_view(),
        name="rental-application-detail",
    ),
    path(
        "rental-applications/<int:pk>/evaluate/",
        RentalApplicationEvaluateView.as_view(),
        name="rental-application-evaluate",
    ),
    path(
        "rental-applications/<int:pk>/decisions/",
        RentalApplicationDecisionLogView.as_view(),
        name="rental-application-decisions",
    ),
]