#!/bin/bash

# JRebel License Server 部署脚本 V3
# 基于服务自动注册实现零停机部署
#
# 发布流程：
# 1. 构建新镜像
# 2. 启动新版本容器（使用不同端口）
# 3. 等待新容器健康检查通过（容器启动后自动注册到注册中心）
# 4. 等待一段时间让流量自动切换
# 5. 停止并删除旧容器（旧容器停止时自动从注册中心注销）

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================
# 配置区域（根据实际情况修改）
# ============================================
PROJECT_NAME="jrebel-license-server"
NAMESPACE="jrebel"
HEALTH_CHECK_PATH="/api/status"
HEALTH_CHECK_TIMEOUT=60               # 健康检查超时（秒）
TRAFFIC_SWITCH_WAIT=30                # 流量切换等待时间（秒）

# 端口配置（交替使用）
PORT_A=58081
PORT_B=58082

# 容器内部端口
CONTAINER_PORT=58080

# 服务注册配置（容器启动后自动注册到注册中心）
REGISTRY_HOST="${KENGER_REGISTRY_HOST:-127.0.0.1}"  # 公网IP或域名
REGISTRY_NAMESPACE="${KENGER_REGISTRY_NAMESPACE:-jrebel}"
REGISTRY_WEIGHT="${KENGER_REGISTRY_WEIGHT:-100}"
REGISTRY_HEARTBEAT_INTERVAL="${KENGER_REGISTRY_HEARTBEAT_INTERVAL:-10}"

# 配置中心地址（容器内通过 Docker bridge gateway 访问宿主机）
CONFIG_SERVER_URL="${CONFIG_SERVER_URL:-http://172.17.0.1:5000}"
CONFIG_SERVER_TOKEN="${CONFIG_SERVER_TOKEN:-u2InTXnmFF0Um6Sd}"

# 前端部署配置
FRONTEND_DEPLOY="${FRONTEND_DEPLOY:-true}"            # true/false
FRONTEND_DIR="${FRONTEND_DIR:-frontend}"
CF_PAGES_PROJECT="${CF_PAGES_PROJECT:-jrebel-web}"
CF_ACCOUNT_ID="${CF_ACCOUNT_ID:-}"
CF_API_TOKEN="${CF_API_TOKEN:-}"
FRONTEND_DOMAIN="${FRONTEND_DOMAIN:-idea.156354.xyz}"
BACKEND_DOMAIN="${BACKEND_DOMAIN:-ideabackend.156354.xyz}"

# Tunnel 配置
TUNNEL_ID="${TUNNEL_ID:-e68531cc-f521-4f8e-bd53-cd1a697993d3}"
CLOUDFLARED_CONFIG="${CLOUDFLARED_CONFIG:-/etc/cloudflared/config.yml}"
CLOUDFLARED_SERVICE="${CLOUDFLARED_SERVICE:-cloudflared}"

# ============================================
# 以下为脚本逻辑，一般不需要修改
# ============================================

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%H:%M:%S') $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%H:%M:%S') $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $(date '+%H:%M:%S') $1"
}

# 获取当前运行的容器信息
get_current_container() {
    local container_a="${PROJECT_NAME}-a"
    local container_b="${PROJECT_NAME}-b"

    if docker ps --format '{{.Names}}' | grep -q "^${container_a}$"; then
        echo "a"
    elif docker ps --format '{{.Names}}' | grep -q "^${container_b}$"; then
        echo "b"
    else
        echo "none"
    fi
}

# 获取下一个容器配置
get_next_config() {
    local current=$1
    if [ "$current" = "a" ]; then
        echo "b ${PORT_B}"
    else
        echo "a ${PORT_A}"
    fi
}

# 健康检查
wait_for_healthy() {
    local host=$1
    local port=$2
    local timeout=$3
    local start_time=$(date +%s)

    log_info "等待服务健康检查通过: ${host}:${port}${HEALTH_CHECK_PATH}"

    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))

        if [ $elapsed -ge $timeout ]; then
            log_error "健康检查超时（${timeout}秒）"
            return 1
        fi

        if curl -sf "http://${host}:${port}${HEALTH_CHECK_PATH}" > /dev/null 2>&1; then
            echo ""
            log_info "健康检查通过！耗时 ${elapsed} 秒"
            return 0
        fi

        echo -n "."
        sleep 2
    done
}

