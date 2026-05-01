"""
计算各字表的拼字表，支持两种模式：

1. 完备模式（完备拼字表）：
   "部件-位置"作为部件单位。部件必须作为独立字符存在才能用于拼合。
   例如有了陪（⿰阝咅）并不能拼出部（⿰咅阝），因为阝和咅
   需要各自作为独立字符存在。

2. 基本模式（基本拼字表）：
   部件出现即可用。制作（或拼合）一个字后，它的所有 IDS 子部件
   都递归地变为可用部件。有了陪就能拼部。
"""

import os
import re
import sys
import unicodedata

# ── IDS 算符 ──────────────────────────────────────────────

# 二元算符
IDS_OPS_2 = set('⿰⿱⿴⿵⿶⿷⿸⿹⿺⿻⿼⿽⿾⿿')
# 三元算符
IDS_OPS_3 = set('⿲⿳')
ALL_IDS_OPS = IDS_OPS_2 | IDS_OPS_3


def arity(op):
    """返回 IDS 算符所需的操作数个数"""
    if op in IDS_OPS_3:
        return 3
    return 2


# ── 字符名 ↔ Unicode 转换 ─────────────────────────────────

def glyph_name_to_char(name):
    """将 Glyphs 字符形名称（如 uni4E00, u2F800）转为 Unicode 字符"""
    name = name.strip()
    if name.startswith('uni') and len(name) == 7:
        try:
            return chr(int(name[3:], 16))
        except ValueError:
            return None
    elif name.startswith('u') and len(name) >= 5:
        try:
            return chr(int(name[1:], 16))
        except ValueError:
            return None
    return None


def char_to_glyph_name(ch):
    """将 Unicode 字符转为 Glyphs 字符形名称"""
    cp = ord(ch)
    if cp <= 0xFFFF:
        return f"uni{cp:04X}"
    else:
        return f"u{cp:05X}"


# ── IDS 解析 ──────────────────────────────────────────────

def parse_ids_leaf_components(ids_str):
    """
    从 IDS 序列中提取所有叶子部件字符。
    返回字符列表，如果遇到无法解析的部件（如 CDP 引用），返回 None。
    """
    components = []
    i = 0
    length = len(ids_str)

    while i < length:
        ch = ids_str[i]

        if ch in ALL_IDS_OPS:
            # 跳过算符
            i += 1
        elif ch == '[':
            # 跳过地区标签 [G], [GTKV] 等
            while i < length and ids_str[i] != ']':
                i += 1
            if i < length:
                i += 1  # 跳过 ']'
        elif ch == '{':
            # CDP/HKCS 引用 {hkcs-xxxx-v01} → 无法解析
            return None
        elif ch == '&':
            # 旧式 CDP 引用 &CDP-XXXX; → 无法解析
            return None
        elif ch == '〓':
            # 占位符 → 无法解析
            return None
        elif ch in (' ', '\t', '\r', '\n'):
            i += 1
        else:
            components.append(ch)
            i += 1

    return components


def load_ids_database(ids_path):
    """
    加载 IDS 数据库。
    返回 dict: { 字符: IDS序列字符串 }
    优先选择无地区标签或第一个可用的 IDS 序列。
    """
    ids_map = {}
    with open(ids_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) < 3:
                continue

            char = parts[1].strip()
            if not char or len(char) != 1:
                continue

            # 从第三列开始是 IDS 变体
            best_ids = None
            for ids_variant in parts[2:]:
                ids_variant = ids_variant.strip()
                if not ids_variant:
                    continue

                # 如果 IDS 就是字符本身，说明是基础字，跳过
                clean = re.sub(r'\[.*?\]', '', ids_variant).strip()
                if clean == char:
                    continue

                # 优先选不带地区标签的
                if '[' not in ids_variant:
                    best_ids = ids_variant
                    break
                elif best_ids is None:
                    # 去掉地区标签后使用
                    best_ids = re.sub(r'\[.*?\]', '', ids_variant).strip()

            if best_ids and best_ids != char:
                ids_map[char] = best_ids

    return ids_map


def load_charset(path):
    """加载字表文件，返回 Unicode 字符列表（保持顺序，去重）"""
    chars = []
    seen = set()
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            name = line.strip()
            if not name:
                continue
            ch = glyph_name_to_char(name)
            if ch and ch not in seen:
                chars.append(ch)
                seen.add(ch)
    return chars


def _get_all_sub_components(ch, ids_map, cache=None):
    """
    递归提取字符的所有子部件（含自身）。
    用于基本模式：制作一个字后，其所有层级的子部件都变为可用。
    """
    if cache is None:
        cache = {}
    if ch in cache:
        return cache[ch]

    result = {ch}
    ids = ids_map.get(ch)
    if ids:
        components = parse_ids_leaf_components(ids)
        if components:
            for comp in components:
                result |= _get_all_sub_components(comp, ids_map, cache)

    cache[ch] = result
    return result


