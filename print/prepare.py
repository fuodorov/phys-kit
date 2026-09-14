#!/usr/bin/env python3
"""Готовит markdown книги к вёрстке печатного пособия.

Собирает главы в порядке SUMMARY.md, приводит уровни заголовков,
вычищает интерактивный HTML (Plotly, pandas-таблицы), извлекает
картинки из base64 и переводит SVG в PDF для XeLaTeX.
"""
import base64
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from index_terms import TERMS as INDEX_TERMS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
BUILD = os.path.join(ROOT, "print", "build")
IMG = os.path.join(BUILD, "img")

# --- Что именно уходит из печатного издания -------------------------
# Электронная версия остаётся полной; здесь описано только то, чем
# книжное издание отличается от неё.

WEB = "https://phys-dev.github.io/soft-dev-book/"

# --- Издание выходит одной книгой ---------------------------------
# Раньше книга делилась на «Теорию» и «Практику», но разделение рвало
# зависимости: главы про ускорение опираются на NumPy, а он оказывался
# в другом томе. Оставлен один том, и порядок частей отвечает порядку
# чтения.
VOLUMES = {
    None: {
        "title": "",
        "parts": None,          # None означает «все части подряд»
        "abstract": (
            "Пособие посвящено разработке программ, результатам которых "
            "можно доверять при обработке физического эксперимента. Главы "
            "выстроены так, что каждая опирается на предыдущие: помощники "
            "на языковых моделях и контроль версий, GNU/Linux и контейнеры, "
            "устройство языка Python, алгоритмы и структуры данных, "
            "инженерные практики от требований к коду до баз данных, "
            "обработка и визуализация данных, машинное обучение, ускорение "
            "расчётов вплоть до графических ускорителей. Завершают книгу "
            "разбор программ, применяемых для расчётов в институтах СО РАН, "
            "и задания для самостоятельной работы. От общего курса "
            "программирования пособие отличается материалом: вместо учебных "
            "примеров рассматриваются работающие коды установок."),
    },
}

# Главы, дословно дублирующие материал других разделов.
# Экспресс-курс по Python пересказывает темы разделов «Погружаемся
# в Python» и «Обрабатываем данные», поэтому в книге его нет.
# Приложение с экспресс-курсом остаётся только в электронной версии:
# основы языка, NumPy и Matplotlib разобраны в книге полными главами,
# а здесь дан беглый справочник для тех, кто Python не знает вовсе.
SKIP = {
    "./dev/python/basics.md",
    "./dev/python/numpy.md",
    "./dev/python/matplotlib.md",
}
SKIP_PARTS = {"Приложение. Экспресс-курс"}

# Выгрузки из Jupyter: печатаем текст, формулы и короткие фрагменты,
# длинные листинги заменяем началом кода и ссылкой на сайт.
NOTEBOOKS = {
    "./examples/kenv.md",
    "./examples/redpic.md",
    "./examples/envelope-optimize.md",
    "./examples/cadquery/layout.md",
    "./dev/python/numpy-and-pandas.md",
}

# Разделы, вырезаемые целиком. Сейчас таких нет: интерактивные графики
# на бумаге не показать, но резать из-за этого раздел не стоит — код,
# которым график строится, проза вокруг него и статические иллюстрации
# на бумаге работают.
DROP_SECTIONS = {}

# Сколько разобранных задач оставить в главе (остальные — списком).
KEEP_TASKS = {"./cs/trees.md": 2, "./cs/graphs.md": 2}

# Практикум печатаем кратко: постановка задачи и ссылка на сайт.
BRIEF = {"./practicum/"}
# Вводная глава практикума — не задание: сокращать в ней нечего,
# а brief_practicum склеил бы абзацы и дописал строку про критерии приёмки.
BRIEF_SKIP = {"./practicum/intro.md"}

# Пределы для листингов и распечаток
# Порог сокращения вывода программ. Поднят так, чтобы проходили осмысленные
# таблицы на десяток-полтора строк; режется только то, что и в блокноте
# читать невозможно, вроде стострочной выгрузки координат элементов.
OUTPUT_LIMIT, OUTPUT_LIMIT_NB = 25, 20



def _ru_count(n):
    """Хвост фразы о числе сокращённых распечаток, согласованный по числу.

    Примечание идёт в оба тома, а распечаток в них разное количество,
    поэтому число считается по собранному тому, а не пишется руками.
    """
    words = {1: "одно", 2: "два", 3: "три", 4: "четыре", 5: "пять",
             6: "шесть", 7: "семь", 8: "восемь", 9: "девять"}
    if n == 0:
        return ", но в этой части их не встретилось"
    if n == 1:
        return ", и в этой части оно одно"
    return f", и в этой части их {words.get(n, str(n))}"


