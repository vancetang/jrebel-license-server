#!/usr/bin/env python3
"""
JRebel & JetBrains License Server
支持 Web 界面生成激活 URL

参考: https://github.com/Ahaochan/JrebelLicenseServerforJava
"""

import logging
import os

from flask import Flask
from flask_cors import CORS

from config import SECRET_KEY, init_service_registry
from routes import web_bp, jrebel_bp, jetbrains_bp, admin_bp
from services.scheduler import start_scheduler

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 服务注册器实例
_service_registry = None


def create_app():
    """创建 Flask 应用"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = SECRET_KEY

    # 启用 CORS（允许前端 Cloudflare Pages 跨域访问）
    CORS(app, origins=[
        'https://idea.156354.xyz',
        'http://localhost:*',
        'http://127.0.0.1:*',
    ], supports_credentials=True)

    # 注册蓝图
    app.register_blueprint(web_bp)
    app.register_blueprint(jrebel_bp)
    app.register_blueprint(jetbrains_bp)
    app.register_blueprint(admin_bp)

    return app


def start_service_registry():
    """启动服务注册和心跳"""
    global _service_registry

    try:
        _service_registry = init_service_registry()
        if _service_registry:
            _service_registry.start()
            logger.info("服务注册和心跳已启动")
        else:
            logger.info("服务注册未启用（未配置环境变量）")
    except Exception as e:
        logger.error(f"启动服务注册失败: {e}")


# 创建应用实例
app = create_app()

# 启动服务注册（在 gunicorn 中会在 worker 启动时执行）
start_service_registry()

# 启动定时任务调度器
start_scheduler()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 58080))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    print("=" * 70)
    print("🚀 JRebel & JetBrains License Server")
    print("=" * 70)
    print(f"Web 界面: http://localhost:{port}")
    print(f"JRebel 激活: http://localhost:{port}/{{GUID}}")
    print(f"JetBrains 激活: http://localhost:{port}/")
    print("=" * 70)
    
    app.run(host='0.0.0.0', port=port, debug=debug)