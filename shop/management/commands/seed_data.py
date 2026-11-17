from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from shop.models import Course

COURSES = [
    ('🐍', 'دوره جامع پایتون', 12_000_000, 15_000_000, 'آموزش صفر تا صد پایتون با بیش از ۱۰۰ ساعت ویدیو آموزشی و پروژه عملی'),
    ('🤖', 'هوش مصنوعی کاربردی', 15_000_000, 18_000_000, 'یادگیری مفاهیم AI و ML با پروژه‌های واقعی و کاربردی در صنعت'),
    ('📊', 'تحلیل داده با پایتون', 12_500_000, 14_000_000, 'آموزش pandas، matplotlib، seaborn و ابزارهای تحلیل داده'),
    ('🧠', 'Deep Learning پیشرفته', 18_000_000, 22_000_000, 'شبکه‌های عصبی، CNN، RNN و پیاده‌سازی مدل‌های پیشرفته یادگیری عمیق'),
    ('🌐', 'وب‌اپلیکیشن با Django', 13_500_000, 16_000_000, 'ساخت اپلیکیشن‌های وب حرفه‌ای با فریم‌ورک قدرتمند جنگو'),
    ('📦', 'پکیج کامل هوش مصنوعی', 25_000_000, 36_000_000, 'مجموعه کامل تمام دوره‌ها با تخفیف ویژه و پشتیبانی دائمی'),
]


class Command(BaseCommand):
    help = 'سید دوره‌های سایت و ساخت کاربر ادمین'

    def add_arguments(self, parser):
        parser.add_argument('--admin-pass', default='hr-admin-1405', help='رمز کاربر ادمین')

    def handle(self, *args, **options):
        for emoji, name, price, old_price, desc in COURSES:
            obj, created = Course.objects.get_or_create(
                name=name,
                defaults={'emoji': emoji, 'price': price, 'old_price': old_price, 'description': desc},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'course added: {name}'))

        User = get_user_model()
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', options['admin_pass'])
            self.stdout.write(self.style.SUCCESS('superuser created (admin)'))
        else:
            self.stdout.write('کاربر ادمین از قبل وجود دارد')