def parse_summary():
    """Возвращает список элементов оглавления: (тип, заголовок, путь, уровень)."""
    path = os.path.join(SRC, "SUMMARY.md")
    items = []
    for line in io.open(path, encoding="utf-8"):
        part = re.match(r"^# (.+)$", line.strip())
        if part:
            items.append(("part", part.group(1).strip(), None, 0))
            continue
        link = re.match(r"^(\s*)[-*] \[([^\]]+)\]\((\./[^)]+)\)", line)
        if link:
            level = len(link.group(1)) // 2
            items.append(("chapter", link.group(2), link.group(3), level))
            continue
        front = re.match(r"^\[([^\]]+)\]\((\./[^)]+)\)", line.strip())
        if front:
            # до первой части — вводные страницы, после — заключительные
            kind = "back" if any(i[0] == "part" for i in items) else "front"
            items.append((kind, front.group(1), front.group(2), 0))
    return items


def _strip_html_chunk(text):
    """Убирает интерактивный HTML из куска текста вне листингов."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.S)
    text = re.sub(r"<div>\s*(<table.*?</table>)\s*</div>", _table_to_md,
                  text, flags=re.S)
    text = re.sub(r"<table.*?</table>", _table_to_md_raw, text, flags=re.S)
    text = re.sub(r"</?div[^>]*>", "", text)
    text = re.sub(r"^\s*window\..*$", "", text, flags=re.M)
    text = re.sub(r"^\s*require\(\[.*$", "", text, flags=re.M)
    text = re.sub(r"^\s*if \(window\.MathJax.*$", "", text, flags=re.M)
    return text


def strip_html(text):
    """Убирает интерактивный HTML: скрипты Plotly, стили, pandas-таблицы.

    Обрабатываем только куски вне листингов. Иначе «ленивая» регулярка,
    наткнувшись на непарный HTML-тег, перепрыгивает через код-блок
    и уносит его вместе с ограждениями — а дальше рушится вся разметка.
    """
    parts, chunk, in_fence = [], [], False
    for line in text.split("\n"):
        if line.startswith("```"):
            if not in_fence:
                parts.append(_strip_html_chunk("\n".join(chunk)))
                chunk = []
            else:
                parts.append("\n".join(chunk))
                chunk = []
            parts.append(line)
            in_fence = not in_fence
            continue
        chunk.append(line)
    parts.append("\n".join(chunk) if in_fence else _strip_html_chunk("\n".join(chunk)))
    return "\n".join(parts)


MAX_CELL = 15


def _cells(row):
    """Содержимое ячеек строки таблицы; длинные значения обрезаем.

    В выводах pandas попадаются ячейки в сотни символов. На полосе А4
    шириной 170 мм шесть колонок дают по 24.8 мм каждой, и в Times 10 pt
    (footnotesize при кегле 12) туда влезает 15 знаков.
    """
    out = []
    for cell in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, flags=re.S):
        text = re.sub(r"<[^>]+>", "", cell).strip()
        text = re.sub(r"\s+", " ", text)
        if len(text) > MAX_CELL:
            text = text[:MAX_CELL - 1] + "…"
        out.append(text.replace("|", r"\|"))
    return out


def _table_html_to_md(html, max_rows=12, max_cols=6):
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S)
    if not rows:
        return ""
    parsed = [_cells(r) for r in rows]
    parsed = [p for p in parsed if p]
    if not parsed:
        return ""
    width = min(max(len(p) for p in parsed), max_cols)
    truncated = len(parsed) > max_rows + 1
    head, body = parsed[0], parsed[1:max_rows + 1]
    head = (head + [""] * width)[:width]
    out = ["", "| " + " | ".join(head) + " |",
           "|" + "|".join(["---"] * width) + "|"]
    for row in body:
        row = (row + [""] * width)[:width]
        out.append("| " + " | ".join(row) + " |")
    if truncated:
        out.append("")
        out.append("*(таблица приведена частично)*")
    out.append("")
    return "\n".join(out)


def _table_to_md(match):
    return _table_html_to_md(match.group(1))


def _table_to_md_raw(match):
    return _table_html_to_md(match.group(0))


def _too_small(data, limit=200):
    """Правда ли, что растр меньше limit пикселей по обеим сторонам.

    В выводе блокнотов попадаются логотипы библиотек размером 32x32 и
    64x64. Как иллюстрации они бессмысленны, а на полосе А5 растягиваются
    на треть страницы и выглядят мутным пятном.
    """
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return len(data) < 3000
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width < limit and height < limit


JUNK_ALT = re.compile(r"^(png|jpe?g|svg|image|output|рис\.?|figure)?[\s._-]*"
                      r"[\w.\-]*\.(png|jpe?g|svg|gif)$|^(png|jpe?g|svg)$",
                      re.I)


def clean_alt(text):
    """Убирает бессмысленные подписи к рисункам.

    Блокноты подставляют в alt имя формата или файла, и в печати это даёт
    подписи вида «Рис. 1.2: png» и «Рис. 2.5: 1_Event_Loop_1629282397.png».
    Пустой alt pandoc печатает без подписи — так и нужно.
    """
    return re.sub(r"!\[([^\]]*)\]\(",
                  lambda m: "![](" if JUNK_ALT.match(m.group(1).strip()) else m.group(0),
                  text)


def extract_base64_images(text, prefix):
    """Сохраняет base64-картинки из <img> в файлы, возвращает markdown-ссылки.

    Встречаются и png, и svg+xml (графики HoloViews); svg сразу переводим в pdf.
    """
    def repl(match):
        mime, payload = match.group(1), match.group(2)
        try:
            data = base64.b64decode(re.sub(r"\s+", "", payload))
        except Exception:
            return ""
        digest = hashlib.md5(data).hexdigest()[:10]
        if "svg" in mime:
            svg = os.path.join(IMG, f"{prefix}-{digest}.svg")
            with open(svg, "wb") as f:
                f.write(data)
            name = f"{prefix}-{digest}.pdf"
            try:
                subprocess.run(["rsvg-convert", "-f", "pdf", "-o",
                                os.path.join(IMG, name), svg],
                               check=True, capture_output=True)
            except subprocess.CalledProcessError:
                return ""
            finally:
                os.remove(svg)
        else:
            ext = "png" if "png" in mime else "jpg"
            if _too_small(data):
                return ""     # логотип библиотеки из вывода блокнота
            name = f"{prefix}-{digest}.{ext}"
            with open(os.path.join(IMG, name), "wb") as f:
                f.write(data)
        return f"\n\n![](img/{name})\n\n"

    pattern = (r"""<img[^>]*src=['"]data:image/"""
               r"""(png|jpeg|jpg|svg\+xml);base64,\s*([^'"]+)['"][^>]*/?>""")
    return re.sub(pattern, repl, text, flags=re.S)


