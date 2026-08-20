<template>
  <div class="ptl-root">
    <!-- 顶部：案例标题与简介 + 折叠按钮 + 功能模块 tab -->
    <div class="ptl-header">
      <div class="ptl-header-top">
        <h2 class="ptl-title">{{ activeCase.name }}</h2>
        <button class="ptl-collapse-btn" @click="collapsed = !collapsed"
                :title="collapsed ? '展开案例列表' : '收纳案例列表'">
          {{ collapsed ? '▾ 选择案例' : '▴ 收纳案例' }}
        </button>
      </div>
      <p class="ptl-intro">{{ activeCase.intro }}</p>
      <!-- 案例选择器（可收纳）：收纳后收起案例列表，展开后选择其他案例 -->
      <div v-show="!collapsed" class="ptl-case-picker">
        <div v-for="c in cases" :key="c.id" class="ptl-case-card"
             :class="{ active: c.id === activeCaseId }" @click="selectCase(c)">
          <span class="ptl-case-name">{{ c.name }}</span>
          <span class="ptl-case-meta">{{ c.features.length }} 个功能模块</span>
        </div>
      </div>
      <div class="ptl-tabs">
        <button v-for="f in activeCase.features" :key="f.id" class="ptl-tab"
                :class="{ active: f.id === activeId }" @click="activeId = f.id">
          {{ f.name }}
        </button>
      </div>
    </div>

    <!-- 中部：上半代码区 / 下半逐句解释区，各自独立滚动 -->
    <div class="ptl-main">
      <div class="ptl-pane ptl-code-pane">
        <div class="ptl-pane-head">
          <span class="ptl-pane-title">源码 · {{ activeFeature.name }}</span>
          <span class="ptl-pane-meta">{{ codeLines.length }} 行 · Python</span>
        </div>
        <div class="ptl-code-scroll">
          <pre class="ptl-code"><code v-for="(line, i) in codeLines" :key="i">{{ line }}</code></pre>
        </div>
      </div>

      <div class="ptl-pane ptl-explain-pane">
        <div class="ptl-pane-head">
          <span class="ptl-pane-title">逐句讲解 · {{ activeFeature.name }}</span>
          <span class="ptl-pane-meta">{{ activeFeature.lines.length }} 条</span>
        </div>
        <div class="ptl-explain-scroll">
          <div v-for="(ln, i) in activeFeature.lines" :key="i" class="ptl-line">
            <span class="ptl-line-idx">{{ i + 1 }}</span>
            <div class="ptl-line-body">
              <pre class="ptl-line-code">{{ ln.code }}</pre>
              <p class="ptl-line-explain">{{ ln.explain }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const activeId = ref('add_book')
const activeCaseId = ref('book_management')   // 当前选中的案例
const collapsed = ref(false)   // 案例选择器收纳/展开

// 案例完整源码（图书管理系统，约 90 行 Python）
const BOOK_CODE = `# -*- coding: utf-8 -*-
"""
图书管理系统（Python 案例）
功能：图书入库 / 图书查找 / 图书删除 / 图书统计
数据：books 列表存储，每项为字典 { "title": 书名, "author": 作者, "price": 价格 }
"""

# 全局图书列表：存放所有入库图书
books = []


def add_book():
    """功能1：图书入库 —— 输入书名/作者/价格"""
    title = input("请输入书名: ").strip()
    if not title:
        print("书名不能为空！")
        return
    author = input("请输入作者: ").strip()
    price_str = input("请输入价格: ").strip()
    try:
        price = float(price_str)
    except ValueError:
        print("价格格式错误，请输入数字！")
        return
    if price < 0:
        print("价格不能为负数！")
        return
    books.append({"title": title, "author": author, "price": price})
    print(f"图书《{title}》入库成功，当前共 {len(books)} 本")


def search_book():
    """功能2：图书查找 —— 按书名模糊查找"""
    keyword = input("请输入要查找的书名关键词: ").strip()
    if not keyword:
        print("查找关键词不能为空！")
        return
    results = [b for b in books if keyword in b["title"]]
    if not results:
        print(f"未找到书名包含「{keyword}」的图书")
        return
    print(f"共找到 {len(results)} 本图书：")
    for i, b in enumerate(results, 1):
        print(f"{i}. 《{b['title']}》 作者：{b['author']} 价格：{b['price']} 元")


def delete_book():
    """功能3：图书删除 —— 按书名删除"""
    title = input("请输入要删除的书名: ").strip()
    before = len(books)
    books[:] = [b for b in books if b["title"] != title]
    removed = before - len(books)
    if removed == 0:
        print(f"未找到《{title}》，无需删除")
    else:
        print(f"已删除 {removed} 本《{title}》")


def stats_books():
    """功能4：图书统计 —— 总数/总价/均价"""
    total = len(books)
    if total == 0:
        print("图书库为空，暂无统计数据")
        return
    total_price = sum(b["price"] for b in books)
    avg_price = total_price / total
    print(f"图书总数：{total} 本")
    print(f"图书总价：{total_price:.2f} 元")
    print(f"平均价格：{avg_price:.2f} 元")


def main():
    """主菜单循环：输入数字选择功能，输入 0 退出"""
    while True:
        print("\\n===== 图书管理系统 =====")
        print("1. 图书入库")
        print("2. 图书查找")
        print("3. 图书删除")
        print("4. 图书统计")
        print("0. 退出系统")
        choice = input("请输入操作编号: ").strip()
        if choice == "1":
            add_book()
        elif choice == "2":
            search_book()
        elif choice == "3":
            delete_book()
        elif choice == "4":
            stats_books()
        elif choice == "0":
            print("感谢使用，再见！")
            break
        else:
            print("输入无效，请重新输入！")


if __name__ == "__main__":
    main()
`

// 案例库：结构支持多个案例，后续可在 cases 数组追加新案例（每个含 name/intro/code/features/lines）
const cases = ref([
  {
    id: 'book_management',
    name: '图书管理系统',
    intro: '预置经典实战案例，按功能模块切换查看完整源码与逐句中文讲解。',
    features: [
      {
        id: 'add_book',
        name: '图书入库',
        code: BOOK_CODE,
        lines: [
      {
        code: `books = []  # 全局图书列表：存放所有入库图书`,
        explain: '初始化一个空列表 books，用于保存所有入库图书；每本图书用一个字典 {"title", "author", "price"} 表示。'
      },
      {
        code: `def add_book():\n    """功能1：图书入库 —— 输入书名/作者/价格"""`,
        explain: '定义 add_book 函数，实现图书入库：依次让用户输入书名、作者与价格。'
      },
      {
        code: `    title = input("请输入书名: ").strip()`,
        explain: '提示用户输入书名，并用 strip() 去掉首尾空白字符。'
      },
      {
        code: `    if not title:\n        print("书名不能为空！")\n        return`,
        explain: '书名为空时给出提示并直接返回，防止入库空书名。'
      },
      {
        code: `    author = input("请输入作者: ").strip()`,
        explain: '输入作者姓名并去除首尾空白。'
      },
      {
        code: `    price_str = input("请输入价格: ").strip()\n    try:\n        price = float(price_str)\n    except ValueError:\n        print("价格格式错误，请输入数字！")\n        return`,
        explain: '先以字符串接收价格，再用 float() 转成数值；若输入不是数字会抛出 ValueError，被 except 捕获后提示并返回，保证价格合法。'
      },
      {
        code: `    if price < 0:\n        print("价格不能为负数！")\n        return`,
        explain: '校验价格不能为负数，非法输入直接返回。'
      },
      {
        code: `    books.append({"title": title, "author": author, "price": price})`,
        explain: '将新书以字典形式追加到 books 列表末尾，完成入库。'
      },
      {
        code: `    print(f"图书《{title}》入库成功，当前共 {len(books)} 本")`,
        explain: '使用 f-string 输出入库成功信息及当前图书总数（即 books 的长度）。'
      }
    ]
  },
  {
    id: 'search_book',
    name: '图书查找',
    code: BOOK_CODE,
    lines: [
      {
        code: `def search_book():\n    """功能2：图书查找 —— 按书名模糊查找"""`,
        explain: '定义 search_book 函数，实现按书名关键词进行模糊查找。'
      },
      {
        code: `    keyword = input("请输入要查找的书名关键词: ").strip()\n    if not keyword:\n        print("查找关键词不能为空！")\n        return`,
        explain: '输入查找关键词并去除空白；关键词为空时提示并直接返回。'
      },
      {
        code: `    results = [b for b in books if keyword in b["title"]]`,
        explain: '列表推导式：遍历 books，筛选出书名中包含关键词的图书，得到结果列表 results。'
      },
      {
        code: `    if not results:\n        print(f"未找到书名包含「{keyword}」的图书")\n        return`,
        explain: '若 results 为空，说明没有匹配图书，提示后返回。'
      },
      {
        code: `    print(f"共找到 {len(results)} 本图书：")`,
        explain: '输出匹配到的图书数量。'
      },
      {
        code: `    for i, b in enumerate(results, 1):\n        print(f"{i}. 《{b['title']}》 作者：{b['author']} 价格：{b['price']} 元")`,
        explain: '用 enumerate 从 1 开始编号，逐本输出书名、作者与价格，方便用户查看。'
      }
    ]
  },
  {
    id: 'delete_book',
    name: '图书删除',
    code: BOOK_CODE,
    lines: [
      {
        code: `def delete_book():\n    """功能3：图书删除 —— 按书名删除"""`,
        explain: '定义 delete_book 函数，实现按书名删除图书（同名图书会一并删除）。'
      },
      {
        code: `    title = input("请输入要删除的书名: ").strip()`,
        explain: '输入要删除的书名并去除首尾空白。'
      },
      {
        code: `    before = len(books)\n    books[:] = [b for b in books if b["title"] != title]\n    removed = before - len(books)`,
        explain: '先记录删除前数量；再用列表切片赋值将书名不匹配的图书保留下来（原地删除匹配项）；removed 为实际删除的本数。'
      },
      {
        code: `    if removed == 0:\n        print(f"未找到《{title}》，无需删除")\n    else:\n        print(f"已删除 {removed} 本《{title}》")`,
        explain: 'removed 为 0 说明库中不存在该书，否则输出实际删除的图书数量。'
      }
    ]
  },
  {
    id: 'stats_books',
    name: '图书统计',
    code: BOOK_CODE,
    lines: [
      {
        code: `def stats_books():\n    """功能4：图书统计 —— 总数/总价/均价"""`,
        explain: '定义 stats_books 函数，统计图书总数、总价与平均价格。'
      },
      {
        code: `    total = len(books)`,
        explain: '图书总数即 books 列表的长度。'
      },
      {
        code: `    if total == 0:\n        print("图书库为空，暂无统计数据")\n        return`,
        explain: '图书库为空时提示并返回，避免后续计算出现除零错误。'
      },
      {
        code: `    total_price = sum(b["price"] for b in books)`,
        explain: '用生成器表达式遍历所有图书并累加价格，得到总价。'
      },
      {
        code: `    avg_price = total_price / total`,
        explain: '总价除以图书总数得到平均价格。'
      },
      {
        code: `    print(f"图书总数：{total} 本")\n    print(f"图书总价：{total_price:.2f} 元")\n    print(f"平均价格：{avg_price:.2f} 元")`,
        explain: '输出统计结果，价格使用 :.2f 保留两位小数。'
      },
      {
        code: `def main():\n    while True:\n        print("\\n===== 图书管理系统 =====")\n        print("1. 图书入库")\n        print("2. 图书查找")\n        print("3. 图书删除")\n        print("4. 图书统计")\n        print("0. 退出系统")\n        choice = input("请输入操作编号: ").strip()`,
        explain: '主菜单循环：进入 while True 死循环，打印菜单让用户选择，输入对应数字执行相应功能。'
      },
      {
        code: `        if choice == "1":\n            add_book()\n        elif choice == "2":\n            search_book()\n        elif choice == "3":\n            delete_book()\n        elif choice == "4":\n            stats_books()\n        elif choice == "0":\n            print("感谢使用，再见！")\n            break\n        else:\n            print("输入无效，请重新输入！")`,
        explain: '根据用户输入分发到对应函数；输入 0 时打印再见并 break 退出循环；其他输入提示无效并重新选择。'
      },
      {
        code: `if __name__ == "__main__":\n    main()`,
        explain: 'Python 程序入口：仅当脚本被直接运行时才调用 main()，被导入为模块时不自动执行。'
      }
        ]
      }
    ]
  }
])

const activeCase = computed(() => cases.value.find(c => c.id === activeCaseId.value) || cases.value[0])
const activeFeature = computed(() => activeCase.value.features.find(f => f.id === activeId.value) || activeCase.value.features[0])
const codeLines = computed(() => activeFeature.value.code.split('\n'))

// 切换案例：同时将功能 tab 重置为该案例的第一个功能模块
function selectCase(c) {
  activeCaseId.value = c.id
  activeId.value = c.features[0] ? c.features[0].id : ''
}
</script>

<style scoped>
.ptl-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}
.ptl-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}
.ptl-header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.ptl-collapse-btn {
  flex-shrink: 0;
  padding: 4px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  font-size: 12px;
  color: #475569;
  cursor: pointer;
  transition: all 0.15s;
}
.ptl-collapse-btn:hover { border-color: #3b82f6; color: #2563eb; }
.ptl-title { margin: 0 0 4px; font-size: 18px; font-weight: 600; color: #1e293b; }
.ptl-intro { margin: 0 0 12px; font-size: 12px; color: #64748b; }
.ptl-case-picker {
  display: flex; gap: 10px; flex-wrap: wrap;
  margin: 0 0 12px; padding: 12px; border-radius: 8px; background: #f8fafc;
}
.ptl-case-card {
  padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 8px;
  background: #fff; cursor: pointer; min-width: 160px;
  display: flex; flex-direction: column; gap: 4px; transition: all 0.15s;
}
.ptl-case-card:hover { border-color: #93c5fd; }
.ptl-case-card.active { background: #eff6ff; border-color: #3b82f6; }
.ptl-case-name { font-size: 13px; font-weight: 600; color: #1e293b; }
.ptl-case-card.active .ptl-case-name { color: #2563eb; }
.ptl-case-meta { font-size: 11px; color: #94a3b8; }
.ptl-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
.ptl-tab {
  padding: 5px 14px; border: 1px solid #e2e8f0; border-radius: 16px;
  background: #fff; font-size: 12px; color: #475569; cursor: pointer;
  transition: all 0.15s;
}
.ptl-tab:hover { border-color: #93c5fd; color: #2563eb; }
.ptl-tab.active { background: #eff6ff; border-color: #3b82f6; color: #2563eb; font-weight: 600; }

.ptl-main { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.ptl-pane { flex: 1; min-height: 0; display: flex; flex-direction: column; }

/* 上半：案例代码区（深色背景，参考 AIPractice .code-textarea 风格） */
.ptl-code-pane { background: #0f172a; }
.ptl-code-pane .ptl-pane-head { background: #1e293b; }
.ptl-code-pane .ptl-pane-title { color: #94a3b8; }
.ptl-code-pane .ptl-pane-meta { color: #546e7a; }
.ptl-code-scroll { flex: 1; overflow-y: auto; padding: 12px 16px; }
.ptl-code {
  margin: 0; font-family: 'Consolas', 'Monaco', monospace; font-size: 13px;
  line-height: 1.6; color: #e2e8f0; white-space: pre; tab-size: 4;
}
.ptl-code code { display: block; }

/* 下半：逐句解释区（白底） */
.ptl-explain-pane { background: #fff; border-top: 1px solid #e2e8f0; }
.ptl-pane-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; flex-shrink: 0;
}
.ptl-pane-title { font-size: 12px; font-weight: 600; color: #475569; }
.ptl-pane-meta { font-size: 11px; color: #94a3b8; }
.ptl-explain-scroll { flex: 1; overflow-y: auto; padding: 12px 16px; }
.ptl-line { display: flex; gap: 10px; padding: 10px 0; border-bottom: 1px dashed #e2e8f0; }
.ptl-line:last-child { border-bottom: none; }
.ptl-line-idx {
  flex-shrink: 0; width: 22px; height: 22px; border-radius: 50%;
  background: #eff6ff; color: #3b82f6; font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.ptl-line-body { flex: 1; min-width: 0; }
.ptl-line-code {
  margin: 0 0 6px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;
  padding: 6px 10px; font-family: 'Consolas', 'Monaco', monospace; font-size: 12px;
  line-height: 1.5; color: #0f172a; white-space: pre-wrap; word-break: break-all;
}
.ptl-line-explain { margin: 0; font-size: 13px; color: #475569; line-height: 1.6; }
</style>
