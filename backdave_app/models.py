from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models, transaction as db_transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
import random
from django.db.models import Sum


# ----------------------------------
# USER MANAGER
# ----------------------------------
class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Phone number must be set.")
        if not password:
            raise ValueError("Password (PIN) must be set.")
        user = self.model(phone=phone, **extra_fields)
        user.set_pin(password, save=False)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(phone, password, **extra_fields)


# ----------------------------------
# USER MODEL
# ----------------------------------
class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(max_length=20, unique=True)
    full_name = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    state = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=50, blank=True, null=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    profilePic = models.ImageField(upload_to="profile_pics/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.full_name or self.phone} ({self.phone})"

    # --------------------------
    # BANK OPERATIONS
    # --------------------------
    def total_points(self):
        earned = self.transactions.filter(type="Reward Points").aggregate(Sum('points'))['points__sum'] or 0
        redeemed = self.transactions.filter(type="Reward Redemption").aggregate(Sum('points'))['points__sum'] or 0
        return earned + redeemed

    def deposit(self, amount):
        self.balance += amount
        self.save(update_fields=["balance"])
        return self.balance

    def withdraw(self, amount):
        if amount > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amount
        self.save(update_fields=["balance"])
        return self.balance

    # --------------------------
    # MOCK BANK ACCOUNT VERIFICATION
    # --------------------------
    def verify_bank_account(self, account_number: str, bank_name: str):
        if not account_number or not bank_name:
            raise ValueError("Both account_number and bank_name are required")
        fake_names = ["John Doe", "Jane Smith", "Chinedu Okafor", "Ngozi Ude"]
        return random.choice(fake_names)

    # --------------------------
    # PIN HANDLING
    # --------------------------
    def set_pin(self, raw_pin, save=True):
        self.password = make_password(raw_pin)
        if save:
            self.save(update_fields=["password"])

    def check_pin(self, raw_pin):
        return check_password(raw_pin, self.password)


# ----------------------------------
# TRANSACTION MODEL
# ----------------------------------
class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ("Deposit", "Deposit"),
        ("Withdrawal", "Withdrawal"),
        ("Transfer", "Transfer"),
        ("Add Money", "Add Money"),
        ("Data Purchase", "Data Purchase"),
        ("Airtime Purchase", "Airtime Purchase"),
        ("Bill Payment", "Bill Payment"),
        ("Betting", "Betting"),
        ("Reward Points", "Reward Points"),
        ("Reward Redemption", "Reward Redemption"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transactions")
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateTimeField(default=timezone.now)
    points = models.IntegerField(default=0)

    # Extra fields
    phone = models.CharField(max_length=20, blank=True, null=True)
    provider = models.CharField(max_length=50, blank=True, null=True)
    expiry = models.DateField(blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=50, blank=True, null=True)
    recipient = models.CharField(max_length=100, blank=True, null=True)
    planLabel = models.CharField(max_length=100, blank=True, null=True)

    # Flutterwave fields
    flw_tx_ref = models.CharField(max_length=100, blank=True, null=True, unique=True)
    flw_id = models.CharField(max_length=100, blank=True, null=True)
    flw_status = models.CharField(max_length=50, blank=True, null=True)
    flw_payment_type = models.CharField(max_length=50, blank=True, null=True)
    flw_currency = models.CharField(max_length=10, default="NGN")

    def save(self, *args, **kwargs):
        from decimal import Decimal
        with db_transaction.atomic():
            amount = Decimal(self.amount)

            # -----------------------------
            # Determine balance change
            # -----------------------------
            if self.type in ("Deposit", "Add Money"):
                new_balance = self.user.balance + amount
            elif self.type in ("Withdrawal", "Transfer", "Data Purchase", "Airtime Purchase", "Bill Payment", "Betting"):
                if amount > self.user.balance:
                    raise ValueError("Insufficient balance for this transaction")
                new_balance = self.user.balance - amount
            elif self.type == "Reward Redemption":
                new_balance = self.user.balance + amount
            elif self.type == "Reward Points":
                new_balance = self.user.balance
            else:
                new_balance = self.user.balance

            self.balance_after = new_balance
            self.user.balance = new_balance
            self.user.save(update_fields=["balance"])

            # -----------------------------
            # Auto-generate description
            # -----------------------------
            if not self.description:
                if self.type in ("Data Purchase", "Airtime Purchase"):
                    network = self.provider or "Unknown"
                    self.description = f"{self.type} of ₦{self.amount} to {self.phone} via {network}"
                    if self.planLabel:
                        self.description += f" ({self.planLabel})"
                elif self.type == "Bill Payment":
                    category = self.category or "General"
                    self.description = f"{self.type} of ₦{self.amount} to {self.recipient} ({category})"
                elif self.type == "Betting":
                    recipient = self.recipient or "Unknown"
                    self.description = f"Betting - {recipient} (₦{self.amount})"
                    if self.planLabel:
                        self.description += f" [{self.planLabel}]"
                elif self.type == "Transfer":
                    recipient = self.recipient or "Unknown"
                    self.description = f"Transfer of ₦{self.amount} to {recipient}"
                elif self.type == "Reward Redemption":
                    self.description = f"Redeemed {abs(self.points)} points for ₦{self.amount}"
                elif self.type == "Reward Points":
                    self.description = f"Earned {self.points} reward points"
                else:
                    self.description = f"{self.type} of ₦{self.amount}"

            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.type} of ₦{self.amount} for {self.user.phone} on {self.date.strftime('%Y-%m-%d %H:%M:%S')}"
