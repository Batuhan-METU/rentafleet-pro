from django.urls import path

from backend.apps.rentals.views import (
    RentalCancelView,
    RentalExportView,
    RentalExtendView,
    RentalListCreateView,
    RentalReturnView,
)

urlpatterns = [
    path("rentals/", RentalListCreateView.as_view(), name="rental-list-create"),
    path("rentals/export/", RentalExportView.as_view(), name="rental-export"),
    path("rentals/<int:pk>/cancel/", RentalCancelView.as_view(), name="rental-cancel"),
    path("rentals/<int:pk>/return/", RentalReturnView.as_view(), name="rental-return"),
    path("rentals/<int:pk>/extend/", RentalExtendView.as_view(), name="rental-extend"),
]
