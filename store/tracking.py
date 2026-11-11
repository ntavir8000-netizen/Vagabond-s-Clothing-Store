from django.shortcuts import render

from .models import Order


def track_order(request):
    order_id = request.GET.get('order_id', '').strip()
    phone = ''
    order = None
    error = ''

    if request.method == 'POST':
        order_id = request.POST.get('order_id', '').strip()
        phone = request.POST.get('phone', '').strip()

        if not order_id or not phone:
            error = 'Enter your order number and phone number.'
        else:
            try:
                order = Order.objects.prefetch_related('items').get(
                    id=int(order_id),
                    phone=phone,
                )
            except (Order.DoesNotExist, ValueError):
                error = 'We could not find an order with those details.'

    return render(request, 'store/track_order.html', {
        'order': order,
        'order_id': order_id,
        'phone': phone,
        'error': error,
    })