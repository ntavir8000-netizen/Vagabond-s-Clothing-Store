from django.urls import path

from . import tracking, views


urlpatterns = [
    path("", views.home, name="home"),
    path(
        "product/<int:product_id>/",
        views.product_detail,
        name="product_detail",
    ),
    path("cart/", views.cart_view, name="cart"),
    path(
        "cart/add/<int:product_id>/",
        views.add_to_cart,
        name="add_to_cart",
    ),
    path(
        "cart/update/<int:item_index>/",
        views.update_cart_quantity,
        name="update_cart_quantity",
    ),
    path(
        "cart/remove/<int:item_index>/",
        views.remove_from_cart,
        name="remove_from_cart",
    ),
    path("checkout/", views.checkout, name="checkout"),
    path("track-order/", tracking.track_order, name="track_order"),
    path(
        "payment/sslcommerz/success/",
        views.sslcommerz_success,
        name="sslcommerz_success",
    ),
    path(
        "payment/sslcommerz/fail/",
        views.sslcommerz_fail,
        name="sslcommerz_fail",
    ),
    path(
        "payment/sslcommerz/cancel/",
        views.sslcommerz_cancel,
        name="sslcommerz_cancel",
    ),
    path(
        "payment/sslcommerz/ipn/",
        views.sslcommerz_ipn,
        name="sslcommerz_ipn",
    ),
]