def convert_svg(svg_path):
    """Переводит SVG в PDF для XeLaTeX, возвращает имя файла."""
    name = hashlib.md5(svg_path.encode()).hexdigest()[:10] + ".pdf"
    out = os.path.join(IMG, name)
    if not os.path.exists(out):
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", out, svg_path],
                       check=True, capture_output=True)
    return name


def fix_images(text, chapter_dir):
    """Приводит пути картинок к каталогу сборки, конвертирует SVG."""
    def repl(match):
        alt, target = match.group(1), match.group(2).strip()
        if target.startswith("http"):
            return ""                      # внешние картинки в печать не берём
        path = os.path.normpath(os.path.join(chapter_dir, target))
        if target.startswith("img/") and not os.path.exists(path):
            return match.group(0)          # уже лежит в каталоге сборки
        if not os.path.exists(path):
            return ""
        if path.lower().endswith(".svg"):
            try:
                return f"![{alt}](img/{convert_svg(path)})"
            except subprocess.CalledProcessError:
                return ""
        if path.lower().endswith(".gif"):
            return ""                      # анимацию не печатаем
        name = hashlib.md5(path.encode()).hexdigest()[:10] + os.path.splitext(path)[1]
        dst = os.path.join(IMG, name)
        if not os.path.exists(dst):
            shutil.copy(path, dst)
        return f"![{alt}](img/{name})"

    return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", repl, text)


def fix_math(text):
    """Приводит формулы mdbook к обычному TeX.

    1. \\( \\) -> $ $, \\[ \\] -> $$ $$. Пробелы внутри долларов убираем:
       pandoc не считает формулой конструкцию вида "$ x $".
    2. Убираем вложенные окружения equation внутри $$ ... $$ — MathJax это
       терпит, а LaTeX считает ошибкой.
    """
    text = re.sub(r"\\\\\((.+?)\\\\\)",
                  lambda m: "$" + m.group(1).strip() + "$", text, flags=re.S)
    text = re.sub(r"\\\\\[(.+?)\\\\\]",
                  lambda m: "\n$$" + m.group(1).strip() + "$$\n", text, flags=re.S)

    def unwrap(match):
        body = match.group(1)
        body = re.sub(r"\\(?:begin|end)\{equation\*?\}", "", body)
        body = re.sub(r"\\(?:begin|end)\{align\*?\}", "", body)
        # пустая строка внутри $$ разрывает формулу — pandoc видит новый абзац
        body = re.sub(r"\n\s*\n+", "\n", body)
        return "$$" + body.strip("\n") + "$$"

    return re.sub(r"\$\$(.+?)\$\$", unwrap, text, flags=re.S)


