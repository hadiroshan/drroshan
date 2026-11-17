from django.db import models
from django.utils.text import slugify

# متغیرهای مجاز در قالب پیامک
TEMPLATE_VARIABLES = ['customer_name', 'order_code', 'total', 'tracking', 'status_label', 'site_name']


class Course(models.Model):
    """دوره آموزشی (همان آیتم‌هایی که در صفحه اصلی فروخته می‌شوند)"""

    emoji = models.CharField('ایموجی', max_length=8, default='🎓')
    name = models.CharField('نام دوره', max_length=150, unique=True)
    slug = models.SlugField('نامک', max_length=160, unique=True, allow_unicode=True, blank=True)
    description = models.TextField('توضیحات', blank=True)
    price = models.PositiveIntegerField('قیمت (تومان)', default=0)
    old_price = models.PositiveIntegerField('قیمت قبل از تخفیف (تومان)', null=True, blank=True)
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField('ایجاد', auto_now_add=True)
    updated_at = models.DateTimeField('به‌روزرسانی', auto_now=True)

    class Meta:
        verbose_name = 'دوره'
        verbose_name_plural = 'دوره‌ها'
        ordering = ['price']

    def __str__(self):
        return f'{self.emoji} {self.name}'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)[:155]
        super().save(*args, **kwargs)


class Order(models.Model):
    """سفارش — معادل رکوردهای hr_orders در localStorage نسخه استاتیک"""

    STATUS_CHOICES = [
        ('paid', 'پرداخت شده'),
        ('shipped', 'ارسال شد'),
        ('awaiting_receipt', 'در انتظار تایید رسید'),
        ('awaiting_cod', 'در انتظار پرداخت در محل'),
        ('canceled', 'لغو شده'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('gateway', 'درگاه بانکی'),
        ('card', 'کارت به کارت'),
        ('cod', 'پرداخت در محل'),
    ]

    code = models.CharField('کد سفارش', max_length=16, unique=True, db_index=True)
    status = models.CharField('وضعیت', max_length=20, choices=STATUS_CHOICES, default='awaiting_receipt', db_index=True)

    # اطلاعات مشتری
    customer_name = models.CharField('نام مشتری', max_length=120)
    customer_phone = models.CharField('موبایل', max_length=20)
    customer_national = models.CharField('کد ملی', max_length=20, blank=True)
    customer_email = models.EmailField('ایمیل', blank=True)
    customer_province = models.CharField('استان', max_length=60, blank=True)
    customer_postal = models.CharField('کد پستی', max_length=20, blank=True)
    customer_address = models.TextField('آدرس', blank=True)
    shipping_method = models.CharField('روش ارسال', max_length=80, blank=True)

    # پرداخت
    payment_method = models.CharField('روش پرداخت', max_length=12, choices=PAYMENT_METHOD_CHOICES, default='card')
    payment_card = models.CharField('شماره کارت', max_length=24, blank=True)
    payment_rrn = models.CharField('کد رهگیری (RRN)', max_length=40, blank=True)
    payment_receipt = models.CharField('کد پیگیری رسید کارت به کارت', max_length=60, blank=True)
    postal_tracking = models.CharField('کد رهگیری پستی', max_length=24, blank=True)
    coupon_code = models.CharField('کد تخفیف', max_length=40, blank=True)

    # مبالغ
    subtotal = models.PositiveIntegerField('جمع اقلام (تومان)', default=0)
    discount = models.PositiveIntegerField('تخفیف (تومان)', default=0)
    shipping_cost = models.PositiveIntegerField('هزینه ارسال (تومان)', default=0)
    total = models.PositiveIntegerField('مبلغ کل (تومان)', default=0, db_index=True)

    note = models.TextField('یادداشت مدیر', blank=True)
    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('به‌روزرسانی', auto_now=True)

    class Meta:
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارش‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} — {self.customer_name}'

    # خروجی‌های سازگار با فرانت (همان کلیدهای hr_orders قبلی)
    def as_frontend_dict(self):
        return {
            'code': self.code,
            'date': self.created_at.isoformat(),
            'status': self.get_status_display(),
            'customer': {
                'name': self.customer_name,
                'phone': self.customer_phone,
                'national': self.customer_national,
                'email': self.customer_email,
                'province': self.customer_province,
                'postal': self.customer_postal,
                'address': self.customer_address,
                'shippingMethod': self.shipping_method,
            },
            'payment': {
                'method': self.payment_method,
                'status': self.get_status_display(),
                'card': self.payment_card,
                'rrn': self.payment_rrn,
                'receipt': self.payment_receipt,
                'tracking': self.postal_tracking or None,
            },
            'coupon': self.coupon_code or None,
            'items': [i.as_frontend_dict() for i in self.items.all()],
            'subtotal': self.subtotal,
            'discount': self.discount,
            'shipping': self.shipping_cost,
            'total': self.total,
            'tracking': self.postal_tracking or None,
        }

    def mark_paid(self):
        if self.status in ('awaiting_receipt', 'awaiting_cod'):
            self.status = 'paid'
            self.save(update_fields=['status', 'updated_at'])

    def as_dashboard_dict(self):
        """خروجی مسطح برای داشبورد"""
        d = self.as_frontend_dict()
        d.update({
            'id': self.id,
            'status': self.status,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'customer_national': self.customer_national,
            'customer_email': self.customer_email,
            'customer_province': self.customer_province,
            'customer_postal': self.customer_postal,
            'customer_address': self.customer_address,
            'shipping_method': self.shipping_method,
            'payment_method': self.payment_method,
            'payment_method_label': self.get_payment_method_display(),
            'payment_card': self.payment_card,
            'payment_rrn': self.payment_rrn,
            'payment_receipt': self.payment_receipt,
            'coupon_code': self.coupon_code,
            'shipping_cost': self.shipping_cost,
        })
        return d


