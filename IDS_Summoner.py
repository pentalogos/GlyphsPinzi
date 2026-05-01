# MenuTitle: 召唤同族字
# -*- coding: utf-8 -*-
"""
召唤同族字 (IDS Summoner)

在当前编辑的汉字基础上，通过 IDS 部件关系找到所有"同族"字符，
并在标签页中打开，方便直接取用已有部件来拼字。

两种模式:
  - 宽松模式（默认）：只要共享任一叶子部件即视为同族
  - 严格模式：必须在 IDS 树中相同结构位置出现相同部件才视为同族

用法：在 Glyphs.app 中打开某个汉字的编辑界面后运行此脚本。
"""

from __future__ import print_function, unicode_literals
import os
import sys

# ============================================================
# IDS 操作符
# ============================================================

IDS_OPERATORS = {
    '\u2FF0': 2,  # ⿰ 左右
    '\u2FF1': 2,  # ⿱ 上下
    '\u2FF2': 3,  # ⿲ 左中右
    '\u2FF3': 3,  # ⿳ 上中下
    '\u2FF4': 2,  # ⿴ 全包围
    '\u2FF5': 2,  # ⿵ 上三包围
    '\u2FF6': 2,  # ⿶ 下三包围
    '\u2FF7': 2,  # ⿷ 左三包围
    '\u2FF8': 2,  # ⿸ 左上包围
    '\u2FF9': 2,  # ⿹ 右上包围
    '\u2FFA': 2,  # ⿺ 左下包围
    '\u2FFB': 2,  # ⿻ 重叠
}


# ============================================================
# 数据加载 —— 复用 IDS_Composer 的内嵌数据
# ============================================================

