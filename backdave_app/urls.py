from django.urls import path
from .views import (
    # Health & Registration
    RegisterView,

    # Auth
    LoginView,
    RefreshTokenView,

    # User account
    AccountView,
    ValidatePinView,
    UpdatePinView,

    # Transactions
    TransactionView,
    TransferVerifyView,

    # Dashboard
    DashboardView,

    # Flutterwave
    flutterwave_webhook,  # function-based view
    InitFlutterwavePayment,
    FlutterwaveVerifyView,
)

urlpatterns = [
    # Health check

    # User registration & auth
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh-token/", RefreshTokenView.as_view(), name="refresh-token"),

    # Account management
    path("account/", AccountView.as_view(), name="account"),
    path("validate-pin/", ValidatePinView.as_view(), name="validate-pin"),
    path("update-pin/", UpdatePinView.as_view(), name="update-pin"),

    # Transactions
    path("transactions/", TransactionView.as_view(), name="transactions"),
    path("transfer/verify/", TransferVerifyView.as_view(), name="transfer-verify"),

    # Dashboard
    path("dashboard/", DashboardView.as_view(), name="dashboard"),

    # Flutterwave webhook
    path("flutterwave/webhook/", flutterwave_webhook, name="flutterwave-webhook"),

    path("flutterwave/init/", InitFlutterwavePayment.as_view()),
    path("flutterwave/verify/", FlutterwaveVerifyView.as_view()),
]
