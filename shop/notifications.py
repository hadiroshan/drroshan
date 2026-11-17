"""اطلاع‌رسانی خودکار به مشتری (پیامک/واتساپ) بعد از تغییر وضعیت سفارش.

پیامک از طریق کاوه‌نگار (kavenegar.com) ارسال می‌شود؛ کلید API را در
متغیر محیطی KAVENEGAR_API_KEY قرار دهید. بدون کلید، ارسال غیرفعال است
و سیستم فقط لاگ «failed» ثبت می‌کند تا جریان سایت نشکند.

واتساپ: واتساپ فقط با شماره کار می‌کند؛ ما یک لینک wa.me آماده با متن
پیام تولید می‌کنیم تا مدیر با یک کلیک آن را برای مشتری بفرستد (بدون API).

متن پیام از قالب‌های MessageTemplate (قابل ویرایش از پنل ادمین) خوانده
می‌شود. متغیرهای مجاز: {customer_name} {order_code} {total} {tracking}
{status_label} {site_name}
"""
import logging

import requests
from django.conf import settings

from .models import MessageTemplate, NotificationLog

logger = logging.getLogger(__name__)

KAVENEGAR_SMS_URL = 'https://api.kavenegar.com/v1/{key}/sms/send.json'

# رویدادهای اطلاع‌رسانی + برچسب وضعیت پیش‌فرض هرکدام
EVENT_STATUS_LABELS = {
    'paid': 'پرداخت شده',
    'shipped': 'ارسال شد',
    'canceled': 'لغو شده',
}


def normalize_phone(phone):
    """تبدیل شماره ایرانی به فرم بین‌المللی بدون + (مثلا 989112921512)."""
    p = (phone or '').strip().replace(' ', '').replace('-', '')
    digits = ''.join(ch for ch in p if ch.isdigit())
    if digits.startswith('0098'):
        digits = digits[4:]
    elif digits.startswith('098'):
        digits = digits[3:]
    elif digits.startswith('98') and len(digits) > 10:
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = '98' + digits[1:]
    return digits


def build_message(order, event='paid'):
    """متن پیام رویداد موردنظر از روی قالب ادمین (یا پیش‌فرض داخلی)."""
    from .utils_fa import fa_money  # noqa: PLC0415 — import داخلی برای پرهیز از چرخه

    tpl = MessageTemplate.objects.filter(event=event, is_active=True).first()
    if tpl and (tpl.message or '').strip():
        text = tpl.message
    else:
        text = DEFAULT_MESSAGES.get(event) or DEFAULT_MESSAGES['paid']

    values = {
        'customer_name': order.customer_name or 'مشتری',
        'order_code': order.code,
        'total': fa_money(order.total),
        'tracking': order.postal_tracking or '—',
        'status_label': EVENT_STATUS_LABELS.get(event, order.get_status_display()),
        'site_name': 'وبسایت رسمی هادی روشن',
    }
    out = text
    for key, val in values.items():
        out = out.replace('{' + key + '}', str(val))
    return out


# متن‌های پیش‌فرض، فقط وقتی قالب ادمین حذف یا خالی شده باشد
DEFAULT_MESSAGES = {
    'paid': (
        '{customer_name} عزیز، سفارش شما {order_code} به مبلغ {total} تومان '
        'با موفقیت تایید و پرداخت شد. همکاران ما به‌زودی برای هماهنگی ارسال با شما تماس می‌گیرند. '
        '— {site_name}'
    ),
    'shipped': (
        '{customer_name} عزیز، سفارش شما {order_code} به مبلغ {total} تومان ارسال شد. '
        'کد رهگیری پستی: {tracking} — پیگیری در 17track.net — {site_name}'
    ),
    'canceled': (
        '{customer_name} عزیز، سفارش شما {order_code} به مبلغ {total} تومان لغو شد. '
        'در صورت پرداخت، مبلغ ظرف ۷۲ ساعت کاری به همان حساب عودت داده می‌شود. '
        '— {site_name}'
    ),
}


def send_sms(phone, message):
    """ارسال پیامک با کاوه‌نگار؛ خروجی: (ok, ref, error)."""
    api_key = getattr(settings, 'KAVENEGAR_API_KEY', '')
    if not api_key:
        return False, '', 'KAVENEGAR_API_KEY تنظیم نشده است'
    to = normalize_phone(phone)
    try:
        resp = requests.get(
            KAVENEGAR_SMS_URL.format(key=api_key),
            params={'receptor': to, 'message': message, 'sender': getattr(settings, 'KAVENEGAR_SENDER', '')},
            timeout=10,
        )
        data = resp.json()
        entries = (data.get('entries') or [])
        ref = str(entries[0].get('messageid')) if entries else ''
        if resp.status_code == 200 and data.get('return', {}).get('status') == 200:
            return True, ref, ''
        return False, ref, data.get('return', {}).get('message') or f'HTTP {resp.status_code}'
    except Exception as exc:  # شبکه/تایم‌اوت — نباید جریان را بشکند
        logger.warning('SMS send failed: %s', exc)
        return False, '', str(exc)


def notify_order_status(order, event, channel='sms'):
    """اطلاع‌رسانی یک رویداد (paid/shipped/canceled). خروجی: NotificationLog ثبت‌شده."""
    if event not in EVENT_STATUS_LABELS:
        event = 'paid'
    message = build_message(order, event=event)
    phone = order.customer_phone

    if channel == 'whatsapp':
        # واتساپ بدون API: لینک آماده wa.me برای ارسال دستی توسط مدیر
        from urllib.parse import quote
        link = f'https://wa.me/{normalize_phone(phone)}?text='
        log = NotificationLog.objects.create(
            order=order, kind=event, channel='whatsapp', phone=normalize_phone(phone),
            message=message, status='manual', provider_ref=link + quote(message),
        )
        return log

    ok, ref, error = send_sms(phone, message)
    return NotificationLog.objects.create(
        order=order, kind=event, channel='sms', phone=normalize_phone(phone),
        message=message,
        status='sent' if ok else 'failed',
        provider_ref=ref, error=error,
    )


def notify_order_paid(order, channel='sms'):
    """سازگاری با کد قبلی: اطلاع‌رسانی تایید پرداخت."""
    return notify_order_status(order, 'paid', channel=channel)


def whatsapp_link(log):
    """لینک wa.me از روی لاگ (برای دکمه داشبورد)."""
    if log.channel == 'whatsapp' and log.provider_ref:
        return log.provider_ref
    return ''
