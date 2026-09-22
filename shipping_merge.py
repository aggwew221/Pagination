"""Match text-based shipping PDFs and place each matched pair on one page."""
import copy
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from PyPDF2 import PdfReader, PdfWriter, PageObject, Transformation
from PyPDF2.generic import RectangleObject


def tracking_numbers(text):
    text = unicodedata.normalize('NFKC', text).upper()
    label = r'(?:快递单号|物流单号|运单号|快递号|运单编号|WAYBILL(?:\s*(?:NO\.?|NUMBER))?|TRACKING(?:\s*(?:NO\.?|NUMBER))?)'
    matches = re.findall(label + r'\s*[:：#]?\s*([A-Z0-9][A-Z0-9-]{4,39})(?![A-Z0-9-])', text)
    return {value for value in matches if any(c.isdigit() for c in value)}


def goods_tracking_numbers(text):
    """The goods template prints the carrier and waybill on its last nonempty line."""
    lines = [line.strip() for line in unicodedata.normalize('NFKC', text).upper().splitlines() if line.strip()]
    if lines:
        # Accept e.g. 极兔特惠 · JT0025632933491, or a bare numeric waybill.
        candidates = set(re.findall(r'(?<![A-Z0-9-])(?:[A-Z]{1,6})?\d{8,30}(?![A-Z0-9-])', lines[-1]))
        if candidates:
            return candidates
    return tracking_numbers(text)


def _read_pages(paths, kind, notes):
    pages = []
    for path in dict.fromkeys(os.path.abspath(p) for p in paths):
        # Read errors stop the operation instead of silently dropping an input file.
        try:
            reader = PdfReader(path)
            for index, page in enumerate(reader.pages):
                label = f'{kind} {Path(path).name} 第 {index + 1} 页'
                try:
                    text = page.extract_text() or ''
                except Exception as exc:
                    text = ''
                    notes.append(f'{label}：文本提取失败：{exc}')
                pages.append({'page': page, 'text': text, 'label': label,
                              'filename': Path(path).name if len(reader.pages) == 1 else f'{Path(path).stem}_第{index + 1}页.pdf',
                              'numbers': goods_tracking_numbers(text) if kind == '货物单' else tracking_numbers(text)})
        except Exception as exc:
            raise ValueError(f'无法读取{kind}文件 {path}：{exc}') from exc
    return pages


def stack_pages(goods_page, express_page):
    # Copies are essential: multiple goods pages may share the same waybill.
    pages = [copy.deepcopy(goods_page), copy.deepcopy(express_page)]
    for page in pages:
        if page.rotation:
            page.transfer_rotation_to_content()
    sizes = [(float(p.cropbox.width), float(p.cropbox.height)) for p in pages]
    if any(w <= 0 or h <= 0 for w, h in sizes):
        raise ValueError('PDF 页面尺寸无效')
    width = max(w for w, h in sizes)
    height = sum(h for w, h in sizes)
    merged = PageObject.create_blank_page(width=width, height=height)
    for index, page in enumerate(pages):
        w, h = sizes[index]
        x = (width - w) / 2
        y = sizes[1][1] if index == 0 else 0
        page.add_transformation(Transformation().translate(x - float(page.cropbox.left), y - float(page.cropbox.bottom)))
        for box in ('mediabox', 'cropbox', 'trimbox', 'bleedbox', 'artbox'):
            setattr(page, box, RectangleObject((x, y, x + w, y + h)))
        merged.merge_page(page)
    return merged


def label_page(source):
    """Fit content proportionally on a separate 100 x 100 mm page."""
    page = copy.deepcopy(source)
    if page.rotation:
        page.transfer_rotation_to_content()
    size = 100 * 72 / 25.4
    width, height = float(page.cropbox.width), float(page.cropbox.height)
    if width <= 0 or height <= 0:
        raise ValueError('PDF 页面尺寸无效')
    scale = min(size / width, size / height)
    x, y = (size - width * scale) / 2, (size - height * scale) / 2
    page.add_transformation(Transformation().translate(-float(page.cropbox.left), -float(page.cropbox.bottom)).scale(scale).translate(x, y))
    for box in ('mediabox', 'cropbox', 'trimbox', 'bleedbox', 'artbox'):
        setattr(page, box, RectangleObject((x, y, x + width * scale, y + height * scale)))
    output = PageObject.create_blank_page(width=size, height=size)
    output.merge_page(page)
    return output


def merge_documents(goods_paths, express_paths, output_dir=None):
    if not goods_paths or not express_paths:
        raise ValueError('请选择货物单和快递单文件')
    notes = []
    goods = _read_pages(goods_paths, '货物单', notes)
    express = _read_pages(express_paths, '快递单', notes)
    known = set().union(*(p['numbers'] for p in goods))
    index = {}
    for position, record in enumerate(express):
        numbers = record['numbers']
        if not numbers:
            # Some carriers only print the number below a barcode, without a label.
            tokens = set(re.findall(r'(?<![A-Z0-9-])[A-Z0-9][A-Z0-9-]{4,39}(?![A-Z0-9-])', unicodedata.normalize('NFKC', record['text']).upper()))
            numbers = tokens & known
        if len(numbers) != 1:
            notes.append(f"{record['label']}：{'未识别到单号（扫描件需先做OCR）' if not numbers else '包含多个单号，未参与匹配'}")
            continue
        for number in numbers:
            index.setdefault(number, []).append(position)
    output = Path(output_dir) if output_dir else Path(tempfile.mkdtemp(prefix='快递单合并结果_', dir=Path(goods_paths[0]).resolve().parent))
    output.mkdir(parents=True, exist_ok=True)
    pdf_paths = []
    filename_map = {}
    used = set()
    matched = 0
    for record in goods:
        numbers = record['numbers']
        if len(numbers) != 1:
            notes.append(f"{record['label']}：单号缺失或存在多个单号，已跳过")
            continue
        number = next(iter(numbers))
        candidates = index.get(number, [])
        if len(candidates) != 1:
            reason = '未找到对应快递单' if not candidates else '对应多张快递单，无法唯一匹配'
            notes.append(f"{record['label']} [{number}]：{reason}，已跳过")
            continue
        position = candidates[0]
        writer = PdfWriter()
        writer.add_page(label_page(record['page']))
        writer.add_page(label_page(express[position]['page']))
        stem = re.sub(r'-修改后的\(\d+\)$', '', Path(record['filename']).stem)
        pdf_path = output / f'{stem}.pdf'
        counter = 1
        while pdf_path.exists():
            pdf_path = output / f'{stem}（{counter}）.pdf'
            counter += 1
        with pdf_path.open('wb') as stream:
            writer.write(stream)
        pdf_paths.append(str(pdf_path))
        filename_map[record['filename']] = pdf_path.name
        used.add(position)
        matched += 1
        notes.append(f"已合并：{record['label']} + {express[position]['label']} [{number}] → {pdf_path.name}")
    skipped = len(goods) - matched
    summary = f'货物单 {len(goods)} 页，快递单 {len(express)} 页\n已生成 {matched} 个独立PDF，跳过货物单 {skipped} 页，未使用快递单 {len(express) - len(used)} 页\n每份PDF两页：第一页货物单，第二页快递单，每页100×100毫米。\n输出目录：{output}'
    if not matched:
        summary += '\n没有唯一匹配的页面，未生成合并PDF。'
    (output / '匹配报告.txt').write_text(summary + '\n\n' + '\n'.join(notes), encoding='utf-8-sig')
    return {'matched': matched, 'skipped': skipped, 'summary': summary,
            'output_dir': str(output), 'pdf_paths': pdf_paths, 'filename_map': filename_map}
