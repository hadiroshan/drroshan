import csv
import json
import mimetypes
import os
import random
import string
from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import FileResponse, HttpResponse, Http404, JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.utils import timezone

BASE_DIR = settings.BASE_DIR
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Course, NotificationLog, Order, OrderItem

FA_MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
             'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']

STATUS_LIST = ['paid', 'shipped', 'awaiting_receipt', 'awaiting_cod', 'canceled']

# نگاشت وضعیت‌های فارسی نسخه استاتیک به کلیدهای مدل
STATUS_MAP = {
    'پرداخت شده': 'paid',
    'ارسال شد': 'shipped',
    'در انتظار تایید رسید': 'awaiting_receipt',
    'در انتظار پرداخت در محل': 'awaiting_cod',
    'لغو شده': 'canceled',
}

# پسوندهای مجاز برای سرو صفحات استاتیک سایت از ریشه پروژه
SAFE_EXT = {'.html', '.css', '.js', '.mjs', '.png', '.jpg', '.jpeg', '.gif',
            '.svg', '.webp', '.ico', '.json', '.webmanifest', '.txt', '.woff2'}


def generate_order_code():
    """کد سفارش یکتا به فرمت HR-XXXXXX"""
    while True:
        code = 'HR-' + ''.join(random.choices(string.digits, k=6))
        if not Order.objects.filter(code=code).exists():
            return code


# ---------------- صفحات سایت ----------------

def index(request):
    """صفحه اصلی — سرو index.html استاتیک"""
    return static_page(request, 'index.html')


def static_page(request, filename):
    """سرو امن فایل‌های استاتیک سایت از ریشه پروژه (فقط DEBUG)"""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SAFE_EXT:
        raise Http404
    full = (BASE_DIR / filename).resolve()
    if not str(full).startswith(str(BASE_DIR)) or not full.is_file():
        raise Http404
    content_type = mimetypes.types_map.get(ext, 'application/octet-stream')
    if ext == '.js':
        content_type = 'text/javascript'
    response = FileResponse(full.open('rb'), content_type=content_type)
    response['Content-Disposition'] = 'inline'
    return response


def dashboard(request):
    """داشبورد مدیریت سفارش‌ها با داده واقعی از دیتابیس"""
    orders = Order.objects.prefetch_related('items').all()

    # آمار کلی
    paid = orders.filter(status='paid')
    stats = {
        'total': orders.count(),
        'paid': paid.count(),
        'pending': orders.exclude(status__in=['paid', 'canceled']).count(),
        'revenue': paid.aggregate(s=Sum('total'))['s'] or 0,
    }

    # فروش ۱۴ روز اخیر
    today = timezone.localdate()
    daily = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        daily.append({'date': d, 'total': 0, 'count': 0})
    d_map = {row['date']: row for row in daily}
    daily_data = (
        paid.filter(created_at__date__gte=today - timedelta(days=13))
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total=Sum('total'), count=Count('id'))
    )
    for row in daily_data:
        if row['day'] in d_map:
            d_map[row['day']]['total'] = row['total']
            d_map[row['day']]['count'] = row['count']

    # فروش ۱۲ ماه اخیر (برچسب شمسی — ماه‌های میلادی به‌ترتیب)
    monthly = []
    y, m = today.year, today.month
    for _ in range(12):
        monthly.append({'first': timezone.datetime(y, m, 1).date(), 'total': 0, 'count': 0})
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    monthly.reverse()
    m_map = {row['first']: row for row in monthly}
    monthly_data = (
        paid.filter(created_at__date__gte=monthly[0]['first'])
        .annotate(month=TruncDate('created_at'))
        .values('month')
        .annotate(total=Sum('total'), count=Count('id'))
    )
    for row in monthly_data:
        slot = m_map.get(row['month'].replace(day=1))
        if slot:
            slot['total'] += row['total']
            slot['count'] += row['count']

    # پرفروش‌ترین دوره‌ها
    top_courses = (
        OrderItem.objects.filter(order__status='paid')
        .values('name', 'emoji')
        .annotate(qty=Sum('qty'), rev=Sum('price'))
        .order_by('-qty')[:5]
    )

    daily_max = max([row['total'] for row in daily] + [1])
    monthly_max = max([row['total'] for row in monthly] + [1])
    top_list = list(top_courses)
    top_max = max([c['qty'] for c in top_list] + [1])

    context = {
        'stats': stats,
        'daily': daily,
        'daily_max': daily_max,
        'monthly': monthly,
        'monthly_max': monthly_max,
        'top_courses': top_list,
        'top_max': top_max,
        'status_choices': Order.STATUS_CHOICES,
        'orders_json': [o.as_dashboard_dict() for o in orders],
        'status_names_json': dict(Order.STATUS_CHOICES),
    }
    return render(request, 'dashboard.html', context)


