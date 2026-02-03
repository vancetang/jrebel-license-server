#!/usr/bin/env python3
"""
Google Search Console API - Sitemap 提交脚本

配置说明:
在配置库中添加 key: google.service_account
值为 JSON 格式的服务账号凭证 (从 Google Cloud Console 下载的 JSON 文件内容)

使用方法:
# 提交 sitemap (使用默认配置)
python scripts/submit_sitemap.py

# 指定网站和 sitemap
python scripts/submit_sitemap.py --site "https://idea.156354.xyz/" --sitemap "https://idea.156354.xyz/sitemap.xml"

# 列出所有网站和 sitemap
python scripts/submit_sitemap.py --list

# 删除 sitemap
python scripts/submit_sitemap.py --delete "https://idea.156354.xyz/sitemap.xml"

# 使用本地凭证文件（不走配置库）
python scripts/submit_sitemap.py --credentials /path/to/credentials.json

参考文档:
- https://developers.google.com/webmaster-tools/v1/sitemaps/submit
"""

import argparse
import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("请先安装依赖: pip install google-auth google-api-python-client")
    sys.exit(1)


# ========== 配置 ==========
# 通用配置 key (可在配置库中使用)
GOOGLE_SERVICE_ACCOUNT_CONFIG_KEY = "google.service_account"

# 默认配置
DEFAULT_SITE_URL = "https://idea.156354.xyz/"
DEFAULT_SITEMAP_URLS = [
    "https://idea.156354.xyz/sitemap.xml",
]

# API 授权范围
SCOPES = ['https://www.googleapis.com/auth/webmasters']


def get_credentials_from_config():
    """从配置库获取 Google 服务账号凭证

    配置 key: google.service_account
    值: JSON 格式的服务账号凭证

    示例配置值:
    {
        "type": "service_account",
        "project_id": "your-project-id",
        "private_key_id": "xxx",
        "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",
        "client_email": "xxx@project-id.iam.gserviceaccount.com",
        "client_id": "123456789",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        ...
    }
    """
    try:
        from config import kenger_client

        if not kenger_client:
            print("警告: KengerClient 未初始化")
            return None

        config_value = kenger_client.config.get(GOOGLE_SERVICE_ACCOUNT_CONFIG_KEY)
        if not config_value:
            print(f"警告: 配置库中未找到 key: {GOOGLE_SERVICE_ACCOUNT_CONFIG_KEY}")
            return None

        # 解析 JSON (可能需要解析两次，因为配置值可能是双重转义的字符串)
        if isinstance(config_value, str):
            credentials_info = json.loads(config_value)
            # 如果解析后仍然是字符串，再解析一次
            if isinstance(credentials_info, str):
                credentials_info = json.loads(credentials_info)
        else:
            credentials_info = config_value

        # 创建凭证
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=SCOPES
        )

        print(f"✓ 从配置库获取凭证成功 (key: {GOOGLE_SERVICE_ACCOUNT_CONFIG_KEY})")
        print(f"  服务账号: {credentials_info.get('client_email', 'N/A')}")
        return credentials

    except ImportError:
        print("警告: 无法导入 config 模块")
        return None
    except json.JSONDecodeError as e:
        print(f"错误: 配置值不是有效的 JSON: {e}")
        return None
    except Exception as e:
        print(f"错误: 从配置库获取凭证失败: {e}")
        return None


def get_credentials_from_file(credentials_file: str):
    """从本地文件获取凭证"""
    if not Path(credentials_file).exists():
        print(f"错误: 找不到凭证文件: {credentials_file}")
        return None

    credentials = service_account.Credentials.from_service_account_file(
        credentials_file,
        scopes=SCOPES
    )
    print(f"✓ 从文件获取凭证成功: {credentials_file}")
    return credentials


def get_service(credentials):
    """创建 Search Console API 服务实例"""
    return build('searchconsole', 'v1', credentials=credentials)


def list_sites(service):
    """列出所有已验证的网站"""
    try:
        sites = service.sites().list().execute()
        print("\n=== 已验证的网站 ===")
        if 'siteEntry' in sites:
            for site in sites['siteEntry']:
                print(f"  - {site['siteUrl']} ({site['permissionLevel']})")
        else:
            print("  没有找到已验证的网站")
        return sites.get('siteEntry', [])
    except HttpError as e:
        print(f"获取网站列表失败: {e}")
        return []


