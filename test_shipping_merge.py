import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import DictionaryObject, NameObject, DecodedStreamObject, RectangleObject
from shipping_merge import tracking_numbers, goods_tracking_numbers, merge_documents, stack_pages


def fixture(path, texts, width=200, height=150, rotation=0):
    writer = PdfWriter()
    for text in texts:
        writer.add_blank_page(width, height)
        page = writer.pages[-1]
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        content = DecodedStreamObject()
        content.set_data(f'BT /F1 12 Tf 20 70 Td ({text}) Tj ET'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(content)
        if rotation:
            page.rotate(rotation)
    with path.open('wb') as stream:
        writer.write(stream)


class ShippingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent / 'recovery')
        self.base = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_identifiers(self):
        self.assertEqual(tracking_numbers('快递单号：sf123456789\n手机号 13800000000'), {'SF123456789'})
        self.assertEqual(tracking_numbers('运单号\n00123456789'), {'00123456789'})
        self.assertEqual(tracking_numbers('Tracking No: AB123456'), {'AB123456'})
        self.assertEqual(tracking_numbers('SKU: 12345678'), set())

    def test_goods_last_line(self):
        self.assertEqual(goods_tracking_numbers('SKC44931579016\nPC2609113184234 第1包\n极兔特惠 · JT0025632933491\n  \n'), {'JT0025632933491'})
        self.assertEqual(goods_tracking_numbers('其他信息\n001234567890'), {'001234567890'})
        self.assertEqual(goods_tracking_numbers('其他信息\n极兔 · JT0025632933491 JT0025636114030'), {'JT0025632933491', 'JT0025636114030'})
        self.assertEqual(goods_tracking_numbers('Tracking: SF123456'), {'SF123456'})

    def test_actual_templates_when_available(self):
        base = Path(__file__).parent
        goods, express = base / '面单1(1).pdf', base / '面单2(1).pdf'
        if not goods.exists() or not express.exists():
            self.skipTest('Sample templates unavailable')
        import shutil
        g, e = self.base / goods.name, self.base / express.name
        shutil.copyfile(goods, g)
        # Reverse express pages to prove matching does not depend on page order.
        writer = PdfWriter()
        for page in reversed(PdfReader(express).pages):
            writer.add_page(page)
        writer.write(str(e))
        result = merge_documents([str(g)], [str(e)])
        self.assertEqual((result['matched'], result['skipped']), (2, 0))
        pairs = [PdfReader(path).pages for path in result['pdf_paths']]
        for pages, number, other in zip(pairs, ['JT0025632933491', 'JT0025636114030'], ['JT0025636114030', 'JT0025632933491']):
            self.assertEqual(len(pages), 2)
            text = ''.join(page.extract_text() for page in pages)
            self.assertGreaterEqual(text.count(number), 2)
            self.assertNotIn(other, text)

    def test_matching_multifile_reuse_and_placement(self):
        goods, more, express = [self.base / f for f in ('goods.pdf', 'more.pdf', 'express.pdf')]
        fixture(goods, ['GOODS Tracking: SF123456', 'GOODS Tracking: SF123456'])
        fixture(more, ['GOODS Tracking: SF999999'])
        fixture(express, ['EXPRESS SF123456'], width=300, height=100)
        result = merge_documents([str(goods), str(more)], [str(express)])
        self.assertEqual((result['matched'], result['skipped']), (2, 1))
        self.assertEqual(len(result['pdf_paths']), 2)
        for path in result['pdf_paths']:
            reader = PdfReader(path)
            self.assertEqual(len(reader.pages), 2)
            self.assertIn('GOODS', reader.pages[0].extract_text())
            self.assertNotIn('EXPRESS', reader.pages[0].extract_text())
            self.assertIn('EXPRESS', reader.pages[1].extract_text())
            for page in reader.pages:
                self.assertAlmostEqual(float(page.mediabox.width) * 25.4 / 72, 100, places=4)
                self.assertAlmostEqual(float(page.mediabox.height) * 25.4 / 72, 100, places=4)
        second = merge_documents([str(goods)], [str(express)])
        self.assertNotEqual(result['output_dir'], second['output_dir'])

    def test_ambiguous_missing_and_exact_match(self):
        goods, express = self.base / 'g.pdf', self.base / 'e.pdf'
        fixture(goods, ['Tracking: SF123456', 'Tracking: SF12345', 'NO NUMBER'])
        fixture(express, ['Tracking: SF123456', 'Tracking: SF123456'])
        result = merge_documents([str(goods)], [str(express)])
        self.assertEqual(result['matched'], 0)
        self.assertEqual(result['pdf_paths'], [])
        self.assertEqual(result['skipped'], 3)
        self.assertTrue((Path(result['output_dir']) / '匹配报告.txt').exists())

    def test_split_filename_preserved(self):
        goods = self.base / '123456-商品-37个.pdf'
        express = self.base / 'express.pdf'
        fixture(goods, ['GOODS Tracking: SF123456'])
        fixture(express, ['EXPRESS SF123456'])
        original = goods.read_bytes()
        result = merge_documents([str(goods)], [str(express)])
        self.assertEqual(len(result['pdf_paths']), 1)
        output = Path(result['pdf_paths'][0])
        self.assertEqual(output.name, goods.name)
        self.assertEqual(len(PdfReader(output).pages), 2)
        self.assertEqual(goods.read_bytes(), original)

    def test_rotation_crop_and_source_unchanged(self):
        g, e = self.base / 'g.pdf', self.base / 'e.pdf'
        fixture(g, ['GOODS'], rotation=90)
        fixture(e, ['EXPRESS'])
        gp, ep = PdfReader(g).pages[0], PdfReader(e).pages[0]
        ep.cropbox = RectangleObject((10, 20, 190, 140))
        page = stack_pages(gp, ep)
        self.assertEqual((float(page.mediabox.width), float(page.mediabox.height)), (180, 320))
        self.assertEqual(gp.rotation, 90)
        self.assertEqual(list(ep.cropbox), [10, 20, 190, 140])
        self.assertIn('GOODS', page.extract_text())
        self.assertIn('EXPRESS', page.extract_text())

    def test_output_name_collisions(self):
        goods, express = self.base / '123-商品-3个.pdf', self.base / 'express.pdf'
        fixture(goods, ['GOODS Tracking: SF123456'])
        fixture(express, ['EXPRESS SF123456'])
        output = self.base / 'results'
        expected = ['123-商品-3个.pdf', '123-商品-3个（1）.pdf', '123-商品-3个（2）.pdf']
        for name in expected:
            result = merge_documents([str(goods)], [str(express)], output_dir=output)
            self.assertEqual(Path(result['pdf_paths'][0]).name, name)
        self.assertEqual(sorted(p.name for p in output.glob('*.pdf')), sorted(expected))

    def test_ui_wiring(self):
        spec = importlib.util.spec_from_file_location('pagination', Path(__file__).with_name('Pagination1.7.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.tk, 'Tk'), patch.object(module.tk, 'StringVar'), patch.object(module.tk, 'Text'), patch.object(module, 'ttk') as widgets:
            app = module.PDFProcessor()
            buttons = {c.kwargs.get('text'): c.kwargs.get('command') for c in widgets.Button.call_args_list}
            self.assertEqual(buttons['合并'], app.merge_shipping_pdfs)
            self.assertEqual(buttons['选择快递单'], app.select_express_files)
            self.assertEqual(buttons['一键生成'], app.generate_all)
            self.assertNotIn('匹配并复制SKU相关PDF', buttons)
            with patch.object(module.filedialog, 'askopenfilenames', return_value=['a.pdf', 'b.pdf']):
                app.select_express_files()
            self.assertEqual(app.express_file_paths, ['a.pdf', 'b.pdf'])
            with patch.object(module.messagebox, 'showwarning') as warning:
                app.merge_shipping_pdfs()
                warning.assert_called_once()
            app.file_paths = ['original-multipage.pdf']
            app.split_file_paths = ['123456-商品-37个.pdf']
            with patch('shipping_merge.merge_documents', return_value={'summary': 'OK', 'matched': 1, 'skipped': 0}) as merge, patch.object(module.messagebox, 'showinfo'):
                app.merge_shipping_pdfs()
                merge.assert_called_once_with(app.split_file_paths, app.express_file_paths)

    def test_one_click_full_pipeline(self):
        import os
        import pandas as pd
        from generation import generate_folder
        spec = importlib.util.spec_from_file_location('pagination_pipeline', Path(__file__).with_name('Pagination1.7.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        goods, express = self.base / 'goods.pdf', self.base / 'express.pdf'
        fixture(goods, ['SKC1001 Tracking: SF123456', 'SKC1001 Tracking: SF123456'])
        fixture(express, ['EXPRESS SF123456'])
        previous = os.getcwd()
        try:
            os.chdir(self.base)
            with patch.object(module.tk, 'Tk'), patch.object(module.tk, 'StringVar'), patch.object(module.tk, 'Text'), patch.object(module, 'ttk'), patch.object(module.messagebox, 'showinfo') as notice, patch.object(module.messagebox, 'showerror') as error:
                app = module.PDFProcessor()
                app.file_paths = [str(goods)]
                app.express_file_paths = [str(express)]
                # Missing optional files must not interrupt a complete run.
                app.generate_all()
                error.assert_not_called()
                notice.assert_called_once()
                first = Path(app.last_generated_folder)
                self.assertEqual(len(list(first.glob('*.pdf'))), 2)
                self.assertTrue((first / '批量_汇总表.xlsx').exists())
                self.assertEqual(len(list((first / '分页原件').glob('*.pdf'))), 2)
                self.assertIn('已跳过', (first / '生成说明.txt').read_text(encoding='utf-8-sig'))
                # Mapping and SKU copying participate in the next complete run.
                pd.DataFrame([{'修改前SKC': '1001', '修改后SKU': 'NEW1001', '修改后名称': '商品'}]).to_excel('preprocess.xlsx', index=False)
                Path('word').mkdir()
                fixture(Path('word/NEW1001-reference.pdf'), ['REFERENCE'])
                app.generate_all()
                self.assertEqual(notice.call_count, 2)
                error.assert_not_called()
                second = Path(app.last_generated_folder)
                self.assertNotEqual(first, second)
                self.assertTrue((second / 'NEW1001-商品-1个.pdf').exists())
                self.assertTrue((second / 'NEW1001-商品-1个（1）.pdf').exists())
                self.assertTrue((second / 'SKU相关文件/NEW1001-reference.pdf').exists())
                for path in second.glob('*.pdf'):
                    pages = PdfReader(path).pages
                    self.assertEqual(len(pages), 2)
                    self.assertIn('EXPRESS', pages[1].extract_text())
                rows = pd.read_excel(second / '批量_汇总表.xlsx')
                self.assertEqual(list(rows['合并状态']), ['已合并', '已合并'])
                # A failed next run must not claim successful generation.
                Path('preprocess.xlsx').write_bytes(b'broken xlsx')
                app.generate_all()
                error.assert_called_once()
                self.assertEqual(notice.call_count, 2)
                self.assertFalse(app._generating)
        finally:
            os.chdir(previous)


if __name__ == '__main__':
    unittest.main(verbosity=2)
