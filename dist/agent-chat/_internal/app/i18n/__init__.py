from typing import Optional
from starlette.requests import Request
from app.i18n import zh, en

LOCALES = {"zh": zh.STRINGS, "en": en.STRINGS}
DEFAULT_LOCALE = "zh"
COOKIE_NAME = "lang"


def get_locale(request: Optional[Request] = None) -> str:
    if request:
        cookie_lang = request.cookies.get(COOKIE_NAME)
        if cookie_lang in LOCALES:
            return cookie_lang
    return DEFAULT_LOCALE


def t(key: str, locale: str = DEFAULT_LOCALE, **kwargs) -> str:
    strings = LOCALES.get(locale, LOCALES[DEFAULT_LOCALE])
    text = strings.get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text


def get_strings(locale: str) -> dict:
    return LOCALES.get(locale, LOCALES[DEFAULT_LOCALE])
