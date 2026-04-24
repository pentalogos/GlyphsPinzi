import os
import zlib
import base64
import glob
import re

def pack_file(path):
    """读取文件并将其进行 zlib 压缩和 base64 编码"""
    with open(path, 'rb') as f:
        data = f.read()
    compressed = zlib.compress(data)
    return base64.b64encode(compressed).decode('ascii')

def main():
    print("🚀 开始构建内嵌数据集...")
    
    # 查找 ids 文件
    ids_files = glob.glob("ids*.txt")
    if not ids_files:
        print("❌ 错误：当前目录下未找到 ids*.txt 文件！")
        return
    
    # 如果有多个，取修改时间最新的
    ids_files.sort(key=os.path.getmtime, reverse=True)
    ids_path = ids_files[0]
    print(f"📖 发现 IDS 数据库：{ids_path}")
    
    # 查找字表目录
    charset_dir = "字表"
    charsets = {}
    if os.path.isdir(charset_dir):
        for fname in sorted(os.listdir(charset_dir)):
            fpath = os.path.join(charset_dir, fname)
            if os.path.isfile(fpath) and fname.endswith('.txt'):
                name = fname[:-4]
                charsets[name] = fpath
    
    print(f"📖 发现地区字表：{', '.join(charsets.keys()) if charsets else '无'}")
    
    # 构建数据字典字符串
    payload = "EMBEDDED_DATA = {\n"
    print(f"📦 正在压缩并打包 {ids_path} ...")
    payload += f'    "ids": "{pack_file(ids_path)}",\n'
    
    for name, path in charsets.items():
        print(f"📦 正在压缩并打包字表 {name} ...")
        payload += f'    "{name}": "{pack_file(path)}",\n'
    
    payload += "}\n"
    
    # 替换 IDS_Composer.py 中的数据
    script_path = "IDS_Composer.py"
    if not os.path.isfile(script_path):
        print(f"❌ 错误：未找到目标脚本 {script_path}！")
        return
        
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到 EMBEDDED_DATA 的定义并替换它
    # 使用正则匹配最后的 EMBEDDED_DATA = { ... }
    new_content = re.sub(
        r'^EMBEDDED_DATA\s*=\s*\{.*?\n\}',
        payload.strip(),
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # 如果替换后的内容与原内容相同，可能是没找到，也可能是数据没变
    if new_content == content and not re.search(r'^EMBEDDED_DATA\s*=\s*\{.*?\n\}', content, flags=re.MULTILINE | re.DOTALL):
        # 确实没找到
        if "EMBEDDED_DATA" not in content:
            new_content = content + "\n\n" + payload
        else:
            print("⚠️ 警告：找不到正则匹配的 EMBEDDED_DATA，但存在同名变量，请手动检查代码结构。")
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print(f"✅ 成功！数据已内嵌更新到 {script_path}，您现在可以使用最新数据运行拼字脚本了。")

if __name__ == "__main__":
    main()