def compute_must_draw(charset_chars, ids_map, basic_mode=False):
    """
    顺序无关的最优拼字表计算。

    算法分三阶段：
    1. 找出所有无 IDS 拆解的基础字（必须画）
    2. 迭代解析：反复扫描，将所有部件已就绪的字标记为可拼合
    3. 贪心选择：对剩余未解析的字，每轮选出"能解锁最多其他字"的一个来画，
       自然实现跨部首均匀分布
    """
    sub_cache = {}

    # 预计算每个字的叶子部件
    char_leaves = {}
    for ch in charset_chars:
        ids = ids_map.get(ch)
        if ids:
            comps = parse_ids_leaf_components(ids)
            if comps:
                char_leaves[ch] = comps

    available = set()
    must_draw = []
    composable = []

    def mark_available(ch):
        if basic_mode:
            available.update(_get_all_sub_components(ch, ids_map, sub_cache))
        else:
            available.add(ch)

    def resolve_pass(unresolved):
        """扫描一轮，将所有部件已就绪的字标记为可拼合。返回是否有变化。"""
        newly = []
        for ch in list(unresolved):
            if all(c in available for c in char_leaves[ch]):
                newly.append(ch)
        for ch in newly:
            composable.append(ch)
            mark_available(ch)
            unresolved.discard(ch)
        return len(newly) > 0

    # ── 阶段 1：基础字 ──
    unresolved = set()
    for ch in charset_chars:
        if ch not in char_leaves:
            must_draw.append(ch)
            mark_available(ch)
        else:
            unresolved.add(ch)

    # ── 阶段 2：迭代解析 ──
    while resolve_pass(unresolved):
        pass

    # ── 阶段 3：贪心选择 ──
    while unresolved:
        # 建立反向索引：每个部件被哪些未解析字需要
        comp_needed_by = {}
        for ch in unresolved:
            for c in char_leaves[ch]:
                if c not in available:
                    comp_needed_by.setdefault(c, set()).add(ch)

        # 为每个候选字打分：它能提供多少"被需要的部件需求次数"
        best_char = None
        best_score = -1
        for candidate in unresolved:
            if basic_mode:
                new_comps = _get_all_sub_components(candidate, ids_map, sub_cache) - available
            else:
                new_comps = {candidate} - available
            score = sum(len(comp_needed_by.get(c, ())) for c in new_comps)
            if score > best_score or (score == best_score and best_char is None):
                best_score = score
                best_char = candidate

        must_draw.append(best_char)
        mark_available(best_char)
        unresolved.discard(best_char)

        # 解析新解锁的字
        while resolve_pass(unresolved):
            pass

    return must_draw, composable


def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    charset_dir = os.path.join(project_dir, '字表')

    # 查找 IDS 数据库
    import glob
    ids_files = glob.glob(os.path.join(project_dir, 'ids*.txt'))
    if not ids_files:
        print("❌ 错误：未找到 ids*.txt 文件！")
        sys.exit(1)
    ids_files.sort(key=os.path.getmtime, reverse=True)
    ids_path = ids_files[0]
    print(f"📖 加载 IDS 数据库：{os.path.basename(ids_path)}")
    ids_map = load_ids_database(ids_path)
    print(f"   已加载 {len(ids_map)} 条 IDS 拆解记录")

    # 收集所有字表
    charsets = {}
    if os.path.isdir(charset_dir):
        for fname in sorted(os.listdir(charset_dir)):
            fpath = os.path.join(charset_dir, fname)
            if os.path.isfile(fpath) and fname.endswith('.txt'):
                name = fname[:-4]
                charsets[name] = [fpath]

    # JF7000 特殊处理：将基本和所有扩展合成一个大表
    jf_dir = os.path.join(charset_dir, 'jf7000v0.9＿Glyph清單')
    if os.path.isdir(jf_dir):
        jf_files = []
        base = os.path.join(jf_dir, 'jf7000_base.txt')
        if os.path.isfile(base):
            jf_files.append(base)
        for fname in sorted(os.listdir(jf_dir)):
            fpath = os.path.join(jf_dir, fname)
            if fname.endswith('.txt') and fname != 'jf7000_base.txt':
                jf_files.append(fpath)
        if jf_files:
            charsets['jf7000'] = jf_files

    # 两种模式分别输出
    modes = [
        (False, '完备拼字表', '完备模式（部件须独立存在）'),
        (True,  '基本拼字表', '基本模式（部件出现即可用）'),
    ]

    base_output_dir = os.path.join(project_dir, '拼字表')
    os.makedirs(base_output_dir, exist_ok=True)

    for basic_mode, dir_name, mode_desc in modes:
        output_dir = os.path.join(base_output_dir, dir_name)
        os.makedirs(output_dir, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  {mode_desc}")
        print(f"  分析 {len(charsets)} 个字表")
        print(f"{'='*60}")

        for name, paths in charsets.items():
            all_chars = []
            seen = set()
            for p in paths:
                for ch in load_charset(p):
                    if ch not in seen:
                        all_chars.append(ch)
                        seen.add(ch)

            must_draw, auto_composed = compute_must_draw(
                all_chars, ids_map, basic_mode=basic_mode
            )

            output_path = os.path.join(output_dir, f'{name}.txt')
            with open(output_path, 'w', encoding='utf-8') as f:
                for ch in must_draw:
                    f.write(ch + '\n')

            total = len(all_chars)
            drawn = len(must_draw)
            composed = len(auto_composed)
            ratio = (composed / total * 100) if total > 0 else 0

            print(f"\n  📋 {name}")
            print(f"     字表总字数：{total}")
            print(f"     必须制作：  {drawn}")
            print(f"     可自动拼合：{composed}")
            print(f"     拼合率：    {ratio:.1f}%")
            print(f"     → {output_path}")

    print(f"\n{'='*60}")
    print(f"✅ 全部完成！")


if __name__ == '__main__':
    main()
