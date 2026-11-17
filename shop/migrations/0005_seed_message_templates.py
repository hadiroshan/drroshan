from django.db import migrations

TEMPLATES = {
    'paid': (
        '{customer_name} عزیز، سفارش شما {order_code} به مبلغ {total} تومان '
        'با موفقیت تایید و پرداخت شد. همکاران ما به‌زودی برای هماهنگی ارسال با شما تماس می‌گیرند. '
        '— وبسایت رسمی هادی روشن'
    ),
    'shipped': (
        '{customer_name} عزیز، سفارش شما {order_code} به مبلغ {total} تومان ارسال شد. '
        'کد رهگیری پستی: {tracking} — پیگیری در 17track.net'
        ' — وبسایت رسمی هادی روشن'
    ),
    'canceled': (
        '{customer_name} عزیز، سفارش شما {order_code} به مبلغ {total} تومان لغو شد. '
        'در صورت پرداخت، مبلغ ظرف ۷۲ ساعت کاری به همان حساب عودت داده می‌شود. '
        '— وبسایت رسمی هادی روشن'
    ),
}


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model('shop', 'MessageTemplate')
    for event, text in TEMPLATES.items():
        MessageTemplate.objects.get_or_create(event=event, defaults={'message': text})


def unseed(apps, schema_editor):
    MessageTemplate = apps.get_model('shop', 'MessageTemplate')
    MessageTemplate.objects.filter(event__in=TEMPLATES.keys()).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('shop', '0004_messagetemplate_notificationlog_kind'),
    ]
    operations = [
        migrations.RunPython(seed, unseed),
    ]