def fix_unicode(text):
    """Готовит текст к печати: убирает эмодзи и чинит символы вне шрифта.

    В печатном издании эмодзи не нужны (их нет в Times New Roman), а
    математические знаки, набранные в прозе как обычные символы, нужно
    перевести в формулы — иначе XeLaTeX их не найдёт.
    """
    # эмодзи и декоративные пиктограммы
    emoji = ("[\U0001F000-\U0001FAFF\U00002600-\U000027BF"
             "\U0001F1E6-\U0001F1FF\U0000FE0F\U00002B00-\U00002BFF]")
    # только пробелы и табуляции: \s съел бы перевод строки, и следующая
    # строка приклеилась бы к предыдущей — так ломались ограждения кода
    text = re.sub(emoji + r"[ \t]*", "", text)

    # одиночные математические знаки в прозе -> формулы
    def to_math(match):
        return "$\\" + {"∈": "in", "∉": "notin", "≈": "approx", "≤": "le",
                       "≥": "ge", "≠": "ne", "→": "to", "∞": "infty"}[match.group(0)] + "$"

    parts, out, in_fence = text.split("\n"), [], False
    for line in parts:
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and not line.startswith("    "):
            line = re.sub(r"[∈∉≈≤≥≠→∞]", to_math, line)
        out.append(line)
    text = "\n".join(out)

    # Голая кириллица внутри формул -> \text{...}.
    # Ищем формулы строго построчно и только вне листингов: иначе
    # доллары из shell-переменных ($PWD, $PATH) в разных код-блоках
    # спариваются между собой, и целые абзацы прозы уезжают в \text{}.
    def _wrap_body(body):
        pieces = re.split(r"(\\text\{[^{}]*\})", body)
        return "".join(q if q.startswith("\\text{")
                       else re.sub(r"[А-Яа-яЁё]+", r"\\text{\g<0>}", q)
                       for q in pieces)

    def wrap_cyrillic_dd(match):
        return "$$" + _wrap_body(match.group(1)) + "$$"

    def wrap_cyrillic_d(match):
        return "$" + _wrap_body(match.group(1)) + "$"

    # Куски вне листингов обрабатываем поабзацно. Это ключевая
    # предосторожность: если искать формулы по всему тексту, доллары
    # из shell-переменных ($PWD, $PATH) в разных код-блоках спариваются
    # между собой, и целые абзацы прозы уезжают внутрь \\text{}.
    def wrap_para(para):
        para = re.sub(r"\$\$(.+?)\$\$", wrap_cyrillic_dd, para, flags=re.S)
        return re.sub(r"(?<!\$)\$([^$\n]+?)\$(?!\$)", wrap_cyrillic_d, para)

    out, chunk, in_fence = [], [], False
    for line in text.split("\n"):
        if line.startswith("```"):
            if not in_fence:
                out.append(_apply_paragraphs("\n".join(chunk), wrap_para))
            else:
                out.append("\n".join(chunk))
            chunk = []
            out.append(line)
            in_fence = not in_fence
            continue
        chunk.append(line)
    tail = "\n".join(chunk)
    out.append(tail if in_fence else _apply_paragraphs(tail, wrap_para))
    return "\n".join(out)


def _apply_paragraphs(text, fn):
    """Применяет fn к каждому абзацу отдельно, сохраняя пустые строки."""
    parts = re.split(r"(\n[ \t]*\n)", text)
    return "".join(p if i % 2 else fn(p) for i, p in enumerate(parts))


# ссылки, текст которых без адреса ничего не значит на бумаге
VAGUE_LINKS = {"здесь", "тут", "сюда", "ссылка", "по ссылке", "here",
               "link", "этой ссылке", "документация", "docs", "репозиторий"}


def fix_links(text):
    """Приводит ссылки к виду, пригодному для бумаги.

    На бумаге по ссылке не кликнешь, поэтому:

    * относительные ссылки на другие главы заменяем их названием —
      искать всё равно придётся по оглавлению;
    * в справочных разделах («Полезные ссылки», «Литература») адрес
      печатаем прямо в строке — это и есть список источников;
    * ссылки внутри текста уводим в подстрочную сноску, чтобы адрес
      не разрывал фразу, но и не потерялся.
    """
    REF_HEADS = ("полезные ссылки", "ресурсы", "литература", "полезные материалы",
                 "что почитать", "источники", "полезное")

    out, in_fence, in_refs = [], False, False
    for line in text.split("\n"):
        if line.startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        head = re.match(r"^(#{1,6}) +(.*)$", line)
        if head and not in_fence:
            in_refs = head.group(2).strip().lower().rstrip(":").startswith(REF_HEADS)
        if in_fence or line.startswith("    "):
            out.append(line)
            continue

        def repl(match):
            title, target = match.group(1), match.group(2)
            if not target.startswith("http"):
                return title                      # ссылка на главу книги
            if target in title:
                return title                      # адрес и так виден
            if in_refs:
                return f"{title}\x01{target}\x02"   # адрес переставим в конец строки
            if title.strip().lower().strip(".,:;") in VAGUE_LINKS:
                return f"{title} — {target}"
            return f"{title}^[{target}]"          # сноска в тексте

        new_line = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)", repl, line)
        # в списке источников адрес ставим в конец: «Название — описание. URL: …»
        if "\x01" in new_line:
            urls = re.findall(r"\x01(.*?)\x02", new_line)
            new_line = re.sub(r"\x01.*?\x02", "", new_line).rstrip()
            tail = "" if new_line.endswith((".", "!", "?", ":", ";")) else "."
            new_line = new_line + tail + " URL: " + ", ".join(urls)
        out.append(new_line)
    return "\n".join(out)