# 构建新镜像
build_image() {
    log_step "构建新镜像: ${PROJECT_NAME}:latest"
    docker build -t ${PROJECT_NAME}:latest . --no-cache
    log_info "镜像构建完成"
}

# 启动新容器
start_new_container() {
    local suffix=$1
    local port=$2
    local container_name="${PROJECT_NAME}-${suffix}"

    log_step "启动新容器: ${container_name} (端口: ${port})"

    # 删除可能存在的同名容器
    docker rm -f ${container_name} 2>/dev/null || true

    docker run -d \
        --name ${container_name} \
        --restart unless-stopped \
        -p ${port}:${CONTAINER_PORT} \
        -e PORT=${CONTAINER_PORT} \
        -e SECRET_KEY="${SECRET_KEY:-your-secret-key}" \
        -e DEBUG=false \
        -e TZ=Asia/Shanghai \
        -e CONFIG_SERVER_URL="${CONFIG_SERVER_URL}" \
        -e CONFIG_SERVER_TOKEN="${CONFIG_SERVER_TOKEN}" \
        -e KENGER_REGISTRY_HOST="${REGISTRY_HOST}" \
        -e KENGER_REGISTRY_PORT="${port}" \
        -e KENGER_REGISTRY_NAMESPACE="${REGISTRY_NAMESPACE}" \
        -e KENGER_REGISTRY_WEIGHT="${REGISTRY_WEIGHT}" \
        -e KENGER_REGISTRY_HEALTH_PATH="${HEALTH_CHECK_PATH}" \
        -e KENGER_REGISTRY_HEARTBEAT_INTERVAL="${REGISTRY_HEARTBEAT_INTERVAL}" \
        ${PROJECT_NAME}:latest

    log_info "容器 ${container_name} 启动完成"
}

# 停止旧容器
stop_old_container() {
    local suffix=$1
    local container_name="${PROJECT_NAME}-${suffix}"

    log_step "停止旧容器: ${container_name}"

    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        docker stop ${container_name}
        docker rm ${container_name}
        log_info "旧容器 ${container_name} 已停止并删除（自动从注册中心注销）"
    else
        log_info "旧容器 ${container_name} 不存在，跳过"
    fi
}

# 查看容器状态
show_containers() {
    echo ""
    log_info "当前容器状态:"
    echo ""
    docker ps --filter "name=${PROJECT_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "无运行中的容器"
}

ensure_requirements() {
    if ! command -v curl &> /dev/null; then
        log_error "curl 未安装"
        exit 1
    fi

    if [ "${FRONTEND_DEPLOY}" = "true" ] && ! command -v npx &> /dev/null; then
        log_error "npx 未安装，请先安装 Node.js（前端部署需要）"
        exit 1
    fi
}

update_cloudflared_config() {
    log_step "更新 cloudflared 配置: ${CLOUDFLARED_CONFIG}"

    if [ ! -f "${CLOUDFLARED_CONFIG}"; then
        log_error "未找到 cloudflared 配置文件: ${CLOUDFLARED_CONFIG}"
        exit 1
    fi

    cp "${CLOUDFLARED_CONFIG}" "${CLOUDFLARED_CONFIG}.bak.$(date +%Y%m%d%H%M%S)"

    if grep -q "hostname: ${BACKEND_DOMAIN}" "${CLOUDFLARED_CONFIG}"; then
        log_info "cloudflared 配置已包含 ${BACKEND_DOMAIN}"
    else
        if grep -q "hostname: .*idea\.156354\.xyz" "${CLOUDFLARED_CONFIG}"; then
            sed -i "s/hostname: .*idea\.156354\.xyz/hostname: ${BACKEND_DOMAIN}/" "${CLOUDFLARED_CONFIG}"
            log_info "已将旧后端域名替换为 ${BACKEND_DOMAIN}"
        else
            log_warn "未在配置中找到可替换的旧域名，请手动确认 ${CLOUDFLARED_CONFIG}"
        fi
    fi

    if command -v cloudflared &> /dev/null; then
        cloudflared tunnel route dns ${TUNNEL_ID} ${BACKEND_DOMAIN} --overwrite-dns || true
    else
        log_warn "未安装 cloudflared 命令，跳过 tunnel dns route"
    fi

    if command -v systemctl &> /dev/null; then
        systemctl restart ${CLOUDFLARED_SERVICE}
        log_info "已重启 ${CLOUDFLARED_SERVICE}"
    else
        log_warn "未检测到 systemctl，请手动重启 ${CLOUDFLARED_SERVICE}"
    fi
}

deploy_frontend() {
    if [ "${FRONTEND_DEPLOY}" != "true" ]; then
        log_info "FRONTEND_DEPLOY=false，跳过前端部署"
        return 0
    fi

    log_step "部署前端到 Cloudflare Pages"

    if [ -z "${CF_API_TOKEN}" ] || [ -z "${CF_ACCOUNT_ID}" ]; then
        log_error "请先配置 CF_API_TOKEN 和 CF_ACCOUNT_ID"
        exit 1
    fi

    if [ ! -d "${FRONTEND_DIR}" ]; then
        log_error "前端目录不存在: ${FRONTEND_DIR}"
        exit 1
    fi

    CLOUDFLARE_API_TOKEN="${CF_API_TOKEN}" \
    CLOUDFLARE_ACCOUNT_ID="${CF_ACCOUNT_ID}" \
    npx wrangler pages project create "${CF_PAGES_PROJECT}" --production-branch main >/dev/null 2>&1 || true

    CLOUDFLARE_API_TOKEN="${CF_API_TOKEN}" \
    CLOUDFLARE_ACCOUNT_ID="${CF_ACCOUNT_ID}" \
    npx wrangler pages deploy "./${FRONTEND_DIR}" \
        --project-name="${CF_PAGES_PROJECT}" \
        --branch=main \
        --commit-dirty=true

    log_info "前端部署完成"
}

bind_frontend_domain() {
    if [ "${FRONTEND_DEPLOY}" != "true" ]; then
        return 0
    fi

    log_step "确保 Pages 域名绑定: ${FRONTEND_DOMAIN}"

    if [ -z "${CF_API_TOKEN}" ] || [ -z "${CF_ACCOUNT_ID}" ]; then
        log_error "请先配置 CF_API_TOKEN 和 CF_ACCOUNT_ID"
        exit 1
    fi

    curl -s -X POST "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/pages/projects/${CF_PAGES_PROJECT}/domains" \
      -H "Authorization: Bearer ${CF_API_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"${FRONTEND_DOMAIN}\"}" >/dev/null || true
}

verify_routes() {
    log_step "验证前后端可访问性"

    curl -sf "https://${FRONTEND_DOMAIN}/" >/dev/null
    log_info "前端可访问: https://${FRONTEND_DOMAIN}/"

    curl -sf "https://${BACKEND_DOMAIN}/api/status" >/dev/null
    log_info "后端可访问: https://${BACKEND_DOMAIN}/api/status"
}

backend_main() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║     JRebel License Server 部署脚本 V3                      ║${NC}"
    echo -e "${GREEN}║     Namespace: ${NAMESPACE}                                         ║${NC}"
    echo -e "${GREEN}║     自动注册模式                                           ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # 检查 Docker 是否可用
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装或不可用"
        exit 1
    fi

    # 获取当前运行状态
    local current=$(get_current_container)
    log_info "当前运行容器: ${current}"

    # 获取下一个配置
    local next_config=$(get_next_config "$current")
    local next_suffix=$(echo $next_config | cut -d' ' -f1)
    local next_port=$(echo $next_config | cut -d' ' -f2)

    log_info "新容器配置: suffix=${next_suffix}, port=${next_port}"
    log_info "注册中心: ${REGISTRY_HOST}:${next_port} -> ${REGISTRY_NAMESPACE}"
    echo ""

    ensure_requirements

    # 1. 更新 tunnel 与 cloudflared 配置
    update_cloudflared_config
    echo ""

    # 2. 构建新镜像
    build_image
    echo ""

    # 3. 启动新容器
    start_new_container "$next_suffix" "$next_port"
    echo ""

    # 4. 等待健康检查（容器启动后会自动注册到注册中心）
    if ! wait_for_healthy "127.0.0.1" "$next_port" "$HEALTH_CHECK_TIMEOUT"; then
        log_error "新容器健康检查失败，执行回滚..."
        docker rm -f "${PROJECT_NAME}-${next_suffix}" 2>/dev/null || true
        exit 1
    fi
    log_info "新容器已自动注册到注册中心"
    echo ""

    # 5. 等待流量切换（如果有旧容器）
    if [ "$current" != "none" ]; then
        log_step "等待 ${TRAFFIC_SWITCH_WAIT} 秒让流量自动切换..."
        sleep $TRAFFIC_SWITCH_WAIT
        echo ""

        # 6. 停止旧容器（停止时会自动从注册中心注销）
        stop_old_container "$current"
    fi

    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    后端部署完成！                          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"

    show_containers

    echo ""
    log_info "本地后端: http://localhost:${next_port}"
    log_info "后端地址: https://${BACKEND_DOMAIN}/api/status"
    echo ""
}

# 主函数 - 执行部署
main() {
    backend_main

    # 7. 部署前端
    deploy_frontend
    echo ""

    # 8. 绑定前端域名
    bind_frontend_domain
    echo ""

    # 9. 验证前后端
    verify_routes

    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    全量部署完成！                          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"

    echo ""
    log_info "前端地址: https://${FRONTEND_DOMAIN}/"
    log_info "后端地址: https://${BACKEND_DOMAIN}/api/status"
    echo ""
}

# 回滚到上一个版本
rollback() {
    echo ""
    log_step "执行回滚操作..."

    local current=$(get_current_container)

    if [ "$current" = "none" ]; then
        log_error "没有运行中的容器，无法回滚"
        exit 1
    fi

    local old_suffix
    local old_port
    local new_suffix
    local new_port

    if [ "$current" = "a" ]; then
        new_suffix="a"
        new_port=$PORT_A
        old_suffix="b"
        old_port=$PORT_B
    else
        new_suffix="b"
        new_port=$PORT_B
        old_suffix="a"
        old_port=$PORT_A
    fi

    # 检查旧容器是否存在
    local old_container="${PROJECT_NAME}-${old_suffix}"
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${old_container}$"; then
        log_error "旧容器 ${old_container} 不存在，无法回滚"
        exit 1
    fi

    # 启动旧容器（如果已停止，启动后会自动注册）
    if ! docker ps --format '{{.Names}}' | grep -q "^${old_container}$"; then
        log_info "启动旧容器 ${old_container}..."
        docker start ${old_container}

        # 等待健康检查
        if ! wait_for_healthy "127.0.0.1" "$old_port" "$HEALTH_CHECK_TIMEOUT"; then
            log_error "旧容器健康检查失败"
            exit 1
        fi
        log_info "旧容器已自动注册到注册中心"
    fi

    # 等待流量切换
    log_step "等待 ${TRAFFIC_SWITCH_WAIT} 秒让流量自动切换..."
    sleep $TRAFFIC_SWITCH_WAIT

    # 停止新容器（停止时会自动注销）
    stop_old_container "$new_suffix"

    log_info "回滚完成！"
    show_containers
}

# 快速启动（不构建镜像）
quick_start() {
    local port=${1:-$PORT_A}
    local suffix="a"

    if [ "$port" = "$PORT_B" ]; then
        suffix="b"
    fi

    log_info "快速启动容器: 端口 ${port}"
    start_new_container "$suffix" "$port"

    if wait_for_healthy "127.0.0.1" "$port" "$HEALTH_CHECK_TIMEOUT"; then
        log_info "容器已启动并自动注册到注册中心"
    else
        log_error "容器启动失败"
        exit 1
    fi

    show_containers
}

# 停止所有容器
stop_all() {
    log_step "停止所有 ${PROJECT_NAME} 容器..."

    docker ps --filter "name=${PROJECT_NAME}" --format '{{.Names}}' | while read container; do
        log_info "停止容器: ${container}"
        docker stop ${container} 2>/dev/null || true
        docker rm ${container} 2>/dev/null || true
    done

    log_info "所有容器已停止（自动从注册中心注销）"
}

# 查看日志
show_logs() {
    local container=${1:-$(docker ps --filter "name=${PROJECT_NAME}" --format '{{.Names}}' | head -1)}

    if [ -z "$container" ]; then
        log_error "没有运行中的容器"
        exit 1
    fi

    log_info "查看容器日志: ${container}"
    docker logs -f --tail 100 ${container}
}

# 帮助信息
show_help() {
    echo ""
    echo "用法: $0 [命令] [参数]"
    echo ""
    echo "命令:"
    echo "  deploy          一键部署（后端+前端+tunnel）（默认）"
    echo "  backend         仅部署后端（镜像+容器切换）"
    echo "  frontend        仅部署前端（Pages）"
    echo "  rollback        回滚到上一个版本"
    echo "  start [port]    快速启动（不构建镜像）"
    echo "  stop            停止所有容器"
    echo "  status          查看容器状态"
    echo "  logs [name]     查看容器日志"
    echo "  help            显示帮助信息"
    echo ""
    echo "配置:"
    echo "  PROJECT_NAME      = ${PROJECT_NAME}"
    echo "  NAMESPACE         = ${NAMESPACE}"
    echo "  PORT_A            = ${PORT_A}"
    echo "  PORT_B            = ${PORT_B}"
    echo "  REGISTRY_HOST     = ${REGISTRY_HOST}"
    echo "  FRONTEND_DEPLOY   = ${FRONTEND_DEPLOY}"
    echo "  CF_PAGES_PROJECT  = ${CF_PAGES_PROJECT}"
    echo "  FRONTEND_DOMAIN   = ${FRONTEND_DOMAIN}"
    echo "  BACKEND_DOMAIN    = ${BACKEND_DOMAIN}"
    echo ""
    echo "环境变量:"
    echo "  SECRET_KEY                      Flask 密钥"
    echo "  KENGER_REGISTRY_HOST            注册中心主机地址"
    echo "  KENGER_REGISTRY_NAMESPACE       注册中心命名空间"
    echo "  KENGER_REGISTRY_WEIGHT          服务权重"
    echo "  KENGER_REGISTRY_HEARTBEAT_INTERVAL  心跳间隔"
    echo "  CF_API_TOKEN                    Cloudflare API Token"
    echo "  CF_ACCOUNT_ID                   Cloudflare Account ID"
    echo "  CF_PAGES_PROJECT                Pages 项目名"
    echo "  FRONTEND_DEPLOY                 是否部署前端(true/false)"
    echo "  FRONTEND_DIR                    前端目录(默认 frontend)"
    echo "  FRONTEND_DOMAIN                 前端域名(默认 idea.156354.xyz)"
    echo "  BACKEND_DOMAIN                  后端域名(默认 ideabackend.156354.xyz)"
    echo "  TUNNEL_ID                       cloudflared tunnel id"
    echo "  CLOUDFLARED_CONFIG              cloudflared 配置路径"
    echo "  CLOUDFLARED_SERVICE             cloudflared systemd 服务名"
    echo ""
    echo "示例:"
    echo "  $0 deploy              # 一键部署前后端"
    echo "  FRONTEND_DEPLOY=false $0 backend   # 仅部署后端"
    echo "  $0 frontend            # 仅部署前端"
    echo "  $0 status              # 查看容器状态"
    echo "  $0 start 58081         # 快速启动（端口 58081）"
    echo "  $0 rollback            # 回滚到上一版本"
    echo "  $0 logs                # 查看日志"
    echo ""
}

# 命令处理
case "${1:-deploy}" in
    deploy)
        main
        ;;
    backend)
        FRONTEND_DEPLOY=false
        main
        ;;
    frontend)
        ensure_requirements
        deploy_frontend
        bind_frontend_domain
        verify_routes
        ;;
    rollback)
        rollback
        ;;
    start)
        quick_start "${2:-$PORT_A}"
        ;;
    stop)
        stop_all
        ;;
    status)
        show_containers
        ;;
    logs)
        show_logs "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "未知命令: $1"
        show_help
        exit 1
        ;;
esac

