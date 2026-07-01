from django.urls import path
from payments.views.payment_view import PaymentCreateView
from payments.views.webhook_view import PaymentWebhookView

urlpatterns = [
    path('payments/', PaymentCreateView.as_view(), name='create-payment'),
    path("payments/webhook/", PaymentWebhookView.as_view(), name="payment-webhook")
]