def list_sitemaps(service, site_url: str):
    """列出网站的所有 sitemap"""
    try:
        sitemaps = service.sitemaps().list(siteUrl=site_url).execute()
        print(f"\n=== {site_url} 的 Sitemap ===")
        if 'sitemap' in sitemaps:
            for sitemap in sitemaps['sitemap']:
                status = "✓" if sitemap.get('isPending') is False else "⏳"
                errors = sitemap.get('errors', 0)
                warnings = sitemap.get('warnings', 0)
                print(f"  {status} {sitemap['path']}")
                print(f"      提交时间: {sitemap.get('lastSubmitted', 'N/A')}")
                print(f"      下载时间: {sitemap.get('lastDownloaded', 'N/A')}")
                print(f"      错误: {errors}, 警告: {warnings}")
        else:
            print("  没有找到 sitemap")
        return sitemaps.get('sitemap', [])
    except HttpError as e:
        print(f"获取 sitemap 列表失败: {e}")
        return []


def submit_sitemap(service, site_url: str, sitemap_url: str):
    """提交 sitemap 到 Google Search Console"""
    try:
        print(f"\n提交 sitemap: {sitemap_url}")
        print(f"  目标网站: {site_url}")

        service.sitemaps().submit(
            siteUrl=site_url,
            feedpath=sitemap_url
        ).execute()

        print(f"  ✓ 提交成功!")
        return True

    except HttpError as e:
        error_content = json.loads(e.content.decode('utf-8'))
        error_message = error_content.get('error', {}).get('message', str(e))
        print(f"  ✗ 提交失败: {error_message}")

        if e.resp.status == 403:
            print("\n提示: 权限不足，请确保服务账号已被添加为 GSC 用户")
            print("步骤:")
            print("  1. 打开 https://search.google.com/search-console")
            print("  2. 选择你的网站")
            print("  3. 设置 > 用户和权限 > 添加用户")
            print("  4. 输入服务账号邮箱")
            print("  5. 权限选择 '完全'")

        return False


def delete_sitemap(service, site_url: str, sitemap_url: str):
    """删除 sitemap"""
    try:
        print(f"\n删除 sitemap: {sitemap_url}")
        service.sitemaps().delete(
            siteUrl=site_url,
            feedpath=sitemap_url
        ).execute()
        print(f"  ✓ 删除成功!")
        return True
    except HttpError as e:
        print(f"  ✗ 删除失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Google Search Console Sitemap 提交工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f'''
配置库 key: {GOOGLE_SERVICE_ACCOUNT_CONFIG_KEY}
配置值: Google 服务账号 JSON 凭证内容

示例:
  # 使用配置库凭证提交 sitemap
  python {Path(__file__).name}

  # 使用本地凭证文件
  python {Path(__file__).name} --credentials /path/to/credentials.json

  # 指定网站和 sitemap
  python {Path(__file__).name} --site "https://example.com/" --sitemap "https://example.com/sitemap.xml"
'''
    )
    parser.add_argument('--credentials', '-c',
                        help='服务账号 JSON 密钥文件路径 (不指定则从配置库获取)')
    parser.add_argument('--site', '-s', default=DEFAULT_SITE_URL,
                        help=f'网站 URL (默认: {DEFAULT_SITE_URL})')
    parser.add_argument('--sitemap', '-m', action='append',
                        help='要提交的 sitemap URL (可多次指定)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='列出所有网站和 sitemap')
    parser.add_argument('--delete', '-d',
                        help='删除指定的 sitemap URL')

    args = parser.parse_args()

    # 获取凭证
    credentials = None

    if args.credentials:
        # 使用本地文件
        credentials = get_credentials_from_file(args.credentials)
    else:
        # 从配置库获取
        credentials = get_credentials_from_config()

        # 如果配置库获取失败，尝试使用默认文件路径
        if not credentials:
            default_credentials_file = PROJECT_ROOT / 'scripts' / 'google-credentials.json'
            if default_credentials_file.exists():
                print(f"尝试使用默认凭证文件: {default_credentials_file}")
                credentials = get_credentials_from_file(str(default_credentials_file))

    if not credentials:
        print("\n错误: 无法获取凭证")
        print(f"\n请在配置库中配置 key: {GOOGLE_SERVICE_ACCOUNT_CONFIG_KEY}")
        print("或使用 --credentials 参数指定本地凭证文件")
        sys.exit(1)

    # 创建服务
    service = get_service(credentials)

    # 列出网站
    sites = list_sites(service)

    if args.list:
        # 列出所有网站的 sitemap
        for site in sites:
            list_sitemaps(service, site['siteUrl'])
        return

    if args.delete:
        # 删除 sitemap
        delete_sitemap(service, args.site, args.delete)
        return

    # 提交 sitemap
    sitemap_urls = args.sitemap if args.sitemap else DEFAULT_SITEMAP_URLS

    for sitemap_url in sitemap_urls:
        submit_sitemap(service, args.site, sitemap_url)

    # 提交后列出当前状态
    print("\n" + "=" * 50)
    list_sitemaps(service, args.site)


if __name__ == '__main__':
    main()