# ---------------- API ----------------

@csrf_exempt
@require_POST
def api_orders(request):
    """ثبت سفارش جدید از checkout.html (به جای localStorage)"""
    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'JSON نامعتبر'}, status=400)

    customer = data.get('customer') or {}
    if not customer.get('name') or not customer.get('phone'):
        return JsonResponse({'ok': False, 'error': 'نام و موبایل الزامی است'}, status=400)

    items = data.get('items') or []
    if not items:
        return JsonResponse({'ok': False, 'error': 'سبد خالی است'}, status=400)

    order = Order.objects.create(
        code=generate_order_code(),
        status=STATUS_MAP.get(data.get('status'), 'awaiting_receipt'),
        customer_name=customer.get('name', '')[:120],
        customer_phone=customer.get('phone', '')[:20],
        customer_national=customer.get('national', '')[:20],
        customer_email=customer.get('email', '')[:254],
        customer_province=customer.get('province', '')[:60],
        customer_postal=customer.get('postal', '')[:20],
        customer_address=customer.get('address', '')[:1000],
        shipping_method=customer.get('shippingMethod', '')[:80],
        payment_method=data.get('payment', {}).get('method') or 'card',
        payment_card=data.get('payment', {}).get('card', '')[:24],
        payment_rrn=data.get('payment', {}).get('rrn', '')[:40],
        payment_receipt=data.get('payment', {}).get('receipt', '')[:60],
        coupon_code=data.get('coupon') or '',
        subtotal=int(data.get('subtotal') or 0),
        discount=int(data.get('discount') or 0),
        shipping_cost=int(data.get('shipping') or 0),
        total=int(data.get('total') or 0),
    )
    for it in items:
        course = Course.objects.filter(name=it.get('name')).first()
        OrderItem.objects.create(
            order=order,
            course=course,
            name=it.get('name', ''),
            emoji=it.get('emoji', '🎓'),
            price=int(it.get('price') or 0),
            qty=int(it.get('qty') or 1),
        )
    return JsonResponse({'ok': True, 'code': order.code, 'id': order.id})


@require_GET
def api_order_status_public(request):
    """وضعیت زنده سفارش‌های مشتری برای صفحه پروفایل (فقط خواندنی، بر اساس کد سفارش)"""
    codes_param = request.GET.get('codes', '')
    codes = [c.strip() for c in codes_param.split(',') if c.strip()][:50]
    if not codes:
        return JsonResponse({'ok': True, 'orders': []})
    orders = Order.objects.filter(code__in=codes).prefetch_related('items')
    data = [{
        'code': o.code,
        'status_key': o.status,
        'status': o.get_status_display(),
        'total': o.total,
        'date': timezone.localtime(o.created_at).isoformat(),
        'tracking': o.postal_tracking or None,
        'items': [{'name': i.name, 'emoji': i.emoji, 'qty': i.qty} for i in o.items.all()],
    } for o in orders]
    return JsonResponse({'ok': True, 'orders': data})