def _load_ids_data():
    """
    从 IDS_Composer.py 源码中提取内嵌 IDS 数据。
    若提取失败则尝试直接读取同目录下的原始 IDS 文件。

    不使用 import 方式，因为 IDS_Composer.py 的 main() 会在
    导入时立即执行。改为用正则表达式从源码中提取 EMBEDDED_DATA。
    """
    import zlib, base64, re

    # 方案 A：从 IDS_Composer.py 源码中提取 EMBEDDED_DATA
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        composer_path = os.path.join(script_dir, "IDS_Composer.py")
        if os.path.exists(composer_path):
            with open(composer_path, 'r', encoding='utf-8') as f:
                source = f.read()

            # 提取 "ids" 对应的 base64 字符串
            # EMBEDDED_DATA 格式: {"ids": "xxxxx", ...}
            pattern = r'"ids"\s*:\s*"([^"]+)"'
            match = re.search(pattern, source)
            if match:
                b64_str = match.group(1)
                data = base64.b64decode(b64_str)
                return zlib.decompress(data).decode('utf-8')
    except Exception:
        pass

    # 方案 B（回退）：直接读取原始文件
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ids_path = os.path.join(script_dir, "ids-20240112.txt")
        if os.path.exists(ids_path):
            with open(ids_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception:
        pass

    return None


def load_ids_database():
    """
    加载 IDS 数据库。
    返回:
        char_to_ids: dict, 字符 -> IDS 描述字符串
        char_to_leaves: dict, 字符 -> 叶子部件集合
        char_to_positioned: dict, 字符 -> 带位置部件集合 {(op, idx, component), ...}
    """
    raw_data = _load_ids_data()
    if raw_data is None:
        return {}, {}, {}

    char_to_ids = {}
    char_to_leaves = {}
    char_to_positioned = {}

    for line in raw_data.splitlines():
        line = line.strip('\r\n')
        if not line or line.startswith('#'):
            continue

        parts = line.split('\t')
        if len(parts) < 3:
            continue

        char = parts[1].strip()
        if not char or len(char) != 1:
            continue

        # 取第一个可用的 IDS 描述
        best_ids = None
        for ids_col in parts[2:]:
            ids_str = ids_col.strip()
            if not ids_str:
                continue
            if ids_str == char:
                break
            if '{' in ids_str or '}' in ids_str:
                continue
            if '〓' in ids_str or '？' in ids_str or '?' in ids_str:
                continue
            best_ids = ids_str
            break

        if best_ids and best_ids != char:
            char_to_ids[char] = best_ids

            # 提取叶子部件
            leaves = set()
            for ch in best_ids:
                cp = ord(ch)
                if 0x2FF0 <= cp <= 0x2FFB:
                    continue
                if cp < 0x20:
                    continue
                leaves.add(ch)
            if leaves:
                char_to_leaves[char] = leaves

            # 提取带位置的部件
            positioned = extract_positioned_components(best_ids)
            if positioned:
                char_to_positioned[char] = positioned

    return char_to_ids, char_to_leaves, char_to_positioned


# ============================================================
# IDS 结构化解析
# ============================================================

def extract_positioned_components(ids_string):
    """
    递归解析 IDS 字符串，返回 (operator, position_index, component) 三元组集合。
    用于严格模式下的部件位置匹配。

    例:
        "⿰日月" -> {("⿰", 0, "日"), ("⿰", 1, "月")}
        "⿱⿰日月水" -> {("⿰", 0, "日"), ("⿰", 1, "月"), ("⿱", 1, "水")}

    使用栈来正确处理嵌套结构。
    """
    if not ids_string:
        return None

    result = set()
    pos = [0]  # 用列表模拟可变引用

    def parse(ids_str):
        if pos[0] >= len(ids_str):
            return None

        ch = ids_str[pos[0]]
        cp = ord(ch)

        if 0x2FF0 <= cp <= 0x2FFB:
            op = ch
            arity = IDS_OPERATORS.get(op, 2)
            pos[0] += 1

            for i in range(arity):
                if pos[0] >= len(ids_str):
                    break
                next_ch = ids_str[pos[0]]
                next_cp = ord(next_ch)

                if 0x2FF0 <= next_cp <= 0x2FFB:
                    # 嵌套的操作符，递归解析
                    parse(ids_str)
                else:
                    # 叶子部件
                    if next_cp >= 0x20:
                        result.add((op, i, next_ch))
                    pos[0] += 1
        else:
            # 单个字符（不应在顶层出现，但处理以防万一）
            pos[0] += 1

    parse(ids_string)
    return result if result else None


# ============================================================
# 同族字检索
# ============================================================

def find_related_loose(current_char, char_to_leaves, existing_chars):
    """
    宽松模式：找到所有与当前字有部件关系的字符。
    仅返回字体中已有的字符。

    覆盖三种关系：
      1. 共享叶子部件（如 明 和 晴 共享 日）
      2. 当前字的直接部件本身（如 伀 的部件 公）
      3. 包含当前字作为部件的字（如 从 公 召唤 伀）
    """
    current_leaves = char_to_leaves.get(current_char)
    if not current_leaves:
        return []

    related = set()

    # 1. 共享叶子部件的字
    for ch, leaves in char_to_leaves.items():
        if ch == current_char:
            continue
        if ch not in existing_chars:
            continue
        if current_leaves & leaves:
            related.add(ch)

    # 2. 当前字的直接部件本身（如 伀→公）
    for leaf in current_leaves:
        if leaf != current_char and leaf in existing_chars:
            related.add(leaf)

    # 3. 包含当前字作为部件的字（如 公→伀）
    for ch, leaves in char_to_leaves.items():
        if ch == current_char:
            continue
        if ch not in existing_chars:
            continue
        if current_char in leaves:
            related.add(ch)

    return sorted(related, key=lambda x: ord(x))


def find_related_strict(current_char, char_to_positioned, existing_chars):
    """
    严格模式：找到所有与当前字在相同结构位置共享部件的字符。
    仅返回字体中已有的字符。

    覆盖三种关系：
      1. 共享位置部件三元组（如 明(⿰,0,日) 和 晴(⿰,0,日)）
      2. 当前字的直接部件本身
      3. 包含当前字作为位置部件的字
    """
    current_pos = char_to_positioned.get(current_char)
    if not current_pos:
        return []

    # 提取当前字的所有直接部件字符
    current_components = {comp for (_, _, comp) in current_pos}

    related = set()

    # 1. 共享位置部件三元组的字
    for ch, pos_set in char_to_positioned.items():
        if ch == current_char:
            continue
        if ch not in existing_chars:
            continue
        if current_pos & pos_set:
            related.add(ch)

    # 2. 当前字的直接部件本身
    for comp in current_components:
        if comp != current_char and comp in existing_chars:
            related.add(comp)

    # 3. 包含当前字作为位置部件的字
    for ch, pos_set in char_to_positioned.items():
        if ch == current_char:
            continue
        if ch not in existing_chars:
            continue
        ch_components = {c for (_, _, c) in pos_set}
        if current_char in ch_components:
            related.add(ch)

    return sorted(related, key=lambda x: ord(x))


# ============================================================
# Glyphs.app 集成
# ============================================================

def get_existing_unicode_chars(font):
    """获取字体中所有已有字符型的 Unicode 字符集合。"""
    chars = set()
    for glyph in font.glyphs:
        if glyph.unicode:
            try:
                cp = int(glyph.unicode, 16)
                chars.add(chr(cp))
            except (ValueError, OverflowError):
                pass
    return chars


def get_current_char(font):
    """获取当前编辑标签页中活动字符。"""
    tab = font.currentTab
    if tab is None:
        return None

    try:
        layer = tab.activeLayer()
    except:
        try:
            layer = font.selectedLayers[0]
        except:
            return None

    if layer is None:
        return None

    glyph = layer.parent
    if glyph is None:
        return None

    # 尝试从 unicode 属性获取字符
    if glyph.unicode:
        try:
            return chr(int(glyph.unicode, 16))
        except (ValueError, OverflowError):
            pass

    # 尝试从 glyph name 推断
    name = glyph.name
    if name:
        if name.startswith('uni') and len(name) == 7:
            try:
                return chr(int(name[3:], 16))
            except (ValueError, OverflowError):
                pass
        elif name.startswith('u') and len(name) >= 5:
            try:
                return chr(int(name[1:], 16))
            except (ValueError, OverflowError):
                pass

    return None


def char_to_glyph_name(ch):
    """将 Unicode 字符转为 Glyphs glyph name。"""
    cp = ord(ch)
    if cp <= 0xFFFF:
        return "uni%04X" % cp
    else:
        return "u%05X" % cp


# ============================================================
# UI 对话框
# ============================================================

class IDSSummonerDialog:
    def __init__(self, font, current_char, char_to_ids, char_to_leaves, char_to_positioned):
        self.font = font
        self.current_char = current_char
        self.char_to_ids = char_to_ids
        self.char_to_leaves = char_to_leaves
        self.char_to_positioned = char_to_positioned
        self.existing_chars = get_existing_unicode_chars(font)

        try:
            import vanilla
        except ImportError:
            print("❌ 错误: 找不到 vanilla 模块。")
            return

        ids_desc = char_to_ids.get(current_char, "（无 IDS 数据）")
        char_info = "%s (U+%04X)  IDS: %s" % (current_char, ord(current_char), ids_desc)

        self.w = vanilla.Window((420, 220), "召唤同族字")
        self.w.charInfo = vanilla.TextBox((15, 15, -15, 22), "当前字符: %s" % char_info, sizeStyle="small")

        self.w.strictCheck = vanilla.CheckBox(
            (15, 48, -15, 20), "严格模式（部件须在相同结构位置）",
            value=False
        )
        self.w.currentTabCheck = vanilla.CheckBox(
            (15, 75, -15, 20), "在当前标签页打开",
            value=True
        )

        self.w.summonButton = vanilla.Button(
            (15, 115, -15, 30), "召唤同族字",
            callback=self.summonCallback
        )

        self.w.statusText = vanilla.TextBox(
            (15, 160, -15, 44), "",
            sizeStyle="small"
        )

        self.w.open()

    def summonCallback(self, sender):
        strict = self.w.strictCheck.get()
        use_current_tab = self.w.currentTabCheck.get()

        if strict:
            related = find_related_strict(
                self.current_char, self.char_to_positioned, self.existing_chars
            )
            mode_name = "严格"
        else:
            related = find_related_loose(
                self.current_char, self.char_to_leaves, self.existing_chars
            )
            mode_name = "宽松"

        if not related:
            self.w.statusText.set("⚠️ 未找到同族字（%s模式）" % mode_name)
            return

        # 构建 glyph name 字符串
        glyph_names = []
        for ch in related:
            gn = char_to_glyph_name(ch)
            # 确认字体中确实存在此 glyph
            if self.font.glyphs[gn] is not None or self.font.glyphs[ch] is not None:
                glyph_names.append(gn)

        if not glyph_names:
            self.w.statusText.set("⚠️ 同族字均不在字体中（%s模式）" % mode_name)
            return

        # 打开同族字
        if use_current_tab:
            tab = self.font.currentTab
            if tab is not None:
                # 收集当前标签页中已有的 glyph name，用于去重
                already_in_tab = set()
                try:
                    for layer in tab.layers:
                        g = layer.parent
                        if g and g.name:
                            already_in_tab.add(g.name)
                except Exception:
                    pass

                # 过滤掉已存在的
                new_names = [gn for gn in glyph_names if gn not in already_in_tab]

                if not new_names:
                    self.w.statusText.set(
                        "ℹ️ %d 个同族字已全部在标签页中（%s模式）" % (len(glyph_names), mode_name)
                    )
                    return

                tab_string = "/" + "/".join(new_names)
                current_text = tab.text or ""
                tab.text = current_text + tab_string

                skipped = len(glyph_names) - len(new_names)
                msg = "✅ 已召唤 %d 个同族字（%s模式）" % (len(new_names), mode_name)
                if skipped > 0:
                    msg += "，跳过 %d 个已有字" % skipped
                self.w.statusText.set(msg)
            else:
                tab_string = "/" + "/".join(glyph_names)
                self.font.newTab(tab_string)
                self.w.statusText.set(
                    "✅ 已召唤 %d 个同族字（%s模式）" % (len(glyph_names), mode_name)
                )
        else:
            # 新标签页
            tab_string = "/" + "/".join(glyph_names)
            self.font.newTab(tab_string)
            self.w.statusText.set(
                "✅ 已召唤 %d 个同族字（%s模式）" % (len(glyph_names), mode_name)
            )


# ============================================================
# 主入口
# ============================================================

def main():
    font = Glyphs.font
    if font is None:
        try:
            from vanilla import dialogs
            dialogs.message("错误", "没有打开的字体文件。")
        except:
            print("❌ 错误: 没有打开的字体文件。")
        return

    # 获取当前编辑的字符
    current_char = get_current_char(font)
    if current_char is None:
        try:
            from vanilla import dialogs
            dialogs.message("错误", "请先在编辑界面中打开一个汉字字符。")
        except:
            print("❌ 错误: 请先在编辑界面中打开一个汉字字符。")
        return

    # 检查是否是 CJK 汉字
    cp = ord(current_char)
    is_cjk = (
        0x4E00 <= cp <= 0x9FFF or
        0x3400 <= cp <= 0x4DBF or
        0x20000 <= cp <= 0x2A6DF or
        0x2A700 <= cp <= 0x2B73F or
        0x2B740 <= cp <= 0x2B81F or
        0x2B820 <= cp <= 0x2CEAF or
        0x2CEB0 <= cp <= 0x2EBEF or
        0x30000 <= cp <= 0x3134F or
        0x31350 <= cp <= 0x323AF or
        0xF900 <= cp <= 0xFAFF or
        0x2F800 <= cp <= 0x2FA1F
    )
    if not is_cjk:
        try:
            from vanilla import dialogs
            dialogs.message("提示", "当前字符 %s (U+%04X) 不是 CJK 汉字。" % (current_char, cp))
        except:
            print("⚠️ 当前字符 %s (U+%04X) 不是 CJK 汉字。" % (current_char, cp))
        return

    # 加载 IDS 数据
    Glyphs.clearLog()
    Glyphs.showMacroWindow()
    print("🔍 召唤同族字")
    print("   当前字符: %s (U+%04X)" % (current_char, cp))
    print("   加载 IDS 数据库...")

    char_to_ids, char_to_leaves, char_to_positioned = load_ids_database()

    if not char_to_ids:
        print("❌ 无法加载 IDS 数据库。请确保 IDS_Composer.py 在同一目录下。")
        return

    print("   IDS 数据库: %d 个字符" % len(char_to_ids))

    ids_desc = char_to_ids.get(current_char, None)
    if ids_desc:
        print("   IDS 描述: %s" % ids_desc)
    else:
        print("   ⚠️ 该字符在 IDS 数据库中无拆解数据")

    # 打开 UI
    IDSSummonerDialog(font, current_char, char_to_ids, char_to_leaves, char_to_positioned)


main()
