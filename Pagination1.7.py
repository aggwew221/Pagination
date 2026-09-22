import os
import re
import shutil
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk


class PDFProcessor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('PDF处理器 - Pagination-1.7')
        self.root.geometry('700x800')
        self.extracted_data = []
        self.current_page = 0
        self.preprocess_data = {}
        self.preprocess_applied = False
        self.file_paths = []
        self.split_file_paths = []
        self.express_file_paths = []
        self.setup_ui()
        return None

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding='16')
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        ttk.Label(main_frame, text='PDF文件处理工具 (v1.7)', font=('Arial', 16, 'bold')
            ).grid(row=0, column=0, columnspan=3, pady=(0, 12))
        file_frame = ttk.LabelFrame(main_frame, text='文件选择', padding='8')
        file_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8)
            )
        self.file_path = tk.StringVar()
        ttk.Label(file_frame, text='货物单文件（可多选）:').grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(file_frame, textvariable=self.file_path, width=60).grid(row=1,
            column=0, sticky=(tk.W, tk.E))
        ttk.Button(file_frame, text='选择PDF文件', command=self.select_file).grid(row=1,
            column=1, padx=(8, 0))
        ttk.Button(file_frame, text='提取信息', command=self.extract_all_pages).grid(row
            =1, column=2, padx=(8, 0))
        preprocess_frame = ttk.Frame(file_frame)
        preprocess_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E),
            pady=(6, 0))
        ttk.Button(preprocess_frame, text='进行预处理', command=self.apply_preprocess_to_all
            ).grid(row=0, column=0, padx=(0, 5))
        self.preprocess_status = ttk.Label(preprocess_frame, text='未预处理',
            foreground='red')
        self.preprocess_status.grid(row=0, column=1, sticky=tk.W)
        self.express_file_path = tk.StringVar()
        ttk.Label(file_frame, text='快递单文件（可多选）:').grid(row=3, column=0, sticky=tk.W, pady=(8, 0))
        ttk.Entry(file_frame, textvariable=self.express_file_path, width=60).grid(row=4, column=0, sticky=(tk.W, tk.E))
        ttk.Button(file_frame, text='选择快递单', command=self.select_express_files).grid(row=4, column=1, padx=(8, 0))
        self.merge_button = ttk.Button(file_frame, text='合并', command=self.merge_shipping_pdfs)
        self.merge_button.grid(row=4, column=2, padx=(8, 0))
        ttk.Label(file_frame, text='每份成果两页：货物单＋快递单，每页100×100毫米；可直接一键生成。').grid(row=5, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))
        edit_frame = ttk.LabelFrame(main_frame, text='信息提取与编辑', padding='8')
        edit_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8)
            )
        ttk.Label(edit_frame, text='SKC:').grid(row=0, column=0, sticky=tk.W, pady=4)
        self.skc_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.skc_var, width=20).grid(row=0,
            column=1, sticky=(tk.W, tk.E), pady=4)
        ttk.Label(edit_frame, text='商品名称:').grid(row=1, column=0, sticky=tk.W, pady=4)
        self.product_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.product_var, width=48).grid(row=1,
            column=1, columnspan=2, sticky=(tk.W, tk.E), pady=4)
        ttk.Label(edit_frame, text='数量:').grid(row=2, column=0, sticky=tk.W, pady=4)
        self.quantity_var = tk.StringVar()
        ttk.Entry(edit_frame, textvariable=self.quantity_var, width=10).grid(row=2,
            column=1, sticky=tk.W, pady=4)
        nav_frame = ttk.Frame(edit_frame)
        nav_frame.grid(row=3, column=0, columnspan=3, pady=8)
        ttk.Button(nav_frame, text='上一页', command=self.prev_page).grid(row=0,
            column=0, padx=4)
        self.page_label = ttk.Label(nav_frame, text='第 0/0 页')
        self.page_label.grid(row=0, column=1, padx=8)
        ttk.Button(nav_frame, text='下一页', command=self.next_page).grid(row=0,
            column=2, padx=4)
        ttk.Button(nav_frame, text='保存修改', command=self.save_changes).grid(row=0,
            column=3, padx=6)
        ttk.Button(nav_frame, text='预览文件名', command=self.preview_filename).grid(row
            =0, column=4, padx=6)
        preview_frame = ttk.Frame(edit_frame)
        preview_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E))
        ttk.Label(preview_frame, text='预览文件名:').grid(row=0, column=0, sticky=tk.W)
        self.filename_preview = ttk.Label(preview_frame, text='', foreground='blue')
        self.filename_preview.grid(row=0, column=1, sticky=tk.W, padx=(6, 0))
        info_frame = ttk.LabelFrame(main_frame, text='其他信息', padding='8')
        info_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 8)
            )
        self.info_text = tk.Text(info_frame, height=10, width=72)
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E))
        scrollbar = ttk.Scrollbar(info_frame, orient='vertical', command=self.
            info_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.info_text.configure(yscrollcommand=scrollbar.set)
        ttk.Button(main_frame, text='开始处理', command=self.process_pdf).grid(row=4,
            column=0, columnspan=3, pady=12)
        self.generate_button = ttk.Button(main_frame, text='一键生成', command=self.generate_all)
        self.generate_button.grid(row=5, column=0, columnspan=3, pady=6)
        self.progress_label = ttk.Label(main_frame, text='')
        self.progress_label.grid(row=6, column=0, columnspan=3)
        main_frame.columnconfigure(0, weight=1)
        file_frame.columnconfigure(0, weight=1)
        edit_frame.columnconfigure(1, weight=1)
        info_frame.columnconfigure(0, weight=1)
        return None

    def generate_all(self):
        if getattr(self, '_generating', False):
            return
        if not self.file_paths or not self.express_file_paths:
            messagebox.showwarning('提示', '请选择货物单和快递单PDF，然后点击“一键生成”。')
            return
        self._generating = True
        self.generate_button.config(state='disabled')
        self.merge_button.config(state='disabled')
        try:
            from generation import generate_folder
            def progress(text):
                self.progress_label.config(text=text)
                self.root.update_idletasks()
            result = generate_folder(self, progress)
            self.last_generated_folder = result['output_dir']
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, result['summary'])
            self.progress_label.config(text=f"生成完成：合并 {result['matched']} 份，未匹配 {result['skipped']} 份")
            notice = messagebox.showwarning if result['skipped'] else messagebox.showinfo
            notice('一键生成结果', result['summary'])
        except Exception as exc:
            self.progress_label.config(text='一键生成失败')
            messagebox.showerror('一键生成失败', str(exc))
        finally:
            self._generating = False
            self.generate_button.config(state='normal')
            self.merge_button.config(state='normal')

    def search_and_copy_pdfs(self):
        '从批量拆分结果文件夹读取PDF文件名提取SKU，在word目录搜索相同SKU的PDF并复制，统计匹配情况'
        if not self.file_paths:
            messagebox.showerror('错误', '请先选择并处理PDF文件，生成批量拆分结果文件夹')
            return
        base_dir = os.path.dirname(self.file_paths[0])
        output_dir = os.path.join(base_dir, '批量拆分结果')
        if not os.path.exists(output_dir):
            messagebox.showerror('错误', f'未找到批量拆分结果文件夹: {output_dir}\n请先执行“开始处理”生成该文件夹。')
            return
        processed_pdfs = [f for f in os.listdir(output_dir) if f.lower().endswith('.pdf')]
        if not processed_pdfs:
            messagebox.showerror('错误', '批量拆分结果文件夹中未找到PDF文件')
            return
        sku_list = []
        for pdf_file in processed_pdfs:
            sku = pdf_file.split('-')[0].strip()
            sku_list.append(sku)
        unique_skus = set(sku_list)
        sku_matched = {sku: False for sku in unique_skus}
        search_dir = './word'
        if not os.path.exists(search_dir):
            messagebox.showerror('错误', f'搜索目录不存在: {search_dir}\n请确认路径正确。')
            return
        self.progress_label.config(text='正在搜索匹配的PDF文件...')
        self.root.update()
        copied_count = 0
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                if file.lower().endswith('.pdf'):
                    file_path = os.path.join(root, file)
                    matched_sku = None
                    for sku in unique_skus:
                        if sku.lower() in file.lower():
                            matched_sku = sku
                            sku_matched[sku] = True
                            break
                    if matched_sku:
                        dest_path = os.path.join(output_dir, file)
                        base, ext = os.path.splitext(file)
                        counter = 1
                        while os.path.exists(dest_path):
                            dest_path = os.path.join(output_dir, f'{base}_{counter}{ext}')
                            counter += 1
                        try:
                            shutil.copy2(file_path, dest_path)
                            copied_count += 1
                            self.progress_label.config(text=f'正在复制: {file}')
                            self.root.update()
                        except Exception as e:
                            print(f'复制失败 {file}: {str(e)}')
        matched_lines = []
        unmatched_lines = []
        for sku in sku_list:
            if sku_matched.get(sku, False):
                matched_lines.append(f'[✓] {sku}')
            else:
                unmatched_lines.append(f'[×] {sku}')
        unique_matched = [sku for sku in unique_skus if sku_matched[sku]]
        unique_unmatched = [sku for sku in unique_skus if not sku_matched[sku]]
        self.info_text.delete(1.0, tk.END)
        info_str = '===== SKU匹配统计 =====\n'
        info_str += f'批量拆分结果目录: {output_dir}\n'
        info_str += f'搜索目录: {search_dir}\n'
        info_str += f'复制文件数: {copied_count}\n'
        info_str += f'处理后PDF总SKU项数: {len(sku_list)} (去重后: {len(unique_skus)})\n\n'
        info_str += '【去重后匹配情况】\n'
        info_str += f'已匹配的SKU ({len(unique_matched)} 个):\n'
        info_str += '\n'.join(unique_matched[:50])
        if len(unique_matched) > 50:
            info_str += f'\n……等共 {len(unique_matched)} 项'
        info_str += f'\n\n未匹配的SKU ({len(unique_unmatched)} 个):\n'
        info_str += '\n'.join(unique_unmatched[:50])
        if len(unique_unmatched) > 50:
            info_str += f'\n……等共 {len(unique_unmatched)} 项'
        info_str += '\n\n【原始SKU列表匹配详情（含重复）】\n'
        info_str += f'已匹配项 ({len(matched_lines)} 个):\n'
        info_str += '\n'.join(matched_lines[:50])
        if len(matched_lines) > 50:
            info_str += f'\n……等共 {len(matched_lines)} 项'
        info_str += f'\n\n未匹配项 ({len(unmatched_lines)} 个):\n'
        info_str += '\n'.join(unmatched_lines[:50])
        if len(unmatched_lines) > 50:
            info_str += f'\n……等共 {len(unmatched_lines)} 项'
        self.info_text.insert(1.0, info_str)
        self.progress_label.config(text='搜索复制完成')
        messagebox.showinfo('完成', f'搜索复制完成！\n共复制 {copied_count} 个文件\n详细结果请查看“其他信息”区域。')

    def select_file(self):
        paths = filedialog.askopenfilenames(title='选择PDF文件', filetypes=[('PDF文件', '*.pdf'), ('所有文件', '*.*')])
        if not paths:
            return
        self.file_paths = list(paths)
        self.split_file_paths = []
        names = [os.path.basename(p) for p in self.file_paths]
        self.file_path.set(f"已选择 {len(names)} 个文件: " + '; '.join(names))

    def select_express_files(self):
        paths = filedialog.askopenfilenames(title='选择快递单PDF（可多选）', filetypes=[('PDF文件', '*.pdf')])
        if paths:
            self.express_file_paths = list(dict.fromkeys(paths))
            self.express_file_path.set(f'已选择 {len(self.express_file_paths)} 个文件: ' + '; '.join(os.path.basename(p) for p in self.express_file_paths))

    def merge_shipping_pdfs(self):
        if not self.file_paths or not self.express_file_paths:
            messagebox.showwarning('提示', '请先选择货物单和快递单PDF文件（均可多选）。')
            return
        self.merge_button.config(state='disabled')
        self.progress_label.config(text='正在匹配快递单号并合并...')
        self.root.update_idletasks()
        try:
            from shipping_merge import merge_documents
            goods_paths = self.split_file_paths
            if not goods_paths:
                from PyPDF2 import PdfReader
                if any(len(PdfReader(path).pages) != 1 for path in self.file_paths):
                    self.progress_label.config(text='请先完成货物单分页')
                    messagebox.showwarning('请先分页', '请先点击“提取信息”和“开始处理”完成分页，再点击“合并”。也可以直接选择已分页的单页PDF。')
                    return
                goods_paths = self.file_paths
            result = merge_documents(goods_paths, self.express_file_paths)
            self.info_text.delete(1.0, tk.END)
            self.info_text.insert(1.0, result['summary'])
            self.progress_label.config(text=f"合并完成：{result['matched']} 页，跳过 {result['skipped']} 页")
            notice = messagebox.showinfo if result['matched'] else messagebox.showwarning
            notice('合并结果', result['summary'])
        except Exception as e:
            self.progress_label.config(text='合并失败')
            messagebox.showerror('合并失败', str(e))
        finally:
            self.merge_button.config(state='normal')

    def load_preprocess_data(self):
        try:
            import pandas as pd
            preprocess_path = 'preprocess.xlsx'
            if os.path.exists(preprocess_path):
                df = pd.read_excel(preprocess_path, sheet_name='Sheet1')
                preprocess_data = {}
                for _, row in df.iterrows():
                    skc = str(row['修改前SKC']).strip()
                    new_sku = str(row['修改后SKU']).strip()
                    new_name = str(row['修改后名称']).strip()
                    preprocess_data[skc] = {'new_sku': new_sku, 'new_name': new_name}
                return preprocess_data
            return {}
        except Exception:
            return {}

    def apply_preprocess_to_all(self):
        if not self.extracted_data:
            messagebox.showwarning('警告', '请先提取PDF信息')
            return
        self.preprocess_data = self.load_preprocess_data()
        if not self.preprocess_data:
            messagebox.showerror('错误', '未找到预处理文件或预处理文件为空')
            return
        for i in range(len(self.extracted_data)):
            self.apply_preprocess_data(self.extracted_data[i])
        self.preprocess_applied = True
        self.preprocess_status.config(text='已预处理', foreground='green')
        self.display_page_info()
        messagebox.showinfo('成功', f'已应用预处理数据到所有页面，共 {len(self.preprocess_data)} 条映射规则')

    def apply_preprocess_data(self, info):
        skc = info.get('SKC', '')
        if skc:
            if skc in self.preprocess_data:
                p = self.preprocess_data[skc]
                info['new_sku'] = p.get('new_sku', skc)
                info['new_name'] = p.get('new_name', info.get('商品名称', ''))
                return None
        info['new_sku'] = info.get('SKC', '')
        info['new_name'] = info.get('商品名称', '')
        return None

    def extract_all_pages(self):
        if not self.file_paths:
            messagebox.showerror('错误', '请先选择 PDF 文件')
            return
        try:
            import PyPDF2
            self.progress_label.config(text='正在提取PDF信息...')
            self.root.update()
            self.preprocess_applied = False
            self.preprocess_status.config(text='未预处理', foreground='red')
            self.extracted_data = []
            total_pages = 0
            for p in self.file_paths:
                try:
                    reader = PyPDF2.PdfReader(p)
                    total_pages += len(reader.pages)
                except Exception:
                    pass
            processed = 0
            for file_index, path in enumerate(self.file_paths):
                try:
                    reader = PyPDF2.PdfReader(path)
                except Exception:
                    continue
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    page_text = page.extract_text() or ''
                    info = self.extract_info_from_page(page_text)
                    info['page_num'] = page_num
                    info['page_text'] = page_text
                    info['original_SKC'] = info.get('SKC', '')
                    info['original_product'] = info.get('商品名称', '')
                    info['new_sku'] = info.get('SKC', '')
                    info['new_name'] = info.get('商品名称', '')
                    info['source_file_index'] = file_index
                    info['source_file'] = os.path.basename(path)
                    info['source_path'] = path
                    self.extracted_data.append(info)
                    processed += 1
                    self.progress_label.config(text=f'正在提取 {processed}/{total_pages} 页信息...')
                    self.root.update()
            if self.extracted_data:
                self.current_page = 0
                self.display_page_info()
                self.progress_label.config(text=f'成功提取 {len(self.extracted_data)} 页信息，请检查并修改')
            else:
                self.progress_label.config(text='未提取到任何信息')
        except Exception as e:
            messagebox.showerror('错误', f'提取PDF信息时出现错误: {str(e)}')
            self.progress_label.config(text='提取失败')

    def extract_info_from_page(self, page_text):
        info = {'SKC': '', '数量': '', '仓库': '', '商品名称': '', 'SKU': '', '快递单号': '', '包裹信息': '', 'new_sku': '', 'new_name': ''}
        warehouse_match = re.search(r'#\s*(.+?)\s*\n', page_text)
        if warehouse_match:
            info['仓库'] = warehouse_match.group(1).strip()
        skc_patterns = [r'SKC\s*[:：]?\s*(\d+)', r'SKC\s*(\d+)', r'货号\s*[:：]?\s*(\d+)', r'型号\s*[:：]?\s*(\d+)']
        for pattern in skc_patterns:
            m = re.search(pattern, page_text)
            if m:
                info['SKC'] = m.group(1)
                break
        quantity_patterns = [r'(\d+)\s*件', r'数量\s*[:：]?\s*(\d+)', r'共\s*(\d+)\s*个', r'第\s*(\d+)\s*包']
        for pattern in quantity_patterns:
            m = re.search(pattern, page_text)
            if m:
                info['数量'] = m.group(1)
                break
        else:
            info['数量'] = '1'
        lines = page_text.split('\n')
        product_candidates = []
        for line in lines:
            line = line.strip()
            if not line or re.search(r'(SKC|件|包|第\d+包|快递|单号|仓库|发货|收货|地址|电话)', line):
                continue
            if re.search(r'[\u4e00-\u9fff]', line) and 2 < len(line) < 50:
                product_candidates.append(line)
        if product_candidates:
            for c in product_candidates:
                if not re.search(r'\d', c):
                    info['商品名称'] = c
                    break
            if not info['商品名称']:
                info['商品名称'] = product_candidates[0]
        sku_match = re.search(r'SKU\s*[:：]?\s*(\S+)', page_text)
        if sku_match:
            info['SKU'] = sku_match.group(1)
        from shipping_merge import goods_tracking_numbers
        express_numbers = goods_tracking_numbers(page_text)
        if len(express_numbers) == 1:
            info['快递单号'] = next(iter(express_numbers))
        package_match = re.search(r'第\s*(\d+)\s*包\s*（\s*共\s*(\d+)\s*包\s*）', page_text)
        if package_match:
            info['包裹信息'] = f'{package_match.group(1)}/{package_match.group(2)}'
        return info

    def display_page_info(self):
        if not self.extracted_data or self.current_page >= len(self.extracted_data):
            return
        data = self.extracted_data[self.current_page]
        self.skc_var.set(data.get('SKC', ''))
        self.product_var.set(data.get('商品名称', ''))
        self.quantity_var.set(data.get('数量', ''))
        self.page_label.config(text=f"第 {self.current_page + 1}/{len(self.extracted_data)} 页 (来源: {data.get('source_file', '')})")
        self.info_text.delete(1.0, tk.END)
        info_str = f"仓库: {data.get('仓库', '')}\n"
        info_str += f"SKU: {data.get('SKU', '')}\n"
        info_str += f"快递单号: {data.get('快递单号', '')}\n"
        info_str += f"包裹信息: {data.get('包裹信息', '')}\n\n"
        info_str += f"原始SKC: {data.get('original_SKC', '')}\n"
        info_str += f"原始商品名称: {data.get('original_product', '')}\n"
        info_str += f"修改后SKU: {data.get('new_sku', '')}\n"
        info_str += f"修改后名称: {data.get('new_name', '')}\n\n"
        info_str += '页面文本预览:\n'
        info_str += data.get('page_text', '')[:600] + ('...' if len(data.get('page_text', '')) > 600 else '')
        self.info_text.insert(1.0, info_str)
        self.update_filename_preview()

    def update_filename_preview(self):
        if not self.extracted_data or self.current_page >= len(self.extracted_data):
            return
        data = self.extracted_data[self.current_page]
        filename = self.generate_filename(data)
        self.filename_preview.config(text=filename)

    def generate_filename(self, data):
        if self.preprocess_applied and data.get('new_sku'):
            skc = data.get('new_sku') or data.get('SKC') or '未知SKC'
            product = data.get('new_name') or data.get('商品名称') or '未知商品'
        else:
            skc = data.get('SKC') or '未知SKC'
            product = data.get('商品名称') or '未知商品'
        quantity = data.get('数量') or '1'
        filename = f'{skc}-{product}-{quantity}个.pdf'
        return self.clean_filename(filename)

    def clean_filename(self, filename):
        invalid_chars = '[<>:"/\\\\|?*]'
        return re.sub(invalid_chars, '-', filename)

    def prev_page(self):
        if self.current_page > 0:
            self.save_changes()
            self.current_page -= 1
            self.display_page_info()

    def next_page(self):
        if self.current_page < len(self.extracted_data) - 1:
            self.save_changes()
            self.current_page += 1
            self.display_page_info()

    def save_changes(self):
        if not self.extracted_data or self.current_page >= len(self.extracted_data):
            return
        self.extracted_data[self.current_page]['SKC'] = self.skc_var.get()
        self.extracted_data[self.current_page]['商品名称'] = self.product_var.get()
        self.extracted_data[self.current_page]['数量'] = self.quantity_var.get()
        if self.preprocess_applied:
            self.apply_preprocess_data(self.extracted_data[self.current_page])
        self.update_filename_preview()

    def preview_filename(self):
        self.update_filename_preview()
        return None

    def process_pdf(self):
        if not self.file_paths:
            messagebox.showerror('错误', '请先选择 PDF 文件（至少 2 个）')
            return
        if not self.extracted_data:
            messagebox.showerror('错误', '请先提取PDF信息')
            return
        try:
            import PyPDF2
            import pandas as pd
            self.save_changes()
            self.progress_label.config(text='正在处理PDF文件...')
            self.root.update()
            base_dir = os.path.dirname(self.file_paths[0])
            output_dir = os.path.join(base_dir, '批量拆分结果')
            os.makedirs(output_dir, exist_ok=True)
            excel_data = []
            self.split_file_paths = []
            filename_count = {}
            pointer = 0
            total_pages = sum([len(PyPDF2.PdfReader(p).pages) for p in self.file_paths])
            processed = 0
            for path in self.file_paths:
                with open(path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    for page_num in range(len(reader.pages)):
                        page = reader.pages[page_num]
                        if pointer < len(self.extracted_data):
                            info = self.extracted_data[pointer]
                        else:
                            page_text = page.extract_text() or ''
                            info = self.extract_info_from_page(page_text)
                            if self.preprocess_applied:
                                self.apply_preprocess_data(info)
                        pointer += 1
                        filename = self.generate_filename(info)
                        if filename in filename_count:
                            filename_count[filename] += 1
                            name, ext = os.path.splitext(filename)
                            filename = f'{name}（{filename_count[filename] - 1}）{ext}'
                        else:
                            filename_count[filename] = 1
                        output_path = os.path.join(output_dir, filename)
                        pdf_writer = PyPDF2.PdfWriter()
                        pdf_writer.add_page(page)
                        with open(output_path, 'wb') as out_f:
                            pdf_writer.write(out_f)
                        self.split_file_paths.append(output_path)
                        if self.preprocess_applied and info.get('new_sku'):
                            custom_name = f"{info.get('new_sku', '')}-{info.get('new_name', '')}-{info.get('数量', '')}个"
                        else:
                            custom_name = f"{info.get('SKC', '')}-{info.get('商品名称', '')}-{info.get('数量', '')}个"
                        excel_data.append({
                            '文件名': filename,
                            '原来源文件': os.path.basename(path),
                            'SKC': info.get('SKC', ''),
                            '数量': info.get('数量', ''),
                            '仓库': info.get('仓库', ''),
                            '商品名称': info.get('商品名称', ''),
                            'SKU': info.get('SKU', ''),
                            '快递单号': info.get('快递单号', ''),
                            '包裹信息': info.get('包裹信息', ''),
                            '原页码': page_num + 1,
                            '修改后SKU': info.get('new_sku', ''),
                            '修改后名称': info.get('new_name', ''),
                            '自定义名称': custom_name,
                        })
                        processed += 1
                        self.progress_label.config(text=f'正在处理 {processed}/{total_pages} 页...')
                        self.root.update()
            excel_path = os.path.join(output_dir, '批量_汇总表.xlsx')
            df = pd.DataFrame(excel_data)
            df.to_excel(excel_path, index=False)
            self.progress_label.config(text='处理完成！')
            messagebox.showinfo('完成', f'处理完成！\nPDF文件已保存到: {output_dir}\nExcel表格已保存为: {excel_path}')
        except Exception as e:
            messagebox.showerror('错误', f'处理过程中出现错误: {str(e)}')
            self.progress_label.config(text='处理失败')

def main():
    app = PDFProcessor()
    app.root.mainloop()
    return None


if __name__ == '__main__':
    main()