def _split_fences(text):
    """Разбивает текст на пары (внутри_листинга, строка)."""
    in_fence = False
    for line in text.split("\n"):
        if line.startswith("```"):
            in_fence = not in_fence
            yield True, line
            continue
        yield in_fence, line


def shift_headings(text, base):
    """Сдвигает заголовки главы так, чтобы верхний стал уровня base.

    Строки внутри листингов не трогаем: там решётка — комментарий.
    """
    levels = [len(m.group(1))
              for inf, l in _split_fences(text) if not inf
              for m in [re.match(r"^(#{1,6}) ", l)] if m]
    if not levels:
        return text
    shift = base - min(levels)
    if shift == 0:
        return text
    out = []
    for inf, line in _split_fences(text):
        if not inf:
            m = re.match(r"^(#{1,6}) ", line)
            if m:
                lvl = min(len(m.group(1)) + shift, 6)
                line = "#" * max(lvl, 1) + " " + line[m.end():]
        out.append(line)
    return "\n".join(out)


def strip_manual_numbering(text):
    """Убирает ручную нумерацию из заголовков.

    В электронной версии заголовки не нумеруются автоматически, поэтому
    «1. Процессы», «2. Планировщик» читаются как список. В книге разделы
    нумерует LaTeX, и такой заголовок превращается в «2.3.2 1. Процессы» —
    номер задваивается.
    """
    out = []
    for inf, line in _split_fences(text):
        if not inf:
            line = re.sub(r"^(#{2,6}) +\d+(?:\.\d+)*\.? +(?=\S)", r"\1 ", line)
        out.append(line)
    return "\n".join(out)


def drop_sections(text, titles):
    """Вырезает разделы вместе с их содержимым — до заголовка того же уровня."""
    for title in titles:
        lines, out, killing, level = text.split("\n"), [], False, 0
        in_fence = False
        for line in lines:
            if line.startswith("```"):
                in_fence = not in_fence
            # решётка внутри листинга — это комментарий, а не заголовок
            m = None if in_fence else re.match(r"^(#{1,6}) +(.*)$", line)
            if m:
                if killing and len(m.group(1)) <= level:
                    killing = False
                if not killing and title.lower() in m.group(2).lower():
                    killing, level = True, len(m.group(1))
                    out.append(f"{m.group(1)} {m.group(2)}")
                    out.append("")
                    out.append("Интерактивные графики на бумаге показать нельзя — "
                               f"этот раздел целиком есть в электронной версии: {WEB}")
                    out.append("")
                    continue
            if not killing:
                out.append(line)
        text = "\n".join(out)
    return text


def keep_first_tasks(text, keep):
    """Оставляет разбор первых задач, остальные перечисляет условиями."""
    parts = re.split(r"^(### Задача \d+\..*)$", text, flags=re.M)
    if len(parts) < 3:
        return text
    head, rest = parts[0], parts[1:]
    pairs = [(rest[i], rest[i + 1]) for i in range(0, len(rest) - 1, 2)]
    out = [head]
    dropped = []
    for i, (title, body) in enumerate(pairs):
        if i < keep:
            out.append(title)
            out.append(body)
            continue
        # у остальных задач сохраняем только условие
        m = re.search(r"\*\*Условие\.\*\*(.+?)(?:\n\n|\Z)", body, re.S)
        cond = " ".join(m.group(1).split()) if m else ""
        dropped.append((title.replace("### ", "").strip(), cond))
    if dropped:
        # хвост главы (резюме и т.п.) не теряем
        tail = ""
        m = re.search(r"^## .*$", pairs[-1][1], flags=re.M)
        if m:
            tail = pairs[-1][1][m.start():]
        out.append("### Задачи для самостоятельного решения\n")
        out.append("Разбор этих задач с кодом и оценкой сложности есть "
                   f"в электронной версии: {WEB}\n")
        for title, cond in dropped:
            out.append(f"**{title}.** {cond}\n")
        if tail:
            out.append(tail)
    return "\n".join(out)


