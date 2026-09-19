"""Run the complete workflow in a fresh output folder, without intermediate dialogs."""
from pathlib import Path
import shutil
import tempfile

from PyPDF2 import PdfReader, PdfWriter
from shipping_merge import merge_documents


def generate_folder(processor, progress=lambda text: None):
    import pandas as pd
    import openpyxl  # Check Excel support before starting to write output.

    goods_paths = list(dict.fromkeys(processor.file_paths))
    express_paths = list(dict.fromkeys(processor.express_file_paths))
    if not goods_paths or not express_paths:
        raise ValueError('请选择货物单和快递单PDF')
    progress('1/5 检查输入文件和预处理规则...')
    goods = [(path, PdfReader(path)) for path in goods_paths]
    for path in express_paths:
        reader = PdfReader(path)
        if not reader.pages:
            raise ValueError(f'快递单没有页面：{path}')
    if not any(reader.pages for _, reader in goods):
        raise ValueError('货物单没有页面')
    mapping = {}
    if Path('preprocess.xlsx').exists():
        df = pd.read_excel('preprocess.xlsx', sheet_name='Sheet1', dtype=str, keep_default_na=False)
        required = ['修改前SKC', '修改后SKU', '修改后名称']
        if any(column not in df.columns for column in required):
            raise ValueError('preprocess.xlsx 缺少必要列：' + '、'.join(required))
        for _, row in df.iterrows():
            if row['修改前SKC'].strip():
                mapping[row['修改前SKC'].strip()] = {'new_sku': row['修改后SKU'].strip(), 'new_name': row['修改后名称'].strip()}
    processor.preprocess_data = mapping
    processor.preprocess_applied = bool(mapping)
    processor.preprocess_status.config(text='已预处理' if mapping else '未预处理', foreground='green' if mapping else 'red')
    output = Path(tempfile.mkdtemp(prefix='一键生成结果_', dir=Path(goods_paths[0]).resolve().parent))
    split_dir = output / '分页原件'
    split_dir.mkdir()
    processor.split_file_paths = []
    processor.extracted_data = []
    rows = []
    notes = [f'预处理映射：{len(mapping)} 条（无规则时使用原信息）']
    try:
        for source_index, (path, reader) in enumerate(goods):
            for page_index, page in enumerate(reader.pages):
                progress(f'2/5 提取并分页：{Path(path).name} 第 {page_index + 1} 页')
                text = page.extract_text() or ''
                info = processor.extract_info_from_page(text)
                info.update(page_num=page_index, page_text=text, source_file_index=source_index,
                            source_file=Path(path).name, source_path=path,
                            original_SKC=info.get('SKC', ''), original_product=info.get('商品名称', ''))
                processor.apply_preprocess_data(info)
                processor.extracted_data.append(info)
                name = processor.generate_filename(info)
                target = split_dir / name
                counter = 2
                while target.exists():
                    target = split_dir / f'{Path(name).stem}_{counter}.pdf'
                    counter += 1
                writer = PdfWriter()
                writer.add_page(page)
                with target.open('wb') as stream:
                    writer.write(stream)
                processor.split_file_paths.append(str(target))
                rows.append({'文件名': target.name, '原来源文件': Path(path).name,
                             **{k: info.get(k, '') for k in ('SKC', '数量', '仓库', '商品名称', 'SKU', '快递单号', '包裹信息')},
                             '原页码': page_index + 1, '修改后SKU': info['new_sku'], '修改后名称': info['new_name'],
                             '自定义名称': f"{info['new_sku']}-{info['new_name']}-{info.get('数量', '')}个"})
        progress('3/5 匹配并复制SKU相关PDF...')
        word = Path('word')
        skus = {info['new_sku'] or info.get('SKC', '') for info in processor.extracted_data}
        skus.discard('')
        copied = 0
        if word.is_dir():
            references = output / 'SKU相关文件'
            references.mkdir()
            for source in sorted(word.rglob('*')):
                if source.is_file() and source.suffix.lower() == '.pdf' and any(sku.lower() in source.name.lower() for sku in skus):
                    target = references / source.name
                    counter = 2
                    while target.exists():
                        target = references / f'{source.stem}_{counter}{source.suffix}'
                        counter += 1
                    shutil.copy2(source, target)
                    copied += 1
            notes.append(f'SKU相关PDF：已复制 {copied} 份')
        else:
            notes.append('未找到 word 文件夹，已跳过SKU相关PDF复制')
        progress('4/5 将快递单拼接到每份货物单下方...')
        result = merge_documents(processor.split_file_paths, express_paths, output_dir=output)
        progress('5/5 导出Excel汇总和生成报告...')
        merged_names = {Path(path).name for path in result['pdf_paths']}
        for row in rows:
            row['合并状态'] = '已合并' if row['文件名'] in merged_names else '未合并，详见匹配报告'
        pd.DataFrame(rows).to_excel(output / '批量_汇总表.xlsx', index=False)
        summary = f"已生成结果文件夹：{output}\n\n合并PDF：{result['matched']} 份（货物单上、快递单下）\n未合并：{result['skipped']} 份，原页保存在“分页原件”\n" + '\n'.join(notes) + '\n已保存Excel汇总表和匹配报告。'
        (output / '生成说明.txt').write_text(summary, encoding='utf-8-sig')
        processor.current_page = 0
        processor.display_page_info()
        result.update(summary=summary, copied=copied)
        return result
    except Exception as exc:
        (output / '生成失败.txt').write_text(f'生成未完成：{exc}\n此文件夹仅包含中间结果。', encoding='utf-8-sig')
        raise RuntimeError(f'{exc}\n中间结果保存在：{output}') from exc
