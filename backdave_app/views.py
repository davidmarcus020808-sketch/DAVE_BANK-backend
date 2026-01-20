import json
import random
import requests
from decimal import Decimal
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.db import transaction


import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import Transaction
from .serializers import (
    LoginSerializer,
    AccountSerializer,
    TransactionSerializer,
     RegisterSerializer,  # <-- add this

)

User = get_user_model()


# --------------------------
# FLUTTERWAVE WEBHOOK
# --------------------------
logger = logging.getLogger(__name__)

@csrf_exempt
def flutterwave_webhook(request):
    signature = request.headers.get("verif-hash")
    if signature != settings.FLUTTERWAVE_SECRET_HASH:
        logger.warning("Invalid webhook signature: %s", signature)
        return JsonResponse({"error": "Invalid signature"}, status=401)

    try:
        payload = json.loads(request.body)
        data = payload.get("data", {})
        tx_ref = data.get("tx_ref")
        flw_id = data.get("id")
        amount = data.get("amount")
        currency = data.get("currency")
        status_tx = data.get("status")
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Webhook parsing failed: %s", str(e))
        return JsonResponse({"error": "Invalid payload"}, status=400)

    if status_tx != "successful":
        logger.info("Ignored webhook for tx_ref=%s, status=%s", tx_ref, status_tx)
        return JsonResponse({"status": "ignored"})

    # Verify with Flutterwave server-side
    verify_url = f"https://api.flutterwave.com/v3/transactions/{flw_id}/verify"
    headers = {"Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"}

    try:
        verify_res = requests.get(verify_url, headers=headers, timeout=10).json()
        verified_data = verify_res.get("data", {})
    except requests.RequestException as e:
        logger.error("Flutterwave verification failed for tx_ref=%s: %s", tx_ref, str(e))
        return JsonResponse({"error": "Verification timeout"}, status=500)

    if verified_data.get("status") != "successful":
        logger.warning("Verification failed for tx_ref=%s", tx_ref)
        return JsonResponse({"error": "Verification failed"}, status=400)

    with transaction.atomic():
        tx = Transaction.objects.select_for_update().filter(flw_tx_ref=tx_ref).first()
        if not tx:
            logger.warning("Transaction not found for tx_ref=%s", tx_ref)
            return JsonResponse({"error": "Transaction not found"}, status=404)

        # Idempotency check
        if tx.processed:
            logger.info("Transaction already processed: tx_ref=%s", tx_ref)
            return JsonResponse({"status": "already_processed"})

        # Validate amount and currency
        if Decimal(verified_data.get("amount")) != tx.amount:
            logger.error("Amount mismatch for tx_ref=%s: expected %s, got %s", tx_ref, tx.amount, verified_data.get("amount"))
            return JsonResponse({"error": "Amount mismatch"}, status=400)
        if verified_data.get("currency") != tx.flw_currency:
            logger.error("Currency mismatch for tx_ref=%s: expected %s, got %s", tx_ref, tx.flw_currency, verified_data.get("currency"))
            return JsonResponse({"error": "Currency mismatch"}, status=400)

        # Credit wallet
        tx.user.balance += tx.amount
        tx.user.save(update_fields=["balance"])

        tx.flw_id = flw_id
        tx.flw_status = "successful"
        tx.processed = True
        tx.save(update_fields=["flw_id", "flw_status", "processed"])

        logger.info("Transaction processed successfully: tx_ref=%s, amount=%s", tx_ref, tx.amount)

    return JsonResponse({"status": "success"})


    # views.py
class InitFlutterwavePayment(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        amount = request.data.get("amount")
        if not amount or Decimal(amount) < 100:
            return Response({"error": "Invalid amount"}, status=400)

        tx_ref = f"FLW-{request.user.id}-{random.randint(100000,999999)}"

        tx = Transaction.objects.create(
            user=request.user,
            type="Add Money",
            amount=Decimal(amount),
            flw_tx_ref=tx_ref,
            flw_status="pending",
            flw_currency="NGN",
        )

        return Response({
            "tx_ref": tx_ref,
            "amount": str(tx.amount),
            "email": request.user.email,
            "phone": request.user.phone,
            "name": request.user.full_name,
        })


# This must be **dedented** (not inside InitFlutterwavePayment)
class FlutterwaveVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        tx_ref = request.data.get("tx_ref")

        if not tx_ref:
            return Response({"error": "tx_ref is required"}, status=400)

        tx = Transaction.objects.filter(
            flw_tx_ref=tx_ref,
            user=request.user
        ).first()

        if not tx:
            return Response({"error": "Transaction not found"}, status=404)

        if tx.processed:
            return Response({"status": "already_processed"})

        # Verify with Flutterwave
        verify_url = f"https://api.flutterwave.com/v3/transactions/verify_by_reference?tx_ref={tx_ref}"
        headers = {
            "Authorization": f"Bearer {settings.FLUTTERWAVE_SECRET_KEY}"
        }

        res = requests.get(verify_url, headers=headers).json()
        data = res.get("data")

        if not data or data.get("status") != "successful":
            return Response({"error": "Payment not successful"}, status=400)

        if Decimal(data["amount"]) != tx.amount:
            return Response({"error": "Amount mismatch"}, status=400)

        # Credit wallet
        with transaction.atomic():
            request.user.balance += tx.amount
            request.user.save(update_fields=["balance"])

            tx.flw_id = data["id"]
            tx.flw_status = "successful"
            tx.processed = True
            tx.save()

        return Response({
            "success": True,
            "balance": str(request.user.balance)
        })


# --------------------------
# REGISTER VIEW
# --------------------------
class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "success": True,
                    "message": "Account created successfully",
                    "phone": user.phone,
                },
                status=status.HTTP_201_CREATED
            )
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

