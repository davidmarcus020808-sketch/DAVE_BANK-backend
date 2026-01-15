from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django import forms
from django.db.models import Sum, Count

from .models import User, Transaction


# -----------------------------
# Custom Forms
# -----------------------------
class UserCreationForm(forms.ModelForm):
    """Form for creating new users with a 4-digit PIN"""
    pin1 = forms.CharField(label="PIN", widget=forms.PasswordInput)
    pin2 = forms.CharField(label="Confirm PIN", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("phone", "full_name", "email", "dob", "state", "city")

    def clean_pin2(self):
        p1 = self.cleaned_data.get("pin1")
        p2 = self.cleaned_data.get("pin2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("PINs don't match")
        if p1 and (not p1.isdigit() or len(p1) != 4):
            raise forms.ValidationError("PIN must be exactly 4 digits")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_pin(self.cleaned_data["pin1"])  # store hashed PIN
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """Form for updating users, including editing PIN"""
    pin = forms.CharField(
        label="PIN",
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text="Enter a new 4-digit PIN to change it"
    )

    class Meta:
        model = User
        fields = "__all__"

    def clean_pin(self):
        pin = self.cleaned_data.get("pin")
        if pin:
            if not pin.isdigit() or len(pin) != 4:
                raise forms.ValidationError("PIN must be exactly 4 digits")
        return pin

    def save(self, commit=True):
        user = super().save(commit=False)
        pin = self.cleaned_data.get("pin")
        if pin:
            user.set_pin(pin)
        if commit:
            user.save()
        return user


# -----------------------------
# Transaction Inline
# -----------------------------
class TransactionInline(admin.TabularInline):
    model = Transaction
    fields = ("type", "amount", "balance_after", "description", "flw_tx_ref", "flw_status", "date")
    readonly_fields = ("balance_after", "date", "flw_tx_ref", "flw_status")
    extra = 0
    ordering = ("-date",)
    can_delete = False
    show_change_link = True


# -----------------------------
# Custom List Filters
# -----------------------------
class LowBalanceFilter(admin.SimpleListFilter):
    title = _('Low Balance')
    parameter_name = 'low_balance'

    def lookups(self, request, model_admin):
        return (
            ('<500', _('Below ₦500')),
            ('500-5000', _('₦500 - ₦5000')),
            ('>5000', _('Above ₦5000')),
        )

    def queryset(self, request, queryset):
        if self.value() == '<500':
            return queryset.filter(balance__lt=500)
        if self.value() == '500-5000':
            return queryset.filter(balance__gte=500, balance__lte=5000)
        if self.value() == '>5000':
            return queryset.filter(balance__gt=5000)
        return queryset


class HighTransactionFilter(admin.SimpleListFilter):
    title = _('High Transactions')
    parameter_name = 'high_transactions'

    def lookups(self, request, model_admin):
        return (
            ('>50', _('More than 50')),
            ('>100', _('More than 100')),
            ('>500', _('More than 500')),
        )

    def queryset(self, request, queryset):
        if self.value() == '>50':
            return queryset.annotate(tx_count=Count('transactions')).filter(tx_count__gt=50)
        if self.value() == '>100':
            return queryset.annotate(tx_count=Count('transactions')).filter(tx_count__gt=100)
        if self.value() == '>500':
            return queryset.annotate(tx_count=Count('transactions')).filter(tx_count__gt=500)
        return queryset


# -----------------------------
# UserAdmin
# -----------------------------
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = [
        "phone", "full_name", "email", "balance_colored", "total_points",
        "profile_pic_preview", "is_staff", "is_active",
        "date_joined", "last_login", "total_transactions"
    ]
    list_filter = ["is_staff", "is_superuser", "is_active", LowBalanceFilter, HighTransactionFilter]
    search_fields = ("phone", "full_name", "email", "city", "state")
    ordering = ["phone"]
    readonly_fields = ("profile_pic_preview", "balance", "total_points")
    inlines = [TransactionInline]

    # ----------------------
    # Helper methods
    # ----------------------
    def profile_pic_preview(self, obj):
        if obj.profilePic:
            return format_html(
                '<img src="{}" style="height:50px;width:50px;border-radius:50%;" />',
                obj.profilePic.url
            )
        return "-"
    profile_pic_preview.short_description = "Profile Picture"

    def total_transactions(self, obj):
        return obj.transactions.count()
    total_transactions.short_description = "Transactions"

    def total_points(self, obj):
        earned = obj.transactions.filter(type="Reward Points").aggregate(Sum('points'))['points__sum'] or 0
        redeemed = obj.transactions.filter(type="Reward Redemption").aggregate(Sum('points'))['points__sum'] or 0
        return earned - redeemed
    total_points.short_description = "Reward Points"

    def balance_colored(self, obj):
        if obj.balance < 500:
            color = "red"
        elif obj.balance <= 5000:
            color = "orange"
        else:
            color = "green"
        return format_html('<span style="color:{};">₦{}</span>', color, obj.balance)
    balance_colored.short_description = "Balance"

    # ----------------------
    # Fieldsets
    # ----------------------
    fieldsets = (
        (None, {"fields": ("phone", "pin")}),
        ("Personal info", {"fields": (
            "full_name", "email", "dob", "state", "city",
            "profilePic", "profile_pic_preview"
        )}),
        ("Permissions", {"fields": (
            "is_active", "is_staff", "is_superuser",
            "groups", "user_permissions"
        )}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "phone", "pin1", "pin2", "full_name", "email",
                "dob", "state", "city",
                "is_staff", "is_active"
            ),
        }),
    )


# -----------------------------
# TransactionAdmin
# -----------------------------
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["user", "type", "amount", "balance_after", "flw_tx_ref", "flw_status", "date"]
    list_filter = ["type", "flw_status", "date"]
    search_fields = ["user__phone", "user__full_name", "description", "flw_tx_ref"]
    readonly_fields = ["balance_after", "flw_tx_ref", "flw_status", "date"]
    ordering = ["-date"]


# -----------------------------
# Register UserAdmin
# -----------------------------
admin.site.register(User, UserAdmin)
