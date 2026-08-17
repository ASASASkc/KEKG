# -*- coding: utf-8 -*-
"""Excel / Word 解析与生成工具"""
import io
import os
import re

from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter


class ExcelHelper:
    """Excel 导入导出辅助"""

    # 模板列名映射（支持中英文列名）
    COLUMN_MAP = {
        '题目': 'title', 'title': 'title', '题目标题': 'title',
        '类型': 'type', 'type': 'type', '题型': 'type',
        '分类': 'category', 'category': 'category', '区块': 'category',
        '难度': 'difficulty', 'difficulty': 'difficulty', '难度(1-9)': 'difficulty',
        '难度等级': 'level',
        '是否多选': 'is_multi', 'is_multi': 'is_multi', '多选题': 'is_multi',
        '选项A': 'opt_a', 'A': 'opt_a',
        '选项B': 'opt_b', 'B': 'opt_b',
        '选项C': 'opt_c', 'C': 'opt_c',
        '选项D': 'opt_d', 'D': 'opt_d',
        '选项E': 'opt_e', 'E': 'opt_e',
        '选项F': 'opt_f', 'F': 'opt_f',
        '答案': 'answer', 'answer': 'answer', '正确答案': 'answer',
        '解析': 'explanation', 'explanation': 'explanation',
    }

    TYPE_MAP = {
        'choice': 'choice', '选择': 'choice', '选择题': 'choice', '单选': 'choice', '单选题': 'choice',
        '多选': 'choice', '多选题': 'choice',
        'judge': 'judge', '判断': 'judge', '判断题': 'judge',
        'fill': 'fill', '填空': 'fill', '填空题': 'fill',
        'subjective': 'subjective', '主观': 'subjective', '主观题': 'subjective',
        '简答': 'subjective', '问答': 'subjective', '简答题': 'subjective', '问答题': 'subjective',
        '解答': 'subjective', '解答题': 'subjective', '论述': 'subjective', '论述题': 'subjective',
        '编程': 'subjective', '编程题': 'subjective', '代码': 'subjective', '开放': 'subjective',
        '主观实验': 'subjective',
    }

    @staticmethod
    def parse_excel(file_stream, created_by=1):
        """解析上传的 Excel 文件，返回题目列表和错误报告"""
        wb = load_workbook(file_stream)
        ws = wb.active

        # 读取表头，建立列映射
        headers = [str(c.value or '').strip() for c in ws[1]]
        col_idx = {}
        for idx, h in enumerate(headers):
            key = ExcelHelper.COLUMN_MAP.get(h, '')
            if key and key not in col_idx:
                col_idx[key] = idx  # 0-based index

        if 'title' not in col_idx:
            return {'success_count': 0, 'error_count': 0, 'errors': [{'row': 0, 'message': '未找到「题目」列，请检查模板格式'}],
                    'questions': []}

        questions = []
        errors = []
        for row_idx in range(2, ws.max_row + 1):
            try:
                row = [c.value for c in ws[row_idx]]
                if not row or all(v is None for v in row):
                    continue  # 跳过空行

                title = _cell_str(row, col_idx.get('title'))
                if not title:
                    continue  # 跳过无标题行

                qtype_raw = _cell_str(row, col_idx.get('type', -1)).strip()
                qtype = ExcelHelper.TYPE_MAP.get(qtype_raw, ExcelHelper.TYPE_MAP.get(qtype_raw.lower(), 'choice'))

                # 构建选项
                options = []
                if qtype == 'choice':
                    for key in ['opt_a', 'opt_b', 'opt_c', 'opt_d', 'opt_e', 'opt_f']:
                        if key in col_idx:
                            v = _cell_str(row, col_idx[key])
                            if v:
                                options.append(v)

                is_multi_str = _cell_str(row, col_idx.get('is_multi', -1))
                is_multi = is_multi_str in ('是', '1', 'true', 'yes', '多选', 'True') or qtype_raw in ('多选题', '多选')

                answer = _cell_str(row, col_idx.get('answer', -1))

                # 校验
                if qtype == 'choice':
                    if not options or len(options) < 2:
                        errors.append({'row': row_idx, 'message': f'选择题"{title[:20]}"选项不足2项'})
                        continue
                    if not answer:
                        errors.append({'row': row_idx, 'message': f'选择题"{title[:20]}"缺少答案'})
                        continue

                category = _cell_str(row, col_idx.get('category', -1)) or '默认'
                explanation = _cell_str(row, col_idx.get('explanation', -1))

                questions.append({
                    'title': title,
                    'type': qtype,
                    'category': category,
                    'is_multi': is_multi,
                    'options': options,
                    'answer': str(answer),
                    'explanation': explanation,
                    'created_by': created_by
                })
            except Exception as e:
                errors.append({'row': row_idx, 'message': str(e)})

        return {'questions': questions, 'errors': errors, 'total_rows': ws.max_row - 1}

    @staticmethod
    def generate_excel(questions):
        """生成 Excel 文件，返回 bytes"""
        wb = load_workbook.__module__  # no-op, just ensure module loaded
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = '题库'

        # 表头
        headers = ['序号', '题目', '类型', '分类', '难度', '是否多选',
                   '选项A', '选项B', '选项C', '选项D', '选项E', '选项F', '答案', '解析']
        header_font = Font(bold=True, size=11)
        header_fill = PatternFill('solid', fgColor='D9EAD3')
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin'))

        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

        # 数据行
        TYPE_LABELS = {'choice': '选择题', 'judge': '判断题', 'fill': '填空题', 'subjective': '主观题'}
        for i, q in enumerate(questions):
            row = i + 2
            ws.cell(row=row, column=1, value=i + 1).border = thin_border
            ws.cell(row=row, column=2, value=q.get('title', '')).border = thin_border
            type_label = TYPE_LABELS.get(q.get('type', ''), q.get('type', ''))
            ws.cell(row=row, column=3, value=type_label).border = thin_border
            ws.cell(row=row, column=4, value=q.get('category', '')).border = thin_border
            ws.cell(row=row, column=5, value=q.get('difficulty', 1)).border = thin_border
            is_multi = '是' if q.get('is_multi') else '否'
            ws.cell(row=row, column=6, value=is_multi).border = thin_border

            opts = q.get('options', [])
            if isinstance(opts, str):
                try:
                    import json
                    opts = json.loads(opts)
                except Exception:
                    opts = [o.strip() for o in opts.replace('|', ',').split(',') if o.strip()]
            if opts is None:
                opts = []
            for oi in range(6):
                val = opts[oi] if oi < len(opts) else ''
                ws.cell(row=row, column=7 + oi, value=val).border = thin_border

            ws.cell(row=row, column=13, value=q.get('answer', '')).border = thin_border
            ws.cell(row=row, column=14, value=q.get('explanation', '')).border = thin_border

        # 列宽
        widths = [6, 40, 10, 12, 6, 10, 16, 16, 16, 16, 8, 8, 30, 30]
        for c, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(c)].width = w

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output.getvalue()


