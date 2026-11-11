import json
import secrets
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Order, OrderItem, Product


DELIVERY_FEES = {
    "inside_dhaka": Decimal("80.00"),
    "outside_dhaka": Decimal("130.00"),
}

SSLCOMMERZ_SESSION_URL = (
    "https://sandbox.sslcommerz.com/gwprocess/v4/api.php"
)
SSLCOMMERZ_VALIDATION_URL = (
    "https://sandbox.sslcommerz.com/validator/api/validationserverAPI.php"
)


class StockUnavailable(Exception):
    pass


class PaymentGatewayError(Exception):
    pass


def _sslcommerz_request(url, data, method="POST"):
    """Send a server-side request to SSLCOMMERZ and return its JSON response."""
    encoded_data = urlencode(data).encode("utf-8")

    if method == "GET":
        url = f"{url}?{encoded_data.decode('utf-8')}"
        request = Request(url, method="GET")
    else:
        request = Request(
            url,
            data=encoded_data,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
        OSError,
    ) as exc:
        raise PaymentGatewayError(
            "Could not contact the payment service. Please try again."
        ) from exc


def _restore_order_stock(order):
    """Restore reserved stock once when a pending online payment fails."""
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)

        if (
            locked_order.payment_method != "sslcommerz"
            or locked_order.payment_status != "pending"
        ):
            return locked_order

        for item in locked_order.items.select_related("product"):
            if item.product_id:
                Product.objects.filter(pk=item.product_id).update(
                    stock=F("stock") + item.quantity
                )

        locked_order.payment_status = "failed"
        locked_order.status = "cancelled"
        locked_order.save(
            update_fields=["payment_status", "status"]
        )

        return locked_order


def _verify_sslcommerz_payment(callback_data, order):
    """Validate the transaction directly with SSLCOMMERZ."""
    val_id = callback_data.get("val_id", "")
    callback_tran_id = callback_data.get("tran_id", "")

    if not val_id or callback_tran_id != order.transaction_id:
        return False, ""

    validation_data = _sslcommerz_request(
        SSLCOMMERZ_VALIDATION_URL,
        {
            "val_id": val_id,
            "store_id": settings.SSLCOMMERZ_STORE_ID,
            "store_passwd": settings.SSLCOMMERZ_STORE_PASS,
            "format": "json",
        },
        method="GET",
    )

    status = str(validation_data.get("status", "")).upper()
    tran_id = validation_data.get("tran_id", "")
    currency = str(validation_data.get("currency", "")).upper()

    try:
        paid_amount = Decimal(str(validation_data.get("amount", "0")))
    except Exception:
        return False, ""

    is_valid = (
        status in {"VALID", "VALIDATED"}
        and tran_id == order.transaction_id
        and currency == "BDT"
        and paid_amount == order.total
    )

    return is_valid, val_id


def _payment_result(request, order, success, message):
    return render(
        request,
        "store/payment_result.html",
        {
            "order": order,
            "payment_success": success,
            "message": message,
        },
    )


def home(request):
    search_query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "").strip()

    products = Product.objects.filter(
        available=True
    ).order_by("id")

    valid_categories = {
        value for value, label in Product.CATEGORY_CHOICES
    }

    if selected_category not in valid_categories:
        selected_category = ""

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    if selected_category:
        products = products.filter(category=selected_category)

    return render(
        request,
        "store/home.html",
        {
            "products": products,
            "search_query": search_query,
            "categories": Product.CATEGORY_CHOICES,
            "selected_category": selected_category,
        },
    )


