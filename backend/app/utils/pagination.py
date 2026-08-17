# -*- coding: utf-8 -*-
"""
分页工具模块 — 为列表端点提供统一的内存分页支持
"""


def get_pagination_params(args):
  """从 request.args 解析 page 和 page_size 参数

  Args:
      args: Flask request.args (ImmutableMultiDict)

  Returns:
      (page, page_size) 元组，page >= 1，1 <= page_size <= 100
  """
  try:
    page = int(args.get('page', '1'))
  except (TypeError, ValueError):
    page = 1
  try:
    page_size = int(args.get('page_size', '20'))
  except (TypeError, ValueError):
    page_size = 20

  page = max(1, page)
  page_size = max(1, min(100, page_size))
  return page, page_size


def paginate_list(data, page, page_size):
  """对 Python list 做内存分页

  Args:
      data: 原始列表
      page: 页码（从 1 开始）
      page_size: 每页条数

  Returns:
      (items, total) 元组 — 当前页数据切片和总条数
  """
  if not isinstance(data, list):
    return data, 0
  total = len(data)
  start = (page - 1) * page_size
  end = start + page_size
  return data[start:end], total


def paginate_response(items, page, page_size, total):
  """构建统一的分页响应数据

  Args:
      items: 当前页的数据列表
      page: 当前页码
      page_size: 每页条数
      total: 总记录数

  Returns:
      包含 items 和 pagination 的字典
  """
  total_pages = max(1, (total + page_size - 1) // page_size) if page_size > 0 else 1
  return {
    "items": items,
    "pagination": {
      "page": page,
      "page_size": page_size,
      "total": total,
      "total_pages": total_pages,
      "has_next": page < total_pages,
      "has_prev": page > 1
    }
  }
