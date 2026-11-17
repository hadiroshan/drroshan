"""ابزارهای کوچک فارسی‌سازی برای پیام‌ها."""

FA_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')


def fa_number(n):
    return f'{int(n):,}'.translate(FA_DIGITS)


def fa_money(n):
    return fa_number(n)
