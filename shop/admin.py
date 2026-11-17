from django.contrib import admin
from django.utils.html import format_html

from .models import Course, MessageTemplate, NotificationLog, Order, OrderItem
from .notifications import notify_order_status

admin.site.site_header = 'مدیریت وب‌سایت دکتر هادی روشن'
admin.site.site_title = 'مدیریت دکتر روشن'
admin.site.index_title = 'پنل مدیریت داده‌ها'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('course', 'name', 'emoji', 'price', 'qty')
    autocomplete_fields = ['course']
    verbose_name = 'قلم سفارش'
    verbose_name_plural = 'اقلام سفارش'


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('emoji_preview', 'name', 'price', 'old_price', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='—')
    def emoji_preview(self, obj):
        return format_html('<span style="font-size:1.3rem">{}</span>', obj.emoji)


class NotificationInline(admin.TabularInline):
    model = NotificationLog
    extra = 0
    fields = ('channel', 'phone', 'status', 'message', 'provider_ref', 'error', 'created_at')
    readonly_fields = fields
    can_delete = False
    verbose_name = 'اطلاع‌رسانی'
    verbose_name_plural = 'تاریخچه اطلاع‌رسانی‌ها'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'customer_name', 'customer_phone', 'items_summary',
        'total', 'payment_badge', 'receipt_preview', 'status_badge', 'created_at_jalali',
    )
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('code', 'customer_name', 'customer_phone', 'customer_national', 'customer_email', 'payment_receipt')
    readonly_fields = ('code', 'created_at', 'updated_at', 'subtotal', 'discount', 'shipping_cost', 'total')
    inlines = [OrderItemInline, NotificationInline]
    date_hierarchy = 'created_at'
    actions = ['mark_paid_action', 'mark_canceled_action', 'notify_paid_action', 'notify_shipped_action', 'notify_canceled_action']
    list_per_page = 25

    fieldsets = [
        ('وضعیت', {'fields': ['status', 'postal_tracking']}),
        ('مشتری', {
            'fields': ['customer_name', 'customer_phone', 'customer_national', 'customer_email',
                       'customer_province', 'customer_postal', 'customer_address', 'shipping_method'],
        }),
        ('پرداخت', {'fields': ['payment_method', 'payment_card', 'payment_rrn', 'payment_receipt', 'coupon_code']}),
        ('اقلام و مبالغ', {'fields': ['subtotal', 'discount', 'shipping_cost', 'total']}),
        ('سایر', {'fields': ['note', 'code', 'created_at', 'updated_at'], 'classes': ['collapse']}),
    ]

    @admin.display(description='اقلام')
    def items_summary(self, obj):
        return '، '.join(f'{i.emoji} {i.name} ×{i.qty}' for i in obj.items.all()[:3]) or '—'

    @admin.display(description='روش پرداخت')
    def payment_badge(self, obj):
        return obj.get_payment_method_display()

    @admin.display(description='کد پیگیری واریز')
    def receipt_preview(self, obj):
        if not obj.payment_receipt:
            return '—'
        return format_html(
            '<code style="direction:ltr">{}</code>', obj.payment_receipt,
        )

    @admin.display(description='وضعیت')
    def status_badge(self, obj):
        colors = {
            'paid': ('#10b981', '#065f46'),
            'shipped': ('#3b82f6', '#1e3a8a'),
            'awaiting_receipt': ('#f59e0b', '#78350f'),
            'awaiting_cod': ('#94a3b8', '#334155'),
            'canceled': ('#ef4444', '#7f1d1d'),
        }
        bg, fg = colors.get(obj.status, ('#94a3b8', '#334155'))
        return format_html(
            '<span style="background:{};color:{};padding:4px 12px;border-radius:999px;font-size:.72rem;font-weight:800;white-space:nowrap">{}</span>',
            bg, fg, obj.get_status_display(),
        )

    @admin.display(description='تاریخ', ordering='created_at')
    def created_at_jalali(self, obj):
        return obj.created_at.strftime('%Y/%m/%d — %H:%M')

    @admin.action(description='علامت‌گذاری به عنوان پرداخت شده')
    def mark_paid_action(self, request, queryset):
        updated = 0
        for order in queryset.filter(status__in=('awaiting_receipt', 'awaiting_cod')):
            order.mark_paid()
            updated += 1
        self.message_user(request, f'{updated} سفارش پرداخت‌شده شد.')

    @admin.action(description='لغو سفارش‌های انتخاب‌شده')
    def mark_canceled_action(self, request, queryset):
        updated = queryset.update(status='canceled')
        self.message_user(request, f'{updated} سفارش لغو شد.')

    def _notify_action(self, request, queryset, event):
        sent, failed, manual = 0, 0, 0
        for order in queryset.filter(status=event):
            log = notify_order_status(order, event, channel='sms')
            if log.status == 'sent':
                sent += 1
            elif log.status == 'manual':
                manual += 1
            else:
                failed += 1
        msg = f'{sent} پیامک ارسال شد'
        if manual:
            msg += f' — {manual} لینک واتساپ دستی'
        if failed:
            msg += f' — {failed} ناموفق (KAVENEGAR_API_KEY را بررسی کنید)'
        self.message_user(request, msg)

    @admin.action(description='اطلاع‌رسانی تایید پرداخت (پیامک)')
    def notify_paid_action(self, request, queryset):
        self._notify_action(request, queryset, 'paid')

    @admin.action(description='اطلاع‌رسانی ارسال سفارش (پیامک)')
    def notify_shipped_action(self, request, queryset):
        self._notify_action(request, queryset, 'shipped')

    @admin.action(description='اطلاع‌رسانی لغو سفارش (پیامک)')
    def notify_canceled_action(self, request, queryset):
        self._notify_action(request, queryset, 'canceled')



@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('order_link', 'kind_badge', 'channel_badge', 'phone', 'status_badge', 'created_at_short')
    list_filter = ('kind', 'channel', 'status', 'created_at')
    search_fields = ('order__code', 'phone', 'message')
    readonly_fields = ('order', 'channel', 'phone', 'message', 'status', 'provider_ref', 'error', 'created_at')
    list_per_page = 25

    @admin.display(description='سفارش')
    def order_link(self, obj):
        return format_html('<a href="/admin/shop/order/{}/change/">{}</a>', obj.order.id, obj.order.code)

    @admin.display(description='نوع')
    def kind_badge(self, obj):
        icons = {'paid': '✅', 'shipped': '📦', 'canceled': '❌'}
        return f"{icons.get(obj.kind, '🔔')} {obj.get_kind_display()}"

    @admin.display(description='کانال')
    def channel_badge(self, obj):
        icon = '✉️' if obj.channel == 'sms' else '💬'
        return f'{icon} {obj.get_channel_display()}'

    @admin.display(description='وضعیت')
    def status_badge(self, obj):
        colors = {'sent': ('#10b981', '#065f46'), 'failed': ('#ef4444', '#7f1d1d'), 'manual': ('#3b82f6', '#1e3a8a')}
        bg, fg = colors.get(obj.status, ('#94a3b8', '#334155'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:999px;font-size:.7rem;font-weight:800">{}</span>',
            bg, fg, obj.get_status_display(),
        )

    @admin.display(description='تاریخ')
    def created_at_short(self, obj):
        return obj.created_at.strftime('%Y/%m/%d — %H:%M')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    """ویرایش قالب پیامک‌های اطلاع‌رسانی از پنل ادمین"""

    list_display = ('event', 'preview', 'is_active', 'updated_at')
    list_editable = ('is_active',)
    fields = ('event', 'message', 'is_active')

    @admin.display(description='پیش‌نمایش متن')
    def preview(self, obj):
        text = (obj.message or '').strip()
        if len(text) > 70:
            text = text[:70] + '…'
        return text or '—'

    def has_add_permission(self, request):
        # هر رویداد فقط یک قالب دارد؛ وقتی همه رویدادها قالب دارند، افزودن جدید بی‌معناست
        return MessageTemplate.objects.count() < len(MessageTemplate.EVENT_CHOICES)

    def has_delete_permission(self, request, obj=None):
        # حذف آزاد است؛ اگر قالب حذف/خالی شود، متن پیش‌فرض داخلی استفاده می‌شود
        return True


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'name', 'price', 'qty')
    list_filter = ('course',)
    search_fields = ('name', 'order__code')