def brief_practicum(text, max_items=8):
    """Оставляет от задания суть: заголовок, постановку и обе ссылки.

    Развёрнутые требования, критерии приёмки и форматы отчёта живут
    на сайте — в книге от задания нужна формулировка, чтобы студент
    понял, о чём речь, и пошёл за подробностями. Адрес репозитория
    с заготовкой печатается полностью: на бумаге ссылка не кликается,
    зато набирается.
    """
    lines = text.split("\n")
    head = lines[0] if lines and lines[0].startswith("# ") else ""
    body, items, in_fence, repo = [], 0, False, ""
    deliver = []          # раздел «Что сдавать» печатаем целиком
    in_deliver = False
    for line in lines[1:]:
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        head_match = re.match(r"^(#{2,6}) (.+)$", line)
        if head_match:
            # рубрики задания не печатаем, кроме одной: без неё студент
            # не знает, что считается выполненным, а прежний отсыл
            # «подробности на сайте» ни на что не указывал.
            # Флаг переключаем только на втором уровне: внутри раздела
            # бывают подрубрики, и они не должны его сбрасывать.
            if len(head_match.group(1)) == 2:
                in_deliver = head_match.group(2).strip().startswith("Что сдавать")
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("- ", "* ", "+ ")) or re.match(r"^\d+\.", stripped):
            # сохраняем вложенность: иначе подпункты становятся
            # отдельными требованиями и смысл списка ломается
            indent = len(line) - len(line.lstrip())
            if not in_deliver:
                if indent == 0:
                    items += 1
                    if items > max_items:
                        continue
                elif items > max_items:
                    continue
            pad = "    " * min(indent // 2, 2)
            (deliver if in_deliver else body).append(
                pad + "* " + re.sub(r"^([-*+]|\d+\.)\s*", "", stripped))
        elif "github.com/" in stripped and "Опирается" not in stripped:
            # адрес репозитория с материалами печатаем как текст: перейти
            # по ссылке с бумаги нельзя, а набрать её руками можно.
            # К этому месту fix_links уже превратил ссылку в сноску
            # «текст^[адрес]», поэтому ловим обе формы записи.
            found = re.search(r"(?:\]\(|\^\[)(https?://[^)\]]+)", stripped)
            if found:
                repo = found.group(1)
            continue
        elif items == 0:
            body.append(stripped)
    out = [head, ""] if head else []
    out.extend(body)
    if deliver:
        out.append("")
        out.append("**Что сдавать.**")
        out.append("")
        out.extend(deliver)
    out.append("")
    if repo:
        out.append(f"Репозиторий задания: {repo}")
        out.append("")          # иначе обе ссылки слипнутся в один абзац
    out.append("Постоянно обновляемая версия задания — "
               f"в электронном издании: {WEB}")
    out.append("")
    return "\n".join(out)


def _index_key(entry):
    """Готовит статью указателя к вставке в LaTeX.

    Подчёркивание, амперсанд и решётка в тексте LaTeX — служебные знаки.
    Если они есть, печатаем экранированный вариант, а сортируем по
    очищенному: «slots@\\texttt{\\_\\_slots\\_\\_}».
    """
    if not re.search(r"[_&#%{}]", entry):
        return entry
    parts = entry.split("!")
    out = []
    for part in parts:
        sort = re.sub(r"[_&#%{}]", "", part)
        shown = part
        for ch in "_&#%":
            shown = shown.replace(ch, "\\" + ch)
        out.append(f"{sort}@\\texttt{{{shown}}}")
    return "!".join(out)


def _index_candidates(text):
    """Находит места, где можно поставить метку указателя.

    Возвращает список (номер строки, позиция, длина, термин, качество).
    Качество: 0 — заголовок, 1 — полужирное выделение, 2 — обычная проза.
    Строки таблиц, листингов и пункты списков со ссылками пропускаем:
    там термин лишь перечислен, а не введён.
    """
    res, in_fence = [], False
    for n, line in enumerate(text.split("\n")):
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or line.startswith("    ") or line.lstrip().startswith("|"):
            continue
        is_head = line.lstrip().startswith("#")
        is_item = bool(re.match(r"^\s*([-*+]|\d+\.)\s", line))
        if is_item and "](" in line:
            continue          # перечисление глав, а не определение
        # в заголовке сравниваем сам текст: уровень к этому моменту уже
        # сдвинут, и шаблон «## Термин» иначе поймает «### Терминал»
        hay = line.lstrip("#").strip() if is_head else line
        for entry, variants in INDEX_TERMS.items():
            for v in variants:
                needle = v.lstrip("#").strip() if is_head else v
                pos = hay.find(needle)
                if pos < 0 or hay.count("`", 0, pos) % 2:
                    continue
                # латинские названия в русском тексте не склоняются, так что
                # «Git» не должен срабатывать внутри «GitHub»
                tail = hay[pos + len(needle):pos + len(needle) + 1]
                if needle[-1:].isascii() and needle[-1:].isalnum() and \
                        tail.isascii() and tail.isalnum():
                    continue
                pos += len(line) - len(hay) if is_head else 0
                v = needle
                if is_head:
                    quality = 0
                elif line.count("**", 0, pos) % 2 or line[max(0, pos - 2):pos] == "**":
                    quality = 1
                else:
                    quality = 2
                res.append((n, pos, len(v), entry, quality))
                break
    return res


def add_index_entries(text, seen, only_definitions=False):
    """Расставляет метки предметного указателя.

    Термин отмечается там, где книга его вводит: в заголовке или
    в полужирном выделении. На проходные упоминания в прозе метка
    ставится только вторым проходом и только если места получше не
    нашлось. Каждый термин отмечается не более двух раз, иначе
    указатель превращается в перечень всех страниц подряд.
    """
    picked = {}
    for n, pos, ln, entry, quality in _index_candidates(text):
        if only_definitions and quality == 2:
            continue
        if not only_definitions and seen.get(entry, 0):
            # определение уже нашлось — проходные упоминания не нужны
            continue
        if seen.get(entry, 0) + len(picked.get(entry, [])) >= 2:
            continue
        picked.setdefault(entry, []).append((n, pos, ln, quality))
    marks = {}
    for entry, places in picked.items():
        for n, pos, ln, quality in places:
            marks.setdefault(n, []).append((pos, ln, entry))
            seen[entry] = seen.get(entry, 0) + 1
    lines = text.split("\n")
    for n, items in marks.items():
        line = lines[n]
        for pos, ln, entry in sorted(items, reverse=True):
            mark = "\\index{" + _index_key(entry) + "}"
            if line.lstrip().startswith("#"):
                line = line + mark
                continue
            end = pos + ln
            for wrap in ("**", "*", "`"):
                if line[end:end + len(wrap)] == wrap:
                    end += len(wrap)
                    break
            line = line[:end] + mark + line[end:]
        lines[n] = line
    return "\n".join(lines)


def clean_output_blocks(text, limit=8):
    """Ограничивает длину распечаток — в книге они съедают страницы."""
    lines, out, buf = text.split("\n"), [], []

    def flush():
        if not buf:
            return
        if len(buf) > limit + 2:
            out.extend(buf[:limit])
            out.append("    ... (вывод сокращён)")
        else:
            out.extend(buf)
        buf.clear()

    in_fence = False
    for line in lines:
        if line.startswith("```"):
            flush()
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence and line.startswith("    ") and line.strip():
            buf.append(line)
            continue
        flush()
        out.append(line)
    flush()
    return "\n".join(out)


def drop_empty_code_blocks(text):
    """Выбрасывает блоки кода, в которых нет ни одной непустой строки.

    Пустая ячейка, оставшаяся в конце блокнота, выгружается в markdown
    открывающей и закрывающей строкой ```python без единой строки между
    ними: на сайте её почти не видно, а на полосе набора она превращается
    в серый прямоугольник ни о чём.
    """
    lines, out = text.split("\n"), []
    i = 0
    while i < len(lines):
        if not lines[i].startswith("```"):
            out.append(lines[i])
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not lines[j].startswith("```"):
            j += 1
        if j < len(lines) and not any(s.strip() for s in lines[i + 1:j]):
            i = j + 1
            # не оставляем на месте блока две пустые строки подряд
            if out and not out[-1].strip() and i < len(lines) \
                    and not lines[i].strip():
                i += 1
            continue
        out.extend(lines[i:j + 1])
        i = j + 1
    return "\n".join(out)


def main(volume=None):
    """Готовит markdown одного тома (или всей книги, если volume=None)."""
    os.makedirs(IMG, exist_ok=True)
    index_seen = {}          # сколько раз термин уже отмечен в этом томе
    wanted = VOLUMES[volume]["parts"] if volume else None
    parts = []
    chapter_slots = []
    stats = []
    keep = wanted is None
    for kind, title, path, level in parse_summary():
        if kind == "part":
            keep = (wanted is None or title in wanted) and title not in SKIP_PARTS
            if keep:
                parts.append(f"\n\n# {title}\n\n")
            continue
        if not keep and kind not in ("front", "back"):
            continue
        if path is None or path in SKIP:
            continue
        full = os.path.normpath(os.path.join(SRC, path[2:]))
        if not os.path.exists(full):
            print(f"  пропуск (нет файла): {path}", file=sys.stderr)
            continue
        text = io.open(full, encoding="utf-8").read()
        before = len(text)
        text = strip_html(text)
        text = extract_base64_images(text, os.path.basename(full)[:-3])
        text = fix_images(text, os.path.dirname(full))
        text = clean_alt(text)
        text = fix_math(text)
        text = fix_unicode(text)
        text = fix_links(text)
        # --- сокращения книжного издания ---
        is_nb = path in NOTEBOOKS
        if path in DROP_SECTIONS:
            text = drop_sections(text, DROP_SECTIONS[path])
        if path in KEEP_TASKS:
            text = keep_first_tasks(text, KEEP_TASKS[path])
        if any(path.startswith(b) for b in BRIEF) and path not in BRIEF_SKIP:
            text = brief_practicum(text)
        # листинги печатаем целиком: обрезка теряла существенные детали,
        # а на формате А4 место под них есть
        text = clean_output_blocks(
            text, OUTPUT_LIMIT_NB if is_nb else OUTPUT_LIMIT)
        text = drop_empty_code_blocks(text)
        text = strip_manual_numbering(text)
        # уровень: front-matter и главы верхнего уровня -> ##, вложенные -> ###
        text = shift_headings(text, 2 + level)
        if kind in ("front", "back"):
            # «О книге» и «О себе» идут до частей, «Заключение» и
            # «Литература» — после. Уровень главы, чтобы в оглавлении они
            # стояли вровень с частями и с предметным указателем, а не
            # выглядели разделом последней части. Без {.unnumbered} pandoc
            # заводит фантомную главу 0 и всё их содержимое попадает
            # в оглавление как 0.0.1.
            lines, first = [], True
            in_fence = False
            for line in text.split("\n"):
                if line.startswith("```"):
                    in_fence = not in_fence
                elif not in_fence and re.match(r"^#+ ", line):
                    if first:
                        line, first = f"# {title} {{.unnumbered}}", False
                    else:
                        # подзаголовки вводных страниц в оглавление не выносим
                        line = re.sub(r"^#+ (.*)$",
                                      r"### \1 {.unnumbered .unlisted}", line)
                lines.append(line)
            text = "\n".join(lines)
        if kind == "chapter":
            # во вводных и заключительных страницах термины только
            # перечислены — отмечать их в указателе незачем
            chapter_slots.append(len(parts))
        parts.append(text.strip() + "\n\n")
        stats.append((path, before, len(text)))

    # Разметка указателя идёт двумя проходами по всей книге: сперва
    # заголовки и полужирные выделения, то есть места, где термин вводят,
    # и только затем — обычная проза для тех терминов, которым места
    # получше не нашлось. Иначе ссылка ведёт на первое попавшееся
    # упоминание в перечислении из вводной главы.
    for definitions_only in (True, False):
        for slot in chapter_slots:
            parts[slot] = add_index_entries(
                parts[slot], index_seen, definitions_only)

    note = """# От автора к печатному изданию {.unnumbered}

У этой книги есть постоянно обновляемая электронная версия:
**https://phys-dev.github.io/soft-dev-book/**

Печатное издание отличается от неё в трёх мелочах, о которых стоит знать
заранее.

Во-первых, **весь код здесь приведён целиком** — ни один листинг не обрезан.
Сокращены только распечатки результатов работы программ, да и то лишь те,
что и на экране читать невозможно: выгрузки координат всех элементов тракта
и тому подобное. Такие места помечены строкой `... (вывод сокращён)`{cut_count}.

Во-вторых, интерактивные графики, построенные библиотеками Plotly и
HoloViews, на бумаге показать невозможно: в электронной версии их можно
крутить, приближать и наводить курсор на точки, а здесь остался только
код, которым они строятся. Все статические иллюстрации (Matplotlib,
Seaborn) на месте.

В-третьих, перекрёстные ссылки между главами в бумажной версии приведены
просто названиями глав — ищи их по оглавлению.

Замечания, опечатки и предложения присылай в issues репозитория
**https://github.com/phys-dev/soft-dev-book**.

"""
    # число сокращённых распечаток считаем по факту: в томах оно разное,
    # а примечание идёт в оба, и «пять» в части, где их одна, читателя собьёт
    cut = "".join(parts).count("(вывод сокращён)")
    note = note.replace("{cut_count}", _ru_count(cut))
    # примечание ставим сразу после «О книге» и «О себе», до первого раздела
    first = next((i for i, p in enumerate(parts) if p.startswith("\n\n# ")), 0)
    parts.insert(first, note)

    book = "".join(parts)
    # схлопываем лишние пустые строки
    book = re.sub(r"\n{4,}", "\n\n\n", book)
    name = f"book{volume}.md" if volume else "book.md"
    out = os.path.join(BUILD, name)
    io.open(out, "w", encoding="utf-8").write(book)
    print(f"собрано глав: {len(stats)}")
    print(f"терминов в указателе: {len(index_seen)} из {len(INDEX_TERMS)}, "
          f"отметок: {sum(index_seen.values())}")
    print(f"размер: {len(book) / 1024:.0f} КБ -> {out}")
    print(f"картинок: {len(os.listdir(IMG))}")
    biggest = sorted(stats, key=lambda s: -s[2])[:5]
    print("самые объёмные главы после очистки:")
    for path, b, a in biggest:
        print(f"  {a / 1024:7.0f} КБ (было {b / 1024:.0f}) {path}")
if __name__ == "__main__":
    vol = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(vol)