class OrderItem(models.Model):
    """اقلام سفارش (پیش‌فرض: دوره‌ها)"""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name='سفارش')
    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.SET_NULL, related_name='order_items', verbose_name='دوره')
    name = models.CharField('نام آیتم', max_length=150)
    emoji = models.CharField('ایموجی', max_length=8, default='🎓')
    price = models.PositiveIntegerField('قیمت واحد (تومان)', default=0)
    qty = models.PositiveSmallIntegerField('تعداد', default=1)

    class Meta:
        verbose_name = 'قلم سفارش'
        verbose_name_plural = 'اقلام سفارش‌ها'
        ordering = ['id']

    def __str__(self):
        return f'{self.name} ×{self.qty}'

    def as_frontend_dict(self):
        return {
            'name': self.name,
            'emoji': self.emoji,
            'price': self.price,
            'qty': self.qty,
        }


class MessageTemplate(models.Model):
    """قالب پیامک اطلاع‌رسانی — قابل ویرایش از پنل ادمین.

    متغیرهای مجاز داخل متن: {customer_name} {order_code} {total}
    {tracking} {status_label} {site_name}
    """

    EVENT_CHOICES = [
        ('paid', 'تایید پرداخت سفارش'),
        ('shipped', 'ارسال سفارش'),
        ('canceled', 'لغو سفارش'),
    ]

    event = models.CharField('رویداد', max_length=20, choices=EVENT_CHOICES, unique=True)
    message = models.TextField(
        'متن پیامک',
        help_text='متغیرهای مجاز: {customer_name} {order_code} {total} {tracking} {status_label} {site_name}',
    )
    is_active = models.BooleanField('فعال', default=True)
    updated_at = models.DateTimeField('به‌روزرسانی', auto_now=True)

    class Meta:
        verbose_name = 'قالب پیامک'
        verbose_name_plural = 'قالب‌های پیامک'

    def __str__(self):
        return self.get_event_display()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        # فقط متغیرهای شناخته‌شده مجازند (با فرم فارسی هم چک می‌شود)
        known = set(TEMPLATE_VARIABLES)
        for i, chunk in enumerate(self.message.split('{')):
            if i == 0 or '}' not in chunk:
                continue
            var = chunk.split('}')[0].strip()
            if var not in known:
                raise ValidationError({'message': f'متغیر «{var}» شناخته‌شده نیست. متغیرهای مجاز: ' + '، '.join(sorted(known))})


class NotificationLog(models.Model):
    """لاگ اطلاع‌رسانی‌های ارسال‌شده به مشتری (پیامک/واتساپ)"""

    CHANNEL_CHOICES = [
        ('sms', 'پیامک'),
        ('whatsapp', 'واتساپ'),
    ]
    STATUS_CHOICES = [
        ('sent', 'ارسال شد'),
        ('failed', 'ناموفق'),
        ('manual', 'لینک دستی'),
    ]
    KIND_CHOICES = [
        ('paid', 'تایید پرداخت'),
        ('shipped', 'ارسال سفارش'),
        ('canceled', 'لغو سفارش'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notifications', verbose_name='سفارش')
    kind = models.CharField('نوع اطلاع‌رسانی', max_length=12, choices=KIND_CHOICES, default='paid')
    channel = models.CharField('کانال', max_length=12, choices=CHANNEL_CHOICES, default='sms')
    phone = models.CharField('شماره مقصد', max_length=20)
    message = models.TextField('متن پیام')
    status = models.CharField('وضعیت', max_length=10, choices=STATUS_CHOICES, default='sent')
    provider_ref = models.CharField('کد پیگیری سرویس', max_length=60, blank=True)
    error = models.TextField('خطا', blank=True)
    created_at = models.DateTimeField('تاریخ ارسال', auto_now_add=True)

    class Meta:
        verbose_name = 'اطلاع‌رسانی'
        verbose_name_plural = 'اطلاع‌رسانی‌ها'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_channel_display()} → {self.phone} ({self.get_status_display()})'
