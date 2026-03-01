#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 SQLAlchemy 模型自动生成数据库 ER 关系图（UML）

使用方式:
    python scripts/generate_db_uml.py

依赖:
    pip install graphviz
    # 系统还需要安装 graphviz:
    # macOS: brew install graphviz
    # Ubuntu: sudo apt-get install graphviz
    # Windows: choco install graphviz

输出:
    docs/database_er_diagram.png  (PNG 图片)
    docs/database_er_diagram.dot  (DOT 源文件，可用在线工具渲染)
"""

import sys
import os

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from graphviz import Digraph
from sqlalchemy import inspect as sa_inspect
from src.storage.metadata.models import Base


# ============================================================
# 配置
# ============================================================
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs')
OUTPUT_NAME = 'database_er_diagram'

# 表的中文名映射
TABLE_LABELS = {
    'documents':           'Document\n(文档表 · Bronze层)',
    'parse_tasks':         'ParseTask\n(解析任务表)',
    'parsed_documents':    'ParsedDocument\n(解析文档表 · Silver层)',
    'images':              'Image\n(图片元数据表)',
    'image_annotations':   'ImageAnnotation\n(图片标注表)',
    'document_chunks':     'DocumentChunk\n(文档分块表)',
    'crawl_tasks':         'CrawlTask\n(爬取任务表)',
    'embedding_tasks':     'EmbeddingTask\n(向量化任务表)',
    'validation_logs':     'ValidationLog\n(验证日志表)',
    'quarantine_records':  'QuarantineRecord\n(隔离记录表)',
    'hs_listed_companies': 'ListedCompany\n(A股上市公司表)',
    'hk_listed_companies': 'HKListedCompany\n(港股上市公司表)',
    'us_listed_companies': 'USListedCompany\n(美股上市公司表)',
}

# 表的颜色分组
TABLE_COLORS = {
    # 核心文档流水线 - 蓝色系
    'documents':           '#4A90D9',
    'parse_tasks':         '#5BA0E0',
    'parsed_documents':    '#6CB0E8',
    'images':              '#7DC0F0',
    'image_annotations':   '#8ED0F8',
    'document_chunks':     '#5BA0E0',
    # 任务管理 - 绿色系
    'crawl_tasks':         '#5CB85C',
    'embedding_tasks':     '#6EC86E',
    # 数据质量 - 橙色系
    'validation_logs':     '#F0AD4E',
    'quarantine_records':  '#EC971F',
    # 基础数据 - 紫色系
    'hs_listed_companies': '#9B59B6',
    'hk_listed_companies': '#8E44AD',
    'us_listed_companies': '#A569BD',
}

# 类型缩写映射
TYPE_SHORT = {
    'UUID':       'UUID',
    'VARCHAR':    'STR',
    'STRING':     'STR',
    'INTEGER':    'INT',
    'BIGINTEGER': 'BIGINT',
    'TEXT':       'TEXT',
    'BOOLEAN':    'BOOL',
    'FLOAT':      'FLOAT',
    'DATETIME':   'DATETIME',
    'DATE':       'DATE',
    'JSON':       'JSON',
}


def get_type_short(col_type):
    """获取列类型的简写"""
    type_name = str(col_type).split('(')[0].upper()
    return TYPE_SHORT.get(type_name, type_name)


def build_table_html(table_name, columns, pk_cols, fk_cols):
    """构建一个表的 HTML label（用于 graphviz record/HTML 节点）"""
    color = TABLE_COLORS.get(table_name, '#999999')
    label = TABLE_LABELS.get(table_name, table_name)
    # 标题用换行分两行
    title_lines = label.split('\n')
    title_main = title_lines[0]
    title_sub = title_lines[1] if len(title_lines) > 1 else ''

    rows = []
    for col_name, col_type_str, nullable, is_pk, is_fk in columns:
        icon = ''
        if is_pk:
            icon = '🔑 '
        elif is_fk:
            icon = '🔗 '

        null_str = '' if not nullable else ' · NULL'
        row = f'<TR><TD ALIGN="LEFT" PORT="{col_name}">{icon}{col_name}</TD><TD ALIGN="LEFT"><FONT COLOR="#888888">{col_type_str}{null_str}</FONT></TD></TR>'
        rows.append(row)

    rows_html = '\n'.join(rows)

    html = f'''<
    <TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="6">
        <TR><TD COLSPAN="2" BGCOLOR="{color}"><FONT COLOR="white"><B>{title_main}</B></FONT></TD></TR>
        <TR><TD COLSPAN="2" BGCOLOR="{color}AA"><FONT COLOR="white" POINT-SIZE="10">{title_sub}</FONT></TD></TR>
        {rows_html}
    </TABLE>
    >'''
    return html


def extract_models_info():
    """从 SQLAlchemy Base 中提取所有模型信息"""
    tables_info = {}
    foreign_keys_info = []

    for mapper in Base.registry.mappers:
        cls = mapper.class_
        table = cls.__table__
        table_name = table.name

        # 收集列信息
        pk_col_names = {col.name for col in table.primary_key.columns}
        fk_col_names = set()
        for fk_constraint in table.foreign_key_constraints:
            for col in fk_constraint.columns:
                fk_col_names.add(col.name)

        columns = []
        for col in table.columns:
            col_type_str = get_type_short(col.type)
            is_pk = col.name in pk_col_names
            is_fk = col.name in fk_col_names
            nullable = col.nullable and not is_pk
            columns.append((col.name, col_type_str, nullable, is_pk, is_fk))

        tables_info[table_name] = {
            'columns': columns,
            'pk_cols': pk_col_names,
            'fk_cols': fk_col_names,
        }

        # 收集外键关系
        for fk_constraint in table.foreign_key_constraints:
            for fk_col in fk_constraint.columns:
                for fk_element in fk_col.foreign_keys:
                    ref_table = fk_element.column.table.name
                    ref_col = fk_element.column.name
                    on_delete = fk_constraint.ondelete or ''
                    foreign_keys_info.append({
                        'from_table': table_name,
                        'from_col': fk_col.name,
                        'to_table': ref_table,
                        'to_col': ref_col,
                        'on_delete': on_delete,
                    })

    # DocumentChunk 的 parent_chunk_id 自引用（没有显式 FK 约束，手动添加）
    if 'document_chunks' in tables_info:
        has_self_ref = any(
            fk['from_table'] == 'document_chunks' and fk['to_table'] == 'document_chunks'
            for fk in foreign_keys_info
        )
        if not has_self_ref:
            foreign_keys_info.append({
                'from_table': 'document_chunks',
                'from_col': 'parent_chunk_id',
                'to_table': 'document_chunks',
                'to_col': 'id',
                'on_delete': '自引用',
            })

    return tables_info, foreign_keys_info


def generate_diagram():
    """生成 ER 图"""
    tables_info, foreign_keys_info = extract_models_info()

    # 创建有向图
    dot = Digraph(
        name='FinNet Database ER Diagram',
        comment='FinNet 数据库模型 ER 关系图',
        format='png',
        engine='dot',
    )

    # 全局属性
    dot.attr(
        rankdir='TB',
        fontname='Helvetica',
        fontsize='14',
        bgcolor='#FAFAFA',
        pad='0.5',
        nodesep='0.8',
        ranksep='1.2',
        label='<<B><FONT POINT-SIZE="24">FinNet 数据库模型 ER 关系图</FONT></B>>',
        labelloc='t',
    )
    dot.attr('node', shape='plaintext', fontname='Helvetica', fontsize='11')
    dot.attr('edge', fontname='Helvetica', fontsize='9', color='#666666')

    # ---- 子图分组 ----

    # 核心文档流水线
    with dot.subgraph(name='cluster_pipeline') as c:
        c.attr(label='核心文档处理流水线', style='dashed', color='#4A90D9', fontcolor='#4A90D9', fontsize='13')
        for tbl in ['documents', 'parse_tasks', 'parsed_documents', 'images', 'image_annotations', 'document_chunks']:
            if tbl in tables_info:
                info = tables_info[tbl]
                html = build_table_html(tbl, info['columns'], info['pk_cols'], info['fk_cols'])
                c.node(tbl, label=html)

    # 任务管理
    with dot.subgraph(name='cluster_tasks') as c:
        c.attr(label='任务管理', style='dashed', color='#5CB85C', fontcolor='#5CB85C', fontsize='13')
        for tbl in ['crawl_tasks', 'embedding_tasks']:
            if tbl in tables_info:
                info = tables_info[tbl]
                html = build_table_html(tbl, info['columns'], info['pk_cols'], info['fk_cols'])
                c.node(tbl, label=html)

    # 数据质量
    with dot.subgraph(name='cluster_quality') as c:
        c.attr(label='数据质量管理', style='dashed', color='#F0AD4E', fontcolor='#EC971F', fontsize='13')
        for tbl in ['validation_logs', 'quarantine_records']:
            if tbl in tables_info:
                info = tables_info[tbl]
                html = build_table_html(tbl, info['columns'], info['pk_cols'], info['fk_cols'])
                c.node(tbl, label=html)

    # 基础数据
    with dot.subgraph(name='cluster_base') as c:
        c.attr(label='上市公司基础数据', style='dashed', color='#9B59B6', fontcolor='#8E44AD', fontsize='13')
        for tbl in ['hs_listed_companies', 'hk_listed_companies', 'us_listed_companies']:
            if tbl in tables_info:
                info = tables_info[tbl]
                html = build_table_html(tbl, info['columns'], info['pk_cols'], info['fk_cols'])
                c.node(tbl, label=html)

    # ---- 外键边 ----
    edge_styles = {
        'CASCADE':  {'color': '#E74C3C', 'style': 'solid',  'label_suffix': ' (CASCADE)'},
        'SET NULL': {'color': '#F39C12', 'style': 'dashed', 'label_suffix': ' (SET NULL)'},
        '自引用':    {'color': '#9B59B6', 'style': 'dotted', 'label_suffix': ' (自引用)'},
    }

    for fk in foreign_keys_info:
        on_del = fk['on_delete'].upper() if fk['on_delete'] else ''
        style_info = edge_styles.get(on_del, edge_styles.get(fk['on_delete'], {'color': '#666666', 'style': 'solid', 'label_suffix': ''}))

        edge_label = f"{fk['from_col']}"
        dot.edge(
            f"{fk['from_table']}:{fk['from_col']}",
            f"{fk['to_table']}:{fk['to_col']}",
            label=edge_label,
            color=style_info['color'],
            style=style_info['style'],
            arrowhead='crow',
            arrowtail='tee',
            dir='both',
            penwidth='1.5',
        )

    return dot


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_NAME)

    print("📊 正在从 SQLAlchemy 模型提取表结构...")
    dot = generate_diagram()

    # 保存 .dot 源文件（始终保存）
    dot_path = output_path + '.dot'
    dot.save(dot_path)
    print(f"✅ DOT 源文件已保存: {dot_path}")

    # 尝试渲染 PNG
    try:
        rendered_path = dot.render(output_path, cleanup=False)
        print(f"✅ PNG 图片已生成: {rendered_path}")
        print(f"\n🎉 完成！请打开 {rendered_path} 查看 ER 关系图")
    except Exception as e:
        print(f"\n⚠️  PNG 渲染失败（可能未安装 graphviz 系统包）: {e}")
        print(f"   DOT 源文件已保存在: {dot_path}")
        print(f"\n📋 解决方案（任选其一）:")
        print(f"   1. 安装 graphviz 后重新运行:")
        print(f"      macOS:   brew install graphviz")
        print(f"      Ubuntu:  sudo apt-get install graphviz")
        print(f"      Windows: choco install graphviz")
        print(f"   2. 在线渲染: 复制 {dot_path} 内容到 https://dreampuf.github.io/GraphvizOnline/")
        print(f"   3. VS Code: 安装 'Graphviz Preview' 扩展，打开 .dot 文件预览")
        sys.exit(1)


if __name__ == '__main__':
    main()
