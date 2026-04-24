# Glyphs IDS Composer

专为 Glyphs.app 编写的汉字自动拼字脚本。基于 Ideographic Description Sequences (IDS) 规则，自动检索当前字体中已有部件，并将其组合生成新的汉字字符型。

## 特性

- **自动生成**：列出字体已有字符，根据 IDS 拆解规则，自动生成能拼装出的新字。
- **字表范围控制**：支持根据指定的字表（如 GB2312、Big5、通规等）筛选生成的字符，防止产生过多的无用生僻字。
- **动态宽度匹配**：自动提取当前字体母版的 UPM (Units Per Em) 作为预设的全角字符宽度，无需手动设定。

## 安装与运行

1. 下载项目中的 `IDS_Composer.py`。
2. 打开 Glyphs.app，进入顶部菜单栏的 `脚本` -> `打开脚本文件夹`。
3. 将 `IDS_Composer.py` 放入该目录中。
4. 重新打开 Glyphs，点击“脚本”->“IDS 汉字拼字”。

## 更新 IDS 数据库或字表

脚本内置了运行所需的数据集。如果需要更新 `ids.txt` 或新增自定义范围字表：

1. 确保您的环境中有 Python 3。
2. 将新的 `ids.txt` 文件放入本仓库根目录。
3. 若需新增字表，请将**每行只有一个标准 Glyphs 字符名称（如 `uni554A` 或 `u2B6AD`）**的纯文本文件放入 `字表/` 目录中。
4. 运行更新脚本：
   ```bash
   python3 build_embedded_data.py
   ```
5. 该脚本会自动对数据进行 `zlib` 和 `base64` 压缩处理，并将新的数据体无缝注入到 `IDS_Composer.py` 的底部。注入成功后，替换旧的脚本即可使用最新数据。

## 数据来源

- IDS 数据来自：[hfhchan/ids](https://github.com/hfhchan/ids)

## 许可证

MIT License