# -------------------------
# LOGIN VIEW
# --------------------------
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        access = serializer.validated_data["access"]
        refresh = serializer.validated_data["refresh"]

        response = Response({"success": True, "access": access})
        response.set_cookie(
            "refresh_token",
            refresh,
            httponly=True,
            samesite="Lax",
            max_age=7 * 24 * 60 * 60
        )
        return response


# --------------------------
# REFRESH TOKEN VIEW
# --------------------------
class RefreshTokenView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        token = request.COOKIES.get("refresh_token")
        if not token:
            return Response({"detail": "Missing refresh token"}, status=401)

        try:
            refresh = RefreshToken(token)
            return Response({"access": str(refresh.access_token)})
        except TokenError:
            return Response({"detail": "Invalid token"}, status=401)


# --------------------------
# ACCOUNT VIEW
# --------------------------
class AccountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(AccountSerializer(request.user).data)

    def post(self, request):
        user = request.user
        user.full_name = request.data.get("name", user.full_name)
        user.email = request.data.get("email", user.email)
        user.phone = request.data.get("phone", user.phone)

        if "profilePic" in request.FILES:
            user.profilePic = request.FILES["profilePic"]

        user.save()
        return Response(AccountSerializer(user).data)


# --------------------------
# VERIFY TRANSFER ACCOUNT VIEW (TEST MODE)
# --------------------------
class TransferVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        account_number = request.data.get("account_number")
        bank_name = request.data.get("bank_name")

        if not account_number or not bank_name:
            return Response({"success": False, "error": "Both account_number and bank_name are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Fake account name for testing
        account_name = random.choice(["John Doe"])
        return Response({"success": True, "account_name": account_name}, status=status.HTTP_200_OK)


# --------------------------
# PIN VIEWS


class UpdatePinView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        pin = request.data.get("pin")
        if not pin or len(pin) != 4 or not pin.isdigit():
            return Response({"error": "Invalid PIN"}, status=400)

        request.user.set_pin(pin, save=False)
        request.user.save(update_fields=["password"])  # force save
        return Response({"success": True})

# --------------------------
class ValidatePinView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        pin = request.data.get("pin")
        if not pin or not request.user.check_pin(pin):
            return Response({"valid": False}, status=400)
        return Response({"valid": True})


class TransactionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        txs = request.user.transactions.order_by("-date")[:100]
        return Response(
            TransactionSerializer(txs, many=True, context={"request": request}).data
        )

    def post(self, request):
        data = request.data.copy()
        tx_type = data.get("type")

        # --------------------------
        # Check required fields
        # --------------------------
        if not tx_type:
            return Response({"error": "Transaction type is required"}, status=400)

        if tx_type not in ["Add Money", "Deposit"]:
            pin = data.get("pin")
            if not pin or not request.user.check_pin(pin):
                return Response({"error": "Invalid or missing PIN"}, status=400)

        # --------------------------
        # Validate amount
        # --------------------------
        amount = data.get("amount")
        if not amount:
            return Response({"error": "Amount is required"}, status=400)

        try:
            amount = Decimal(amount)
            if amount <= 0:
                raise ValueError
        except:
            return Response({"error": "Invalid amount"}, status=400)

        # --------------------------
        # Create transaction (FIXED)
        # --------------------------
        serializer = TransactionSerializer(
            data=data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            tx = serializer.save(user=request.user)

            if tx.type not in ["Reward Points", "Reward Redemption"]:
                Transaction.objects.create(
                    user=request.user,
                    type="Reward Points",
                    points=100,
                    amount=0
                )

        return Response(
            {
                "success": True,
                "reference": f"TXN-{tx.id:06d}",
                "amount": str(tx.amount),
                "type": tx.type,
            },
            status=201,
        )

        return Response({
            "success": True,
            "reference": f"TXN-{tx.id:06d}",
            "amount": str(tx.amount),
            "type": tx.type
        }, status=201)
# --------------------------
# REWARDS VIEW
# --------------------------
class RewardsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        txs = request.user.transactions.all()
        earned = txs.filter(type="Reward Points").aggregate(Sum("points"))["points__sum"] or 0
        redeemed = txs.filter(type="Reward Redemption").aggregate(Sum("points"))["points__sum"] or 0
        total = earned + redeemed

        if total >= 5000:
            tier = "Platinum"
        elif total >= 2500:
            tier = "Gold"
        elif total >= 1000:
            tier = "Silver"
        else:
            tier = "Bronze"

        return Response({"points": total, "tier": tier})


# --------------------------
# DASHBOARD VIEW
# --------------------------
class DashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        msg = f"Welcome, {request.user.full_name or request.user.phone}"
        return Response({"message": msg})
