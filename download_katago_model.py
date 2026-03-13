#!/usr/bin/env python3
"""
KataGo 模型下载脚本
尝试多种方式下载模型文件
"""

import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

# 模型信息
MODEL_NAME = "kata1-b18c384nbt-s10793838592-d4609278972"
MODEL_FILE = f"{MODEL_NAME}.bin.gz"

# 保存路径
WEIGHTS_DIR = Path("/Users/qiao/Desktop/qiao/program/GoMaster/server/katago/weights")
SAVE_PATH = WEIGHTS_DIR / MODEL_FILE

# 尝试的下载链接
URLS = [
    f"https://media.katagotraining.org/uploaded/networks/models/kata1/{MODEL_FILE}",
    f"https://katagotraining.org/networks/download/{MODEL_FILE}",
    f"https://github.com/lightvector/KataGo/releases/download/v1.15.0/{MODEL_FILE}",
]

def download_with_progress(url, save_path):
    """带进度条的下载"""
    try:
        print(f"尝试下载: {url}")
        
        # 创建请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/gzip,application/octet-stream,*/*',
            'Referer': 'https://katagotraining.org/',
        }
        
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=60) as response:
            # 获取文件大小
            total_size = int(response.headers.get('Content-Length', 0))
            
            if total_size < 1000000:  # 小于 1MB 可能是错误页面
                print(f"  ⚠️  文件太小 ({total_size} bytes)，可能是错误页面")
                return False
            
            print(f"  文件大小: {total_size / 1024 / 1024:.1f} MB")
            print(f"  开始下载...")
            
            # 下载文件
            block_size = 8192
            downloaded = 0
            
            with open(save_path, 'wb') as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # 显示进度
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\r  进度: {percent:.1f}% ({downloaded / 1024 / 1024:.1f} MB / {total_size / 1024 / 1024:.1f} MB)", end='', flush=True)
            
            print()  # 换行
            print(f"  ✅ 下载完成: {save_path}")
            return True
            
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP 错误: {e.code} - {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"  ❌ URL 错误: {e.reason}")
        return False
    except Exception as e:
        print(f"  ❌ 错误: {e}")
        return False

def main():
    print("=" * 60)
    print("KataGo 模型下载工具")
    print("=" * 60)
    print(f"模型名称: {MODEL_NAME}")
    print(f"保存路径: {SAVE_PATH}")
    print()
    
    # 确保目录存在
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 检查文件是否已存在
    if SAVE_PATH.exists():
        file_size = SAVE_PATH.stat().st_size
        print(f"⚠️  文件已存在 ({file_size / 1024 / 1024:.1f} MB)")
        response = input("是否重新下载? (y/N): ")
        if response.lower() != 'y':
            print("取消下载")
            return
        SAVE_PATH.unlink()
    
    # 尝试所有 URL
    for i, url in enumerate(URLS, 1):
        print(f"\n[{i}/{len(URLS)}] 尝试下载源...")
        if download_with_progress(url, SAVE_PATH):
            # 验证文件
            file_size = SAVE_PATH.stat().st_size
            print(f"\n✅ 成功下载模型!")
            print(f"   文件: {SAVE_PATH}")
            print(f"   大小: {file_size / 1024 / 1024:.1f} MB")
            
            # 检查文件类型
            with open(SAVE_PATH, 'rb') as f:
                magic = f.read(2)
                if magic == b'\x1f\x8b':  # gzip magic number
                    print(f"   格式: 有效的 gzip 文件")
                else:
                    print(f"   ⚠️  警告: 文件可能不是有效的 gzip 格式")
            
            print("\n你可以使用以下命令切换到新模型:")
            print(f"curl -X POST http://localhost:8001/switch_model \\")
            print(f"  -H 'Content-Type: application/json' \\")
            print(f"  -d '{{\"model_name\": \"{MODEL_FILE}\"}}'")
            return
        
        # 删除失败的文件
        if SAVE_PATH.exists():
            SAVE_PATH.unlink()
    
    print("\n" + "=" * 60)
    print("❌ 所有下载源都失败了")
    print("=" * 60)
    print("\n请尝试手动下载:")
    print("1. 访问 https://katagotraining.org/networks/")
    print(f"2. 搜索 {MODEL_NAME}")
    print("3. 点击下载按钮")
    print(f"4. 将文件移动到: {WEIGHTS_DIR}")
    print("\n或者尝试使用浏览器直接下载:")
    print(f"   {URLS[0]}")

if __name__ == "__main__":
    main()
