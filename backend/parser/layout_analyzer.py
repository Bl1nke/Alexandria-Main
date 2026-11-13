"""Анализ структуры и визуального расположения элементов документа.

Layout Analyzer работает поверх модели Этапа 2 и НЕ извлекает содержимое
повторно. Результаты (колонки, порядок чтения, типы блоков, связи)
добавляются к исходным данным: блоки/таблицы/изображения не удаляются,
координаты не пересчитываются.

Ключевые идеи:
  * определение колонок — по высотно-взвешенному профилю вертикального
    покрытия (а не по фиксированной координате X); полноширинные элементы
    исключаются из голосования за гуттеры;
  * порядок чтения — полноширинные элементы делят страницу на полосы,
    внутри полосы колонки читаются слева-направо, внутри колонки — сверху-вниз;
  * классификация блоков — по сочетанию признаков (размер/начертание,
    положение, длина, выравнивание, нумерация), а не по одному признаку;
  * колонтитулы — по повторяемости текста в краевых зонах нескольких страниц;
  * DOCX без координат — структурный порядок и роли из стилей; колоночный
    анализ помечается как недоступный (координаты не выдумываются).

Все пороги — относительные (доли/медианы), в config/parser_settings.py.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set

from config.parser_settings import (
    LAYOUT_CAPTION_DISTANCE_FACTOR,
    LAYOUT_COVERAGE_MAX,
    LAYOUT_FULL_WIDTH_FRACTION,
    LAYOUT_GUTTER_MIN_FRACTION,
    LAYOUT_HEADING_MAX_CHARS,
    LAYOUT_HEADING_SIZE_FACTOR,
    LAYOUT_HEADER_FOOTER_REPEAT_MIN,
    LAYOUT_MARGIN_FRACTION,
)
from models.document import BBox, Document, Page
from models.layout import Column, PageLayout
from models.validation import Confidence

# Маркеры списков (маркер или короткая нумерация) и подписей.
_LIST_MARKER_RE = re.compile(r"^\s*(?:[•·▪◦‣\-–—*]|\(?\d{1,2}[.)])\s+")
_CAPTION_RE = re.compile(
    r"^\s*(?:рис(?:унок|\.)?|табл(?:ица|\.)?|схема|figure|fig\.?|table|diagram)(?!\w)",
    re.IGNORECASE,
)
_DIGITS_RE = re.compile(r"\d+")
_SENTENCE_END = (".", "!", "?", "…", ":", ";")


def analyze_layout(document: Document) -> Document:
    """Анализирует макет документа, дополняя модели структурной информацией.

    Args:
        document: документ, загруженный и извлечённый на этапе 2.

    Returns:
        Тот же документ: у каждой страницы заполнен ``Page.layout``,
        у блоков — ``column``/``alignment``/``block_type``, переупорядочены
        блоки и проставлен сквозной ``order``. Исходные данные сохранены.
    """
    repeated_texts = _find_repeated_margin_texts(document)
    for page in document.pages:
        page.layout = _analyze_page(page, repeated_texts)
    _reorder_and_number(document)
    _link_captions(document)
    _detect_continuations(document)
    _collect_warnings(document)
    return document


def _analyze_page(page: Page, repeated_texts: Set[str]) -> PageLayout:
    """Строит :class:`PageLayout` для одной страницы."""
    geo_blocks = [block for block in page.blocks if block.bbox is not None]
    if not geo_blocks:
        return _structural_layout(page)

    content_box = _content_box(geo_blocks)
    median_size = _median([b.font_size for b in geo_blocks if b.font_size]) or 10.0
    median_height = _median([b.bbox.height for b in geo_blocks]) or median_size

    for block in page.blocks:
        if block.bbox is not None:
            block.alignment = _alignment(block, content_box)
        _classify_block(block, page, median_size, repeated_texts)

    body = [b for b in geo_blocks if b.block_type not in ("header", "footer")]
    columns, column_confidence = _detect_columns(page, body, content_box)
    _assign_columns(page, columns, content_box)

    has_full_width = _has_full_width(page, body, content_box)
    layout_type = _layout_type(columns, has_full_width)
    reading_order = _page_reading_order(page, columns)

    uncertain = column_confidence is Confidence.LOW or layout_type == "unknown"
    warnings: List[str] = []
    if uncertain:
        warnings.append(f"Страница {page.number}: неоднозначная структура колонок")

    return PageLayout(
        page=page.number,
        layout_type=layout_type,
        column_count=len(columns),
        columns=columns,
        reading_order=reading_order,
        confidence=column_confidence,
        uncertain=uncertain,
        warnings=warnings,
    )


def _structural_layout(page: Page) -> PageLayout:
    """Макет для страницы без координат (DOCX): структурный порядок."""
    for block in page.blocks:
        _classify_structural_block(block)
    order = [block.id for block in page.blocks]
    order += [table.id for table in page.tables]
    order += [image.id for image in page.images]
    return PageLayout(
        page=page.number,
        layout_type="unavailable",
        column_count=None,
        columns=[],
        reading_order=order,
        confidence=Confidence.MEDIUM,
        uncertain=True,
        warnings=[
            f"Страница {page.number}: координаты недоступны — "
            f"колоночный анализ не выполняется"
        ],
    )


def _find_repeated_margin_texts(document: Document) -> Set[str]:
    """Нормализованные тексты, повторяющиеся в краевых зонах нескольких страниц."""
    counts: Dict[str, int] = {}
    for page in document.pages:
        seen: Set[str] = set()
        for block in page.blocks:
            if _in_margin_zone(page, block) is None:
                continue
            key = _normalize(block.text)
            if key and key not in seen:
                seen.add(key)
                counts[key] = counts.get(key, 0) + 1
    return {
        key for key, count in counts.items() if count >= LAYOUT_HEADER_FOOTER_REPEAT_MIN
    }


def _in_margin_zone(page: Page, block) -> Optional[str]:
    """Возвращает ``header``/``footer``, если блок в краевой зоне страницы."""
    if block.bbox is None or page.height <= 0:
        return None
    top_zone = page.height * LAYOUT_MARGIN_FRACTION
    bottom_zone = page.height * (1 - LAYOUT_MARGIN_FRACTION)
    if block.bbox.y1 <= top_zone:
        return "header"
    if block.bbox.y0 >= bottom_zone:
        return "footer"
    return None


def _normalize(text: str) -> str:
    """Нормализует текст для сравнения повторов (цифры и пробелы убираются)."""
    return re.sub(r"\s+", " ", _DIGITS_RE.sub("", text.lower())).strip()


def _block_role(page: Page, block, repeated_texts: Set[str]) -> Optional[str]:
    """Роль блока по положению и повторяемости: header/footer либо None."""
    if block.block_type in ("header", "footer"):
        return block.block_type
    zone = _in_margin_zone(page, block)
    if zone is not None and _normalize(block.text) in repeated_texts:
        return zone
    return None


def _alignment(block, content_box: BBox) -> Optional[str]:
    """Выравнивание блока относительно области контента страницы."""
    bbox = block.bbox
    content_width = content_box.x1 - content_box.x0
    if bbox is None or content_width <= 0:
        return None
    if bbox.width >= LAYOUT_FULL_WIDTH_FRACTION * content_width:
        return "left"
    left = bbox.x0 - content_box.x0
    right = content_box.x1 - bbox.x1
    if abs(left - right) <= 0.15 * content_width:
        return "center"
    if right <= 0.1 * content_width and left >= 0.2 * content_width:
        return "right"
    return "left"


def _classify_block(block, page: Page, median_size: float, repeated_texts: Set[str]) -> None:
    """Классифицирует блок по сочетанию признаков (координаты доступны)."""
    role = _block_role(page, block, repeated_texts)
    if role in ("header", "footer"):
        block.block_type = role
        block.alignment = None
        return
    if block.block_type in ("heading", "list_item", "caption"):
        if block.block_type == "list_item":
            block.block_type = "list"
        return
    if block.block_type == "table_row":
        block.block_type = "table"
        return
    text = block.text.strip()
    if _CAPTION_RE.match(text):
        block.block_type = "caption"
        return
    if _LIST_MARKER_RE.match(text):
        block.block_type = "list"
        return
    size = block.font_size or median_size
    font_name = (block.font_name or "").lower()
    bold = block.is_bold or "bold" in font_name or "black" in font_name
    is_heading = (
        size >= LAYOUT_HEADING_SIZE_FACTOR * median_size
        and len(text) <= LAYOUT_HEADING_MAX_CHARS
        and (bold or block.alignment == "center")
        and not text.endswith(".")
    )
    block.block_type = "heading" if is_heading else "paragraph"


def _classify_structural_block(block) -> None:
    """Классифицирует блок без координат (DOCX) по стилю и тексту."""
    if block.block_type == "table_row":
        block.block_type = "table"
        return
    if block.block_type in ("heading", "list_item"):
        if block.block_type == "list_item":
            block.block_type = "list"
        return
    text = block.text.strip()
    if _CAPTION_RE.match(text):
        block.block_type = "caption"
    elif _LIST_MARKER_RE.match(text):
        block.block_type = "list"
    else:
        block.block_type = "paragraph"



def _content_box(blocks) -> BBox:
    """Объединяющий bbox всех блоков страницы (область контента)."""
    return BBox(
        x0=min(b.bbox.x0 for b in blocks),
        y0=min(b.bbox.y0 for b in blocks),
        x1=max(b.bbox.x1 for b in blocks),
        y1=max(b.bbox.y1 for b in blocks),
    )


def _has_full_width(page: Page, body, content_box: BBox) -> bool:
    """Есть ли на странице полноширинный элемент (блок/таблица/изображение)."""
    width = content_box.x1 - content_box.x0
    if width <= 0:
        return False
    threshold = LAYOUT_FULL_WIDTH_FRACTION * width
    for block in body:
        if block.bbox.width >= threshold:
            return True
    for table in page.tables:
        if table.bbox is not None and table.bbox.width >= threshold:
            return True
    for image in page.images:
        if image.bbox is not None and image.bbox.width >= threshold:
            return True
    return False


def _detect_columns(page: Page, body, content_box: BBox):
    """Определяет колонки страницы по профилю вертикального покрытия.

    Возвращает ``(columns, confidence)``. Полноширинные элементы исключаются
    из голосования, чтобы не «разрушать» гуттеры; пороги адаптивные
    (доли ширины страницы и медианы), без единой фиксированной координаты.
    """
    single = [
        Column(
            index=0,
            x0=content_box.x0,
            x1=content_box.x1,
            y0=content_box.y0,
            y1=content_box.y1,
            confidence=Confidence.MEDIUM,
        )
    ]
    content_width = content_box.x1 - content_box.x0
    if not body or content_width <= 0 or page.width <= 0:
        return single, Confidence.LOW

    threshold = LAYOUT_FULL_WIDTH_FRACTION * content_width
    voters = [b for b in body if b.bbox.width < threshold]
    if not voters:
        return single, Confidence.MEDIUM

    x_min = min(b.bbox.x0 for b in voters)
    x_max = max(b.bbox.x1 for b in voters)
    span = x_max - x_min
    if span <= 0:
        return single, Confidence.MEDIUM

    char_widths = [b.bbox.width / len(b.text) for b in voters if len(b.text) >= 3]
    cw = _median(char_widths) or 5.0
    content_height = max(b.bbox.y1 for b in voters) - min(b.bbox.y0 for b in voters)
    if content_height <= 0:
        return single, Confidence.LOW

    bin_count = max(20, int(span / 2.0))
    bin_width = span / bin_count
    coverage = [0.0] * bin_count
    for block in voters:
        first = max(0, int((block.bbox.x0 - x_min) / bin_width))
        last = min(bin_count - 1, int((block.bbox.x1 - x_min) / bin_width))
        height = block.bbox.height
        for index in range(first, last + 1):
            coverage[index] += height

    ratios = [min(1.0, value / content_height) for value in coverage]
    is_gutter = [ratio < LAYOUT_COVERAGE_MAX for ratio in ratios]

    min_gutter = max(LAYOUT_GUTTER_MIN_FRACTION * page.width, 2 * cw)
    gutters: List[tuple] = []
    start = None
    for index in range(bin_count):
        if is_gutter[index] and start is None:
            start = index
        elif not is_gutter[index] and start is not None:
            if (index - start) * bin_width >= min_gutter:
                gutters.append((x_min + start * bin_width, x_min + index * bin_width))
            start = None
    if start is not None and (bin_count - start) * bin_width >= min_gutter:
        gutters.append((x_min + start * bin_width, x_max))

    if not gutters:
        return single, _columns_confidence(ratios, is_gutter, voters)

    columns: List[Column] = []
    previous = x_min
    for gutter_start, gutter_end in gutters:
        if gutter_start - previous > 0:
            columns.append(
                Column(
                    index=len(columns),
                    x0=previous,
                    x1=gutter_start,
                    y0=content_box.y0,
                    y1=content_box.y1,
                    confidence=Confidence.MEDIUM,
                )
            )
        previous = gutter_end
    if x_max - previous > 0:
        columns.append(
            Column(
                index=len(columns),
                x0=previous,
                x1=x_max,
                y0=content_box.y0,
                y1=content_box.y1,
                confidence=Confidence.MEDIUM,
            )
        )

    if len(columns) < 2:
        return single, Confidence.LOW
    confidence = _columns_confidence(ratios, is_gutter, voters)
    for column in columns:
        column.confidence = confidence
    return columns, confidence


def _columns_confidence(ratios, is_gutter, voters) -> Confidence:
    """Оценка уверенности определения колонок по контрасту покрытия."""
    inside = [r for r, flag in zip(ratios, is_gutter) if flag]
    outside = [r for r, flag in zip(ratios, is_gutter) if not flag]
    if not inside or not outside:
        return Confidence.MEDIUM
    contrast = sum(outside) / len(outside) - sum(inside) / len(inside)
    if contrast >= 0.5 and len(voters) >= 4:
        return Confidence.HIGH
    if contrast >= 0.25:
        return Confidence.MEDIUM
    return Confidence.LOW


def _column_index(bbox: BBox, columns) -> Optional[int]:
    """Индекс колонки, содержащей центр bbox (или ближайшей к нему)."""
    if not columns:
        return None
    center = (bbox.x0 + bbox.x1) / 2.0
    for column in columns:
        if column.x0 <= center <= column.x1:
            return column.index
    return min(columns, key=lambda c: abs(center - (c.x0 + c.x1) / 2.0)).index


def _assign_columns(page: Page, columns, content_box: BBox) -> None:
    """Проставляет индекс колонки и признак полноширинности элементам страницы."""
    content_width = content_box.x1 - content_box.x0
    for block in page.blocks:
        if block.bbox is not None:
            block.column = _column_index(block.bbox, columns)
    for table in page.tables:
        if table.bbox is None:
            continue
        table.column = _column_index(table.bbox, columns)
        table.full_width = table.bbox.width >= LAYOUT_FULL_WIDTH_FRACTION * content_width
    for image in page.images:
        if image.bbox is None:
            continue
        image.column = _column_index(image.bbox, columns)
        image.full_width = image.bbox.width >= LAYOUT_FULL_WIDTH_FRACTION * content_width


def _layout_type(columns, has_full_width: bool) -> str:
    """Тип макета: single / multi / mixed."""
    if len(columns) <= 1:
        return "single"
    return "mixed" if has_full_width else "multi"


def _item(element_id: str, bbox: BBox, column: Optional[int], full: bool) -> dict:
    """Унифицированное описание элемента для расчёта порядка чтения."""
    return {
        "id": element_id,
        "x0": bbox.x0,
        "x1": bbox.x1,
        "y0": bbox.y0,
        "y1": bbox.y1,
        "column": column,
        "full": full,
    }


def _page_reading_order(page: Page, columns) -> List[str]:
    """Порядок чтения страницы с учётом колонок и полноширинных элементов."""
    columns_span = columns[-1].x1 - columns[0].x0 if len(columns) >= 2 else 0.0
    items: List[dict] = []
    for block in page.blocks:
        if block.bbox is None or block.block_type in ("header", "footer"):
            continue
        full = (
            columns_span > 0
            and block.bbox.width >= LAYOUT_FULL_WIDTH_FRACTION * columns_span
        )
        items.append(_item(block.id, block.bbox, block.column, full))
    for table in page.tables:
        if table.bbox is None:
            continue
        items.append(_item(table.id, table.bbox, table.column, bool(table.full_width)))
    for image in page.images:
        if image.bbox is None:
            continue
        items.append(_item(image.id, image.bbox, image.column, bool(image.full_width)))

    if not items:
        return []

    full = sorted([it for it in items if it["full"]], key=lambda it: it["y0"])
    rest = [it for it in items if not it["full"]]

    def sort_key(item: dict):
        return (
            item["column"] if item["column"] is not None else 0,
            round(item["y0"], 1),
            item["x0"],
        )

    if not full:
        rest.sort(key=sort_key)
        return [it["id"] for it in rest]

    centers = [(it["y0"] + it["y1"]) / 2.0 for it in full]
    bands: Dict[int, List[dict]] = {}
    for item in rest:
        center = (item["y0"] + item["y1"]) / 2.0
        band = sum(1 for full_center in centers if full_center <= center)
        bands.setdefault(band, []).append(item)

    order: List[str] = []
    for band in range(len(full) + 1):
        band_items = bands.get(band, [])
        band_items.sort(key=sort_key)
        order.extend(it["id"] for it in band_items)
        if band < len(full):
            order.append(full[band]["id"])
    return order


def _median(values) -> float:
    """Медиана числового списка (0.0 для пустого)."""
    numbers = [value for value in values if value is not None]
    if not numbers:
        return 0.0
    numbers = sorted(numbers)
    middle = len(numbers) // 2
    if len(numbers) % 2 == 1:
        return float(numbers[middle])
    return (float(numbers[middle - 1]) + float(numbers[middle])) / 2.0


def _vertical_distance(a: BBox, b: BBox) -> float:
    """Вертикальное расстояние между областями (0 при перекрытии)."""
    if b.y0 >= a.y1:
        return b.y0 - a.y1
    if a.y0 >= b.y1:
        return a.y0 - b.y1
    return 0.0


def _reorder_and_number(document: Document) -> None:
    """Переупорядочивает блоки по порядку чтения и проставляет сквозной ``order``."""
    counter = 0
    for page in document.pages:
        order = page.layout.reading_order if page.layout else []
        by_id = {block.id: block for block in page.blocks}
        ordered = [by_id[bid] for bid in order if bid in by_id]
        included = {block.id for block in ordered}
        leftovers = [block for block in page.blocks if block.id not in included]
        for block in ordered + leftovers:
            block.order = counter
            counter += 1
        page.blocks = ordered + leftovers


def _body_blocks(page: Page) -> List:
    """Блоки страницы без колонтитулов (в порядке чтения)."""
    return [block for block in page.blocks if block.block_type not in ("header", "footer")]


def _link_captions(document: Document) -> None:
    """Связывает подписи с ближайшими изображениями/таблицами (если очевидно)."""
    for page in document.pages:
        captions = [b for b in page.blocks if b.block_type == "caption" and b.bbox is not None]
        if not captions:
            continue
        targets = [(im.id, im) for im in page.images if im.bbox is not None]
        targets += [(table.id, table) for table in page.tables if table.bbox is not None]
        if not targets:
            continue
        heights = [b.bbox.height for b in page.blocks if b.bbox is not None]
        max_distance = LAYOUT_CAPTION_DISTANCE_FACTOR * (_median(heights) or 10.0)
        for caption in captions:
            best = None
            best_distance = None
            for _target_id, target in targets:
                target_column = getattr(target, "column", None)
                if caption.column is not None and target_column is not None:
                    if caption.column != target_column:
                        continue
                if caption.bbox.x1 < target.bbox.x0 or caption.bbox.x0 > target.bbox.x1:
                    continue
                distance = _vertical_distance(caption.bbox, target.bbox)
                if distance > max_distance:
                    continue
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best = target
            if best is not None:
                best.caption_id = caption.id
                caption.caption_for = best.id


def _ends_sentence(text: str) -> bool:
    """Заканчивается ли текст предложением (терминальная пунктуация)."""
    stripped = text.rstrip()
    return bool(stripped) and stripped.endswith(_SENTENCE_END)


def _starts_lowercase(text: str) -> bool:
    """Начинается ли текст со строчной буквы (признак продолжения)."""
    for char in text:
        if char.isalpha():
            return char.islower()
    return False


def _detect_continuations(document: Document) -> None:
    """Связывает блоки, продолжающиеся на следующей странице (по признакам)."""
    links: List[dict] = []
    pages = document.pages
    for index in range(len(pages) - 1):
        current = _body_blocks(pages[index])
        following = _body_blocks(pages[index + 1])
        if not current or not following:
            continue
        last = current[-1]
        first = following[0]
        if last.bbox is None or first.bbox is None:
            continue
        if last.block_type == "heading" or first.block_type == "heading":
            continue
        if _ends_sentence(last.text) or not _starts_lowercase(first.text):
            continue
        if (
            last.column is not None
            and first.column is not None
            and last.column != first.column
        ):
            continue
        if pages[index].width > 0 and abs(last.bbox.x0 - first.bbox.x0) > 0.05 * pages[index].width:
            continue
        links.append({"from": last.id, "to": first.id})
    if links:
        document.metadata["continuation_links"] = links


def _collect_warnings(document: Document) -> None:
    """Добавляет предупреждения страниц в общий список документа."""
    for page in document.pages:
        if not page.layout:
            continue
        for warning in page.layout.warnings:
            if warning not in document.warnings:
                document.warnings.append(warning)

