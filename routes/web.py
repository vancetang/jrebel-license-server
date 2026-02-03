#!/usr/bin/env python3
"""
Web 界面路由
"""

import uuid
from datetime import datetime

from flask import Blueprint, request, render_template, jsonify, Response

from services import jrebel_signer, jetbrains_signer

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """首页 - Web 界面"""
    host = request.host
    scheme = request.scheme
    base_url = f"{scheme}://{host}"

    # 生成示例 GUID
    example_guid = str(uuid.uuid4())

    return render_template('index.html',
                           base_url=base_url,
                           example_guid=example_guid)


@web_bp.route('/generate', methods=['POST'])
def generate_url():
    """生成激活 URL"""
    data = request.get_json() or request.form

    product = data.get('product', 'jrebel')
    custom_guid = data.get('guid', '').strip()

    # 生成或使用自定义 GUID
    guid = custom_guid if custom_guid else str(uuid.uuid4())

    host = request.host
    scheme = request.scheme
    base_url = f"{scheme}://{host}"

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
        'version': '1.0.0',
        'jrebel_signer': jrebel_signer.private_key is not None,
        'jetbrains_signer': jetbrains_signer.private_key is not None
    })


@web_bp.route('/sitemap.xml')
def sitemap():
    """生成 sitemap.xml 供搜索引擎爬取"""
    host = request.host
    # 优先使用 X-Forwarded-Proto，适配反向代理
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    # 如果是生产环境域名，强制使用 https
    if 'idea.156354.xyz' in host:
        scheme = 'https'
    base_url = f"{scheme}://{host}"

    # 获取当前日期作为 lastmod
    today = datetime.now().strftime('%Y-%m-%d')

    # 定义网站的主要页面
    pages = [
        {'loc': base_url + '/', 'priority': '1.0', 'changefreq': 'weekly'},
    ]

    # 生成 XML
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

    return Response(xml_content, mimetype='application/xml')


@web_bp.route('/robots.txt')
def robots():
    """生成 robots.txt"""
    host = request.host
    # 优先使用 X-Forwarded-Proto，适配反向代理
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    # 如果是生产环境域名，强制使用 https
    if 'idea.156354.xyz' in host:
        scheme = 'https'
    base_url = f"{scheme}://{host}"

    content = f"""User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin

Sitemap: {base_url}/sitemap.xml
"""
    return Response(content, mimetype='text/plain')


@web_bp.route('/<path:guid>', methods=['GET'])
def handle_guid_path(guid):
    """处理 GUID 路径访问 (用于 JRebel 激活页面)"""
    # 如果是静态文件请求或管理页面，跳过
    if guid.startswith('static/') or guid.startswith('api/') or guid == 'admin':
        return '', 404

    # 返回激活信息页面
    host = request.host
    scheme = request.scheme
    base_url = f"{scheme}://{host}"

    return render_template('activation.html',
                           guid=guid,
                           base_url=base_url,
                           activation_url=f"{base_url}/{guid}")

