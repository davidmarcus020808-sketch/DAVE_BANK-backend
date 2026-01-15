
from rest_framework import serializers
from django.contrib.auth import get_user_model                          
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Sum
from django.db import transaction as db_transaction
from .models import Transaction


User = get_user_model()


# --------------------------
# VERIFY FLUTTERWAVE PAYMENT
# --------------------------
class VerifyFlutterwavePaymentSerializer(serializers.Serializer):
    tx_ref = serializers.CharField()
    transaction_id = serializers.CharField()

    def create(self, validated_data):
        import requests
        from django.conf import settings

        user = self.context["request"].user
        tx_ref = validated_data["tx_ref"]
        transaction_id = validated_data["transaction_id"]

        url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
        headers = {"Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"}

        response = requests.get(url, headers=headers).json()
        data = response.get("data", {})

        if response.get("status") != "success" or data.get("status") != "successful":
            raise serializers.ValidationError("Transaction verification failed")

        if data.get("currency") != "NGN":
            raise serializers.ValidationError("Invalid currency")

        amount = data.get("amount")
        if not amount:
            raise serializers.ValidationError("Invalid amount")

        if Transaction.objects.filter(flw_tx_ref=tx_ref).exists():
            return {"message": "Transaction already recorded"}

        tx = Transaction.objects.create(
            user=user,
            type="Add Money",
            amount=amount,
            flw_tx_ref=tx_ref,
            flw_id=data.get("id"),
            flw_status="pending",
            flw_payment_type=data.get("payment_type"),
            flw_currency="NGN",
            description=f"Wallet top-up via Flutterwave (tx_ref: {tx_ref})"
        )

        return {"transaction_id": tx.id, "amount": amount}

# --------------------------
# USER REGISTRATION SERIALIZER
# --------------------------
class RegisterSerializer(serializers.ModelSerializer):
    pin = serializers.CharField(write_only=True, min_length=4, max_length=4)
    firstName = serializers.CharField(required=True)
    lastName = serializers.CharField(required=True)
    dob = serializers.DateField(required=True)
    email = serializers.EmailField(required=True)
    state = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["id", "phone", "email", "firstName", "lastName", "dob", "state", "city", "pin"]

    def validate_phone(self, value):
        if User.objects.filter(phone=value.strip()).exists():
            raise serializers.ValidationError("Phone number already exists.")
        return value.strip()

    def create(self, validated_data):
        pin = validated_data.pop("pin")
        first_name = validated_data.pop("firstName")
        last_name = validated_data.pop("lastName")
        full_name = f"{first_name} {last_name}"

        user = User.objects.create_user(
            phone=validated_data["phone"],
            password=pin,
            full_name=full_name,
            email=validated_data.get("email"),
            dob=validated_data.get("dob"),
            state=validated_data.get("state", ""),
            city=validated_data.get("city", ""),
        )
        return user


# --------------------------
# LOGIN SERIALIZER
# --------------------------
class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    pin = serializers.CharField(write_only=True, min_length=4, max_length=4)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)

    def validate(self, attrs):
        phone = attrs.get("phone").strip()
        pin = attrs.get("pin").strip()

        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid phone or PIN.")

        if not user.check_pin(pin):
            raise serializers.ValidationError("Invalid phone or PIN.")

        refresh = RefreshToken.for_user(user)
        attrs["user"] = user
        attrs["access"] = str(refresh.access_token)
        attrs["refresh"] = str(refresh)
        return attrs


# --------------------------
# TRANSACTION SERIALIZER
# --------------------------
class TransactionSerializer(serializers.ModelSerializer):
    pin = serializers.CharField(write_only=True, required=True)
    balance_after = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    description = serializers.CharField(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id", "type", "amount", "recipient", "account_number", "description",
            "pin", "phone", "provider", "expiry", "category", "planLabel",
            "points", "balance_after"
        ]

    def validate_pin(self, value):
        user = self.context['request'].user
        if not user.check_pin(value):
            raise serializers.ValidationError("Invalid PIN")
        return value

    def create(self, validated_data):
        validated_data.pop("pin", None)
        return Transaction.objects.create(**validated_data)

# --------------------------
# ACCOUNT SERIALIZER
# --------------------------
class AccountSerializer(serializers.ModelSerializer):
    profilePic = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()
    tier = serializers.SerializerMethodField()
    recent_transactions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "phone", "balance",
                  "profilePic", "date_joined", "total_points", "tier", "recent_transactions"]

    def get_profilePic(self, obj):
        if obj.profilePic:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.profilePic.url)
        return None

    def get_total_points(self, obj):
        txns = obj.transactions.all()
        earned = txns.filter(type="Reward Points").aggregate(Sum('points'))['points__sum'] or 0
        redeemed = txns.filter(type="Reward Redemption").aggregate(Sum('points'))['points__sum'] or 0
        return earned - redeemed

    def get_tier(self, obj):
        total_points = self.get_total_points(obj)
        if total_points >= 5000:
            return "Platinum"
        elif total_points >= 2500:
            return "Gold"
        elif total_points >= 1000:
            return "Silver"
        return "Bronze"

    def get_recent_transactions(self, obj):
        txns = obj.transactions.order_by('-date')[:5]
        return TransactionSerializer(txns, many=True, context=self.context).data
