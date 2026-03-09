#!/usr/bin/env python3
"""
Web API 路由
前端已迁移到 Cloudflare Pages (idea.156354.xyz)
后端只保留 API 接口
"""

import uuid
from datetime import datetime

from flask import Blueprint, request, jsonify, Response, redirect

from services import jrebel_signer, jetbrains_signer

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """首页 - 重定向到前端"""
    return redirect('https://idea.156354.xyz', code=302)


@web_bp.route('/generate', methods=['POST'])
def generate_url():
    """生成激活 URL"""
    data = request.get_json() or request.form

    product = data.get('product', 'jrebel')
    custom_guid = data.get('guid', '').strip()

    # 生成或使用自定义 GUID
    guid = custom_guid if custom_guid else str(uuid.uuid4())

    # 使用后端 API 域名构建激活 URL
    base_url = 'https://api.idea.156354.xyz'

    if product == 'jrebel':
        activation_url = f"{base_url}/{guid}"
    else:
        activation_url = f"{base_url}/"

    return jsonify({
        'success': True,
        'product': product,
        'guid': guid,
        'activation_url': activation_url,
        'email': '任意邮箱'
    })


@web_bp.route('/api/status')
def api_status():
    """API 状态检查"""
    return jsonify({
        'status': 'running',
        'version': '2.0.0',
        'jrebel_signer': jrebel_signer.private_key is not None,
        'jetbrains_signer': jetbrains_signer.private_key is not None
    })


def _generate_sitemap_content():
    """生成 sitemap XML 内容"""
    base_url = 'https://idea.156354.xyz'
    today = datetime.now().strftime('%Y-%m-%d')

    pages = [
        {'loc': base_url + '/', 'priority': '1.0', 'changefreq': 'weekly'},
    ]

    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for page in pages:
        xml_content += '  <url>\n'
        xml_content += f'    <loc>{page["loc"]}</loc>\n'
        xml_content += f'    <lastmod>{today}</lastmod>\n'
        xml_content += f'    <changefreq>{page["changefreq"]}</changefreq>\n'
        xml_content += f'    <priority>{page["priority"]}</priority>\n'
        xml_content += '  </url>\n'

    xml_content += '</urlset>'
    return xml_content


def _create_sitemap_response():
    """创建符合 Google 规范的 sitemap 响应"""
    content = _generate_sitemap_content()
    response = Response(content, mimetype='application/xml')
    response.headers['Content-Type'] = 'application/xml; charset=utf-8'
    response.headers['X-Robots-Tag'] = 'noindex'
    response.headers['Cache-Control'] = 'public, max-age=3600'
    response.headers['Vary'] = 'Accept-Encoding'
    return response


@web_bp.route('/sitemap.xml')
def sitemap():
    """生成 sitemap.xml"""
    return _create_sitemap_response()


@web_bp.route('/sitemap_index.xml')
def sitemap_index():
    """备用 sitemap 路径"""
    return _create_sitemap_response()


@web_bp.route('/site-map.xml')
def sitemap_alt():
    """另一个备用 sitemap 路径"""
    return _create_sitemap_response()


@web_bp.route('/sitemaps.xml')
def sitemaps():
    """全新路径"""
    return _create_sitemap_response()


@web_bp.route('/robots.txt')
def robots():
    """生成 robots.txt"""
    base_url = 'https://idea.156354.xyz'

    content = f"""User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin

Sitemap: {base_url}/sitemap.xml
Sitemap: {base_url}/sitemap_index.xml
"""
    return Response(content, mimetype='text/plain')


@web_bp.route('/<path:guid>', methods=['GET'])
def handle_guid_path(guid):
    """处理 GUID 路径访问 (用于 JRebel 激活)
    保留此路由因为 JRebel 客户端会直接请求 /{GUID} 路径进行激活验证
    """
    # 如果是静态文件请求或管理页面，跳过
    if guid.startswith('static/') or guid.startswith('api/') or guid == 'admin':
        return '', 404

    # 重定向到前端激活页面
    return redirect(f'https://idea.156354.xyz/activation.html?guid={guid}&base_url=https://api.idea.156354.xyz', code=302)
