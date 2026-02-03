#!/usr/bin/env python3
"""
定时任务调度器
负责管理和执行后台定时任务
"""

import logging
import os
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# 全局调度器实例
_scheduler_thread: Optional[threading.Thread] = None
_scheduler_running = False


def submit_sitemap_task():
    """提交 sitemap 到 Google Search Console"""
    try:
        from scripts.submit_sitemap import (
            get_credentials_from_config,
            get_credentials_from_file,
            get_service,
            list_sites,
            submit_sitemap,
            DEFAULT_SITE_URL,
            DEFAULT_SITEMAP_URLS,
        )

        logger.info("开始执行 sitemap 提交任务...")

        # 获取凭证
        credentials = get_credentials_from_config()
        if not credentials:
            logger.warning("无法从配置库获取 Google 凭证，跳过 sitemap 提交")
            return

        # 创建服务
        service = get_service(credentials)

        # 提交 sitemap
        for sitemap_url in DEFAULT_SITEMAP_URLS:
            try:
                submit_sitemap(service, DEFAULT_SITE_URL, sitemap_url)
            except Exception as e:
                logger.error(f"提交 sitemap 失败 ({sitemap_url}): {e}")

        logger.info("sitemap 提交任务完成")

    except ImportError as e:
        logger.warning(f"无法导入 sitemap 提交模块: {e}")
    except Exception as e:
        logger.error(f"sitemap 提交任务执行失败: {e}")


def _run_scheduler():
    """调度器主循环"""
    global _scheduler_running

    try:
        import schedule
    except ImportError:
        logger.warning("schedule 库未安装，定时任务功能不可用")
        return

    # 配置定时任务
    # 每天凌晨 3 点执行 sitemap 提交
    schedule.every().day.at("03:00").do(submit_sitemap_task)

    # 也可以配置启动后立即执行一次（可选）
    # submit_sitemap_task()

    logger.info("定时任务调度器已启动")
    logger.info("  - sitemap 提交: 每天 03:00")

    while _scheduler_running:
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error(f"调度器执行任务时出错: {e}")
        time.sleep(60)  # 每分钟检查一次


def start_scheduler():
    """启动定时任务调度器"""
    global _scheduler_thread, _scheduler_running

    # 检查是否启用定时任务
    enable_scheduler = os.environ.get('ENABLE_SCHEDULER', 'true').lower() == 'true'
    if not enable_scheduler:
        logger.info("定时任务调度器已禁用 (ENABLE_SCHEDULER=false)")
        return

    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        logger.warning("定时任务调度器已在运行")
        return

    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True)
    _scheduler_thread.start()
    logger.info("定时任务调度器线程已启动")


def stop_scheduler():
    """停止定时任务调度器"""
    global _scheduler_running

    _scheduler_running = False
    logger.info("定时任务调度器已停止")