def product_detail(request, product_id):
    product = get_object_or_404(
        Product,
        id=product_id,
        available=True,
    )

    sizes = [
        item.strip()
        for item in product.sizes.split(",")
        if item.strip()
    ]
    colors = [
        item.strip()
        for item in product.colors.split(",")
        if item.strip()
    ]

    return render(
        request,
        "store/product_detail.html",
        {
            "product": product,
            "sizes": sizes,
            "colors": colors,
            "stock_error": request.GET.get("stock_error") == "1",
        },
    )


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(
        Product,
        id=product_id,
        available=True,
    )

    sizes = [
        item.strip()
        for item in product.sizes.split(",")
        if item.strip()
    ]
    colors = [
        item.strip()
        for item in product.colors.split(",")
        if item.strip()
    ]

    size = request.POST.get("size", "")
    color = request.POST.get("color", "")

    if sizes and size not in sizes:
        return redirect("product_detail", product_id=product.id)

    if colors and color not in colors:
        return redirect("product_detail", product_id=product.id)

    cart = request.session.get("cart", [])

    for item in cart:
        if (
            item["product_id"] == product.id
            and item["size"] == size
            and item["color"] == color
        ):
            if item["quantity"] >= product.stock:
                error_url = (
                    f"{reverse('product_detail', args=[product.id])}"
                    "?stock_error=1"
                )
                return redirect(error_url)

            item["quantity"] += 1
            break
    else:
        if product.stock < 1:
            error_url = (
                f"{reverse('product_detail', args=[product.id])}"
                "?stock_error=1"
            )
            return redirect(error_url)

        cart.append(
            {
                "product_id": product.id,
                "size": size,
                "color": color,
                "quantity": 1,
            }
        )

    request.session["cart"] = cart
    return redirect("cart")


def cart_view(request):
    cart = request.session.get("cart", [])
    cart_items = []
    subtotal = Decimal("0.00")

    for index, item in enumerate(cart):
        product = Product.objects.filter(
            id=item["product_id"],
            available=True,
        ).first()

        if product is None:
            continue

        line_total = product.price * item["quantity"]
        subtotal += line_total

        cart_items.append(
            {
                "index": index,
                "product": product,
                "size": item["size"],
                "color": item["color"],
                "quantity": item["quantity"],
                "line_total": line_total,
            }
        )

    return render(
        request,
        "store/cart.html",
        {
            "cart_items": cart_items,
            "total": subtotal,
            "stock_error": request.GET.get("stock_error") == "1",
        },
    )


@require_POST
def update_cart_quantity(request, item_index):
    cart = request.session.get("cart", [])

    if 0 <= item_index < len(cart):
        item = cart[item_index]
        action = request.POST.get("action")

        if action == "increase":
            product = Product.objects.filter(
                id=item["product_id"],
                available=True,
            ).first()

            if product is None or item["quantity"] >= product.stock:
                error_url = f"{reverse('cart')}?stock_error=1"
                return redirect(error_url)

            item["quantity"] += 1

        elif action == "decrease":
            item["quantity"] -= 1

            if item["quantity"] <= 0:
                cart.pop(item_index)

        request.session["cart"] = cart

    return redirect("cart")


@require_POST
def remove_from_cart(request, item_index):
    cart = request.session.get("cart", [])

    if 0 <= item_index < len(cart):
        cart.pop(item_index)
        request.session["cart"] = cart

    return redirect("cart")