class WordHelper:
    """Word 文档生成"""

    @staticmethod
    def generate_exam_paper(questions, title='测试试卷', description='', duration_minutes=120):
        """将题目列表生成 Word 试卷"""
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn

        doc = Document()

        # 页边距
        for section in doc.sections:
            section.top_margin = Cm(2.5)
            section.bottom_margin = Cm(2.5)
            section.left_margin = Cm(2.5)
            section.right_margin = Cm(2.5)

        # 标题
        title_para = doc.add_paragraph()
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = title_para.add_run(title)
        run.font.size = Pt(18)
        run.font.bold = True

        # 说明
        if description:
            desc = doc.add_paragraph(description)
            desc.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in desc.runs:
                run.font.size = Pt(10.5)

        # 考试信息
        info = doc.add_paragraph()
        info.alignment = WD_ALIGN_PARAGRAPH.CENTER
        info_run = info.add_run(f'答题时间：{duration_minutes} 分钟　　总分：')
        info_run.font.size = Pt(10.5)
        info_run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

        doc.add_paragraph()  # 空行

        TYPE_LABELS = {'choice': '选择题', 'judge': '判断题', 'fill': '填空题', 'subjective': '主观题'}

        # 按题型分组
        current_type = None
        q_num = 0
        for q in questions:
            q_type = q.get('type', 'choice')
            if q_type != current_type:
                current_type = q_type
                type_heading = doc.add_heading(level=2)
                run = type_heading.add_run(TYPE_LABELS.get(q_type, q_type))
                run.font.color.rgb = RGBColor(0x1a, 0x56, 0xdb)

            q_num += 1
            # 题号 + 标题
            q_text = f'{q_num}. {q.get("title", "")}'
            if q.get('difficulty'):
                q_text += f'  (难度: {q.get("difficulty")}/12)'
            p = doc.add_paragraph()
            run = p.add_run(q_text)
            run.font.size = Pt(11)
            run.font.bold = True

            # 选项
            if q_type == 'choice':
                opts = q.get('options', [])
                if isinstance(opts, str):
                    try:
                        import json
                        opts = json.loads(opts)
                    except Exception:
                        opts = [o.strip() for o in opts.replace('|', ',').split(',') if o.strip()]
                if opts:
                    labels = ['A', 'B', 'C', 'D', 'E', 'F']
                    for oi, opt in enumerate(opts):
                        if oi >= len(labels):
                            break
                        opt_para = doc.add_paragraph()
                        opt_para.paragraph_format.left_indent = Cm(1)
                        run = opt_para.add_run(f'{labels[oi]}. {opt}')
                        run.font.size = Pt(10.5)

            elif q_type == 'judge':
                judge_para = doc.add_paragraph()
                judge_para.paragraph_format.left_indent = Cm(1)
                run = judge_para.add_run('A. 对　　B. 错')
                run.font.size = Pt(10.5)

            elif q_type == 'fill':
                fill_para = doc.add_paragraph()
                fill_para.paragraph_format.left_indent = Cm(1)
                run = fill_para.add_run('答案：____________________')
                run.font.size = Pt(10.5)

            elif q_type == 'subjective':
                sub_para = doc.add_paragraph()
                sub_para.paragraph_format.left_indent = Cm(1)
                run = sub_para.add_run('答：')
                run.font.size = Pt(10.5)
                sub_para.add_run('_' * 60)

            doc.add_paragraph()  # 题目间空行

        output = io.BytesIO()
        doc.save(output)
        output.seek(0)
        return output.getvalue()


def _cell_str(row, index):
    """取单元格值转为字符串"""
    if index is None or index < 0 or index >= len(row):
        return ''
    v = row[index]
    if v is None:
        return ''
    if isinstance(v, (int, float)):
        return str(int(v)) if v == int(v) else str(v)
    return str(v).strip()


def _int_or(row, index, default=1):
    """取单元格值转为 int"""
    try:
        return int(float(_cell_str(row, index) or default))
    except (ValueError, TypeError):
        return default