@staff_member_required
def api_order_status(request, code):
    """تغییر وضعیت سفارش از داشبورد"""
    order = get_object_or_404(Order, code=code)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        tracking = (request.POST.get('tracking') or '').strip()
        if new_status not in STATUS_LIST:
            return JsonResponse({'ok': False, 'error': 'وضعیت نامعتبر'}, status=400)
        if new_status == 'shipped' and not (order.postal_tracking or tracking):
            return JsonResponse({'ok': False, 'error': 'برای ارسال، کد رهگیری پستی لازم است'}, status=400)
        order.status = new_status
        if tracking:
            order.postal_tracking = tracking
        order.save(update_fields=['status', 'postal_tracking', 'updated_at'])

        # اطلاع‌رسانی خودکار به مشتری بعد از تغییر وضعیت (اگر مدیر خواسته باشد)
        # رویدادها: paid / shipped / canceled — متن از قالب‌های قابل ویرایش ادمین
        notif = None
        notify_events = ('paid', 'shipped', 'canceled')
        if new_status in notify_events and request.POST.get('notify', '1') != '0':
            from .notifications import notify_order_status
            channel = 'whatsapp' if request.POST.get('channel') == 'whatsapp' else 'sms'
            notif = notify_order_status(order, new_status, channel=channel)

        return JsonResponse({
            'ok': True, 'status': order.get_status_display(), 'tracking': order.postal_tracking,
            'notify': ({
                'id': notif.id, 'channel': notif.channel, 'kind': notif.kind, 'status': notif.status,
                'error': notif.error, 'link': notif.provider_ref if notif.status == 'manual' else '',
            } if notif else None),
        })
    return JsonResponse({'ok': True, 'status': order.status, 'name': order.get_status_display()})


@staff_member_required
def notifications_page(request):
    """صفحه اطلاع‌رسانی‌ها در داشبورد با فیلتر کانال، وضعیت ارسال و نوع رویداد"""
    logs = NotificationLog.objects.select_related('order').all()

    channel = request.GET.get('channel', '')
    status = request.GET.get('status', '')
    kind = request.GET.get('kind', '')
    if channel in ('sms', 'whatsapp'):
        logs = logs.filter(channel=channel)
    if status in ('sent', 'failed', 'manual'):
        logs = logs.filter(status=status)
    if kind in ('paid', 'shipped', 'canceled'):
        logs = logs.filter(kind=kind)

    context = {
        'logs': logs[:200],
        'total_count': logs.count(),
        'stats': {
            'total': NotificationLog.objects.count(),
            'sent': NotificationLog.objects.filter(status='sent').count(),
            'failed': NotificationLog.objects.filter(status='failed').count(),
            'manual': NotificationLog.objects.filter(status='manual').count(),
        },
        'channel': channel,
        'status': status,
        'kind': kind,
        'channel_choices': NotificationLog.CHANNEL_CHOICES,
        'status_choices': NotificationLog.STATUS_CHOICES,
        'kind_choices': NotificationLog.KIND_CHOICES,
    }
    return render(request, 'notifications.html', context)


@staff_member_required
def export_csv(request):
    """خروجی CSV سفارش‌ها"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=orders.csv'
    response.write('\ufeff')  # BOM برای اکسل
    writer = csv.writer(response)
    writer.writerow(['کد', 'تاریخ', 'مشتری', 'موبایل', 'تعداد اقلام', 'جمع', 'تخفیف', 'ارسال', 'کل', 'روش پرداخت', 'وضعیت', 'کد رهگیری پستی'])
    for o in Order.objects.prefetch_related('items').all():
        writer.writerow([
            o.code,
            timezone.localtime(o.created_at).strftime('%Y-%m-%d %H:%M'),
            o.customer_name, o.customer_phone,
            sum(i.qty for i in o.items.all()),
            o.subtotal, o.discount, o.shipping_cost, o.total,
            o.get_payment_method_display(),
            o.get_status_display(),
            o.postal_tracking,
        ])
    return response


@staff_member_required
def export_json(request):
    data = [o.as_frontend_dict() for o in Order.objects.prefetch_related('items').all()]
    response = HttpResponse(json.dumps(data, ensure_ascii=False, indent=2), content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename=orders.json'
    return response
