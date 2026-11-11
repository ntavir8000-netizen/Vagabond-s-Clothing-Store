from django.contrib import admin

from .models import Order, OrderItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'stock', 'available')
    list_filter = ('category', 'available')
    search_fields = ('name',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        'product_name',
        'size',
        'color',
        'price',
        'quantity',
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer_name',
        'phone',
        'delivery_area',
        'delivery_fee',
        'status',
        'created_at',
    )
    list_filter = ('status', 'delivery_area', 'created_at')
    search_fields = ('customer_name', 'phone')
    inlines = [OrderItemInline]