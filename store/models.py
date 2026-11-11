from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    CATEGORY_CHOICES = [
        ("t-shirts", "T-Shirts"),
        ("shirts", "Shirts"),
        ("pants", "Pants"),
        ("hoodies", "Hoodies"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="other",
    )
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    image = models.ImageField(
        upload_to="products/",
        blank=True,
        null=True,
    )
    sizes = models.CharField(
        max_length=100,
        blank=True,
        help_text="Enter sizes separated by commas, for example: S, M, L, XL",
    )
    colors = models.CharField(
        max_length=150,
        blank=True,
        help_text="Enter colors separated by commas, for example: Black, White",
    )
    stock = models.PositiveIntegerField(
        default=0,
        help_text="How many units are currently available?",
    )
    available = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    DELIVERY_AREA_CHOICES = [
        ("inside_dhaka", "Inside Dhaka"),
        ("outside_dhaka", "Outside Dhaka"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("cod", "Cash on Delivery"),
        ("sslcommerz", "SSLCOMMERZ"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("pending", "Payment Pending"),
        ("paid", "Paid"),
        ("failed", "Payment Failed"),
    ]

    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    delivery_area = models.CharField(
        max_length=20,
        choices=DELIVERY_AREA_CHOICES,
        default="inside_dhaka",
    )
    delivery_fee = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="cod",
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="unpaid",
    )
    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    sslcommerz_val_id = models.CharField(
        max_length=100,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} — {self.customer_name}"

    @property
    def total(self):
        items_total = sum(
            (item.line_total for item in self.items.all()),
            Decimal("0.00"),
        )
        return items_total + self.delivery_fee


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=200)
    size = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} × {self.product_name}"

    @property
    def line_total(self):
        return self.price * self.quantity