def checkout(request):
    cart = request.session.get("cart", [])
    cart_items = []
    subtotal = Decimal("0.00")

    for item in cart:
        product = Product.objects.filter(
            id=item["product_id"],
            available=True,
        ).first()

        if product is None:
            continue

        line_total = product.price * item["quantity"]
        subtotal += line_total

        cart_items.append(
            {
                "product": product,
                "size": item["size"],
                "color": item["color"],
                "quantity": item["quantity"],
                "line_total": line_total,
            }
        )

    if not cart_items:
        return redirect("cart")

    error = ""
    customer_name = ""
    phone = ""
    address = ""
    delivery_area = "inside_dhaka"
    payment_method = "cod"

    if request.method == "POST":
        customer_name = request.POST.get(
            "customer_name", ""
        ).strip()
        phone = request.POST.get("phone", "").strip()
        address = request.POST.get("address", "").strip()
        delivery_area = request.POST.get(
            "delivery_area",
            "inside_dhaka",
        )
        payment_method = request.POST.get("payment_method", "cod")

        if delivery_area not in DELIVERY_FEES:
            delivery_area = "inside_dhaka"
            error = "Please choose a valid delivery area."

        if payment_method not in {"cod", "sslcommerz"}:
            payment_method = "cod"
            error = "Please choose a valid payment method."

        if not customer_name or not phone or not address:
            error = "Please fill in your name, phone number, and address."

        if not error:
            delivery_fee = DELIVERY_FEES[delivery_area]

            try:
                with transaction.atomic():
                    order = Order.objects.create(
                        customer_name=customer_name,
                        phone=phone,
                        address=address,
                        delivery_area=delivery_area,
                        delivery_fee=delivery_fee,
                        payment_method=payment_method,
                        payment_status=(
                            "pending"
                            if payment_method == "sslcommerz"
                            else "unpaid"
                        ),
                    )

                    order.transaction_id = (
                        f"VAG-{order.pk}-{secrets.token_hex(4).upper()}"
                    )
                    order.save(update_fields=["transaction_id"])

                    for item in cart:
                        quantity = int(item["quantity"])

                        product = Product.objects.filter(
                            id=item["product_id"],
                            available=True,
                        ).first()

                        if product is None:
                            raise StockUnavailable

                        updated = Product.objects.filter(
                            id=product.id,
                            available=True,
                            stock__gte=quantity,
                        ).update(stock=F("stock") - quantity)

                        if updated == 0:
                            raise StockUnavailable

                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            product_name=product.name,
                            size=item.get("size", ""),
                            color=item.get("color", ""),
                            price=product.price,
                            quantity=quantity,
                        )

                    if not order.items.exists():
                        raise StockUnavailable

            except StockUnavailable:
                error_url = f"{reverse('cart')}?stock_error=1"
                return redirect(error_url)

            if payment_method == "cod":
                request.session["cart"] = []
                return render(
                    request,
                    "store/order_success.html",
                    {"order": order},
                )

            if (
                not settings.SSLCOMMERZ_STORE_ID
                or not settings.SSLCOMMERZ_STORE_PASS
            ):
                _restore_order_stock(order)
                error = (
                    "SSLCOMMERZ credentials are missing. "
                    "Check your .env file."
                )
            else:
                product_names = ", ".join(
                    item.product_name for item in order.items.all()
                )[:250]

                shipping_area = (
                    "Inside Dhaka"
                    if delivery_area == "inside_dhaka"
                    else "Outside Dhaka"
                )

                session_data = {
                    "store_id": settings.SSLCOMMERZ_STORE_ID,
                    "store_passwd": settings.SSLCOMMERZ_STORE_PASS,
                    "total_amount": str(order.total),
                    "currency": "BDT",
                    "tran_id": order.transaction_id,
                    "success_url": request.build_absolute_uri(
                        reverse("sslcommerz_success")
                    ),
                    "fail_url": request.build_absolute_uri(
                        reverse("sslcommerz_fail")
                    ),
                    "cancel_url": request.build_absolute_uri(
                        reverse("sslcommerz_cancel")
                    ),
                    "ipn_url": request.build_absolute_uri(
                        reverse("sslcommerz_ipn")
                    ),
                    "cus_name": customer_name,
                    "cus_email": "customer@example.com",
                    "cus_add1": address[:100],
                    "cus_city": "Dhaka",
                    "cus_postcode": "1200",
                    "cus_country": "Bangladesh",
                    "cus_phone": phone,
                    "shipping_method": "YES",
                    "ship_name": customer_name[:50],
                    "ship_add1": address[:50],
                    "ship_add2": address[50:100],
                    "ship_area": shipping_area,
                    "ship_city": "Dhaka",
                    "ship_sub_city": "Dhaka",
                    "ship_postcode": "1200",
                    "ship_country": "Bangladesh",
                    "product_name": product_names or "Clothing order",
                    "product_category": "Clothing",
                    "product_profile": "general",
                    "value_a": str(order.pk),
                }

                try:
                    gateway_response = _sslcommerz_request(
                        SSLCOMMERZ_SESSION_URL,
                        session_data,
                    )
                except PaymentGatewayError as exc:
                    _restore_order_stock(order)
                    error = str(exc)
                else:
                    gateway_url = gateway_response.get("GatewayPageURL")

                    if (
                        gateway_response.get("status") == "SUCCESS"
                        and gateway_url
                    ):
                        request.session["cart"] = []
                        return redirect(gateway_url)

                    _restore_order_stock(order)
                    error = (
                        gateway_response.get("failedreason")
                        or "SSLCOMMERZ could not start the payment. "
                        "Please try again."
                    )

    delivery_fee = DELIVERY_FEES[delivery_area]
    total = subtotal + delivery_fee

    delivery_options = [
        (
            "inside_dhaka",
            "Inside Dhaka",
            DELIVERY_FEES["inside_dhaka"],
        ),
        (
            "outside_dhaka",
            "Outside Dhaka",
            DELIVERY_FEES["outside_dhaka"],
        ),
    ]

    return render(
        request,
        "store/checkout.html",
        {
            "error": error,
            "customer_name": customer_name,
            "phone": phone,
            "address": address,
            "cart_items": cart_items,
            "subtotal": subtotal,
            "delivery_area": delivery_area,
            "delivery_fee": delivery_fee,
            "total": total,
            "delivery_options": delivery_options,
            "payment_method": payment_method,
        },
    )


@csrf_exempt
def sslcommerz_success(request):
    callback_data = request.POST if request.method == "POST" else request.GET
    tran_id = callback_data.get("tran_id", "")

    order = Order.objects.filter(
        transaction_id=tran_id,
        payment_method="sslcommerz",
    ).first()

    if order is None:
        return HttpResponse("Order not found.", status=404)

    try:
        is_valid, val_id = _verify_sslcommerz_payment(
            callback_data,
            order,
        )
    except PaymentGatewayError:
        return _payment_result(
            request,
            order,
            False,
            "We could not verify the payment yet. Please contact the store.",
        )

    if not is_valid:
        return _payment_result(
            request,
            order,
            False,
            "The payment could not be verified.",
        )

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)

        if locked_order.payment_status != "paid":
            locked_order.payment_status = "paid"
            locked_order.sslcommerz_val_id = val_id
            locked_order.save(
                update_fields=[
                    "payment_status",
                    "sslcommerz_val_id",
                ]
            )

    return _payment_result(
        request,
        order,
        True,
        "Your payment was verified and your order is confirmed.",
    )


@csrf_exempt
def sslcommerz_fail(request):
    callback_data = request.POST if request.method == "POST" else request.GET
    tran_id = callback_data.get("tran_id", "")

    order = Order.objects.filter(
        transaction_id=tran_id,
        payment_method="sslcommerz",
    ).first()

    if order is None:
        return HttpResponse("Order not found.", status=404)

    order = _restore_order_stock(order)

    return _payment_result(
        request,
        order,
        False,
        "The payment failed. Your order was not completed.",
    )


@csrf_exempt
def sslcommerz_cancel(request):
    callback_data = request.POST if request.method == "POST" else request.GET
    tran_id = callback_data.get("tran_id", "")

    order = Order.objects.filter(
        transaction_id=tran_id,
        payment_method="sslcommerz",
    ).first()

    if order is None:
        return HttpResponse("Order not found.", status=404)

    order = _restore_order_stock(order)

    return _payment_result(
        request,
        order,
        False,
        "You cancelled the payment. Your order was not completed.",
    )


@csrf_exempt
@require_POST
def sslcommerz_ipn(request):
    callback_data = request.POST
    tran_id = callback_data.get("tran_id", "")

    order = Order.objects.filter(
        transaction_id=tran_id,
        payment_method="sslcommerz",
    ).first()

    if order is None:
        return HttpResponse("Order not found.", status=404)

    try:
        is_valid, val_id = _verify_sslcommerz_payment(
            callback_data,
            order,
        )
    except PaymentGatewayError:
        return HttpResponse("Could not verify payment.", status=502)

    if not is_valid:
        return HttpResponse("Invalid payment.", status=400)

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)

        if locked_order.payment_status != "paid":
            locked_order.payment_status = "paid"
            locked_order.sslcommerz_val_id = val_id
            locked_order.save(
                update_fields=[
                    "payment_status",
                    "sslcommerz_val_id",
                ]
            )

    return HttpResponse("Payment validated.", status=200)