"""RentA-Fleet PRO API görünüm paketi."""

from backend.views.ai import AIConsultantView, EventStreamRenderer
from backend.views.analytics import FleetAnalyticsView
from backend.views.auth import LoginView, LogoutView, MeView
from backend.views.driver import (
    DriverCreateView,
    DriverDetailView,
    DriverListView,
    DriverRentalHistoryView,
    DriverScoreView,
)
from backend.views.finance import (
    ExpenseCategoryListView,
    ExpenseDetailView,
    IncomeDetailView,
    VehicleCreateView,
    VehicleExpenseListCreateView,
    VehicleFinancialAnalysisView,
    VehicleFinancialProfileView,
    VehicleIncomeListCreateView,
    VehicleRentalQuoteView,
)
from backend.views.health import HealthCheckView
from backend.views.market import FleetCompetitorPricesView, VehicleCompetitorPriceView
from backend.views.personnel import PersonnelManagementView
from backend.views.rental import (
    RentalApplicationDecisionLogView,
    RentalApplicationDetailView,
    RentalApplicationEvaluateView,
    RentalApplicationListCreateView,
    RentalCancelView,
    RentalListCreateView,
)
from backend.views.saas import CompanyListView, CreateNewTenantView, TenantBrandingView
from backend.views.vehicle import (
    VehicleAnomalyView,
    VehicleCurrentRenterScoreView,
    VehicleFuelOptimizationView,
    VehicleListView,
    VehicleLiveStreamView,
    VehicleMaintenanceAlertView,
)

__all__ = [
    "AIConsultantView",
    "CompanyListView",
    "CreateNewTenantView",
    "DriverCreateView",
    "DriverDetailView",
    "DriverListView",
    "DriverRentalHistoryView",
    "DriverScoreView",
    "EventStreamRenderer",
    "ExpenseCategoryListView",
    "ExpenseDetailView",
    "FleetAnalyticsView",
    "FleetCompetitorPricesView",
    "HealthCheckView",
    "IncomeDetailView",
    "LoginView",
    "LogoutView",
    "MeView",
    "PersonnelManagementView",
    "RentalApplicationDecisionLogView",
    "RentalApplicationDetailView",
    "RentalApplicationEvaluateView",
    "RentalApplicationListCreateView",
    "RentalCancelView",
    "RentalListCreateView",
    "TenantBrandingView",
    "VehicleAnomalyView",
    "VehicleCompetitorPriceView",
    "VehicleCreateView",
    "VehicleCurrentRenterScoreView",
    "VehicleExpenseListCreateView",
    "VehicleFinancialAnalysisView",
    "VehicleFinancialProfileView",
    "VehicleFuelOptimizationView",
    "VehicleIncomeListCreateView",
    "VehicleListView",
    "VehicleLiveStreamView",
    "VehicleMaintenanceAlertView",
    "VehicleRentalQuoteView",
]
