"""不可由 JSON 配置放行的本机 SIM 身份门；每次写入重新取证。

Vendored 2026-10-23 from D:/STM/针尖修复实验室/源码/设备接口/安全身份.py.
No runtime bypass or hardware write mode is provided.
"""
from __future__ import annotations
import ipaddress
from pathlib import PureWindowsPath
import time

IDENTITY_KEYS = ("host_pid", "sim_pid", "host_created", "sim_created", "host_exe", "sim_exe", "port")


def loopback(ip):
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def verify_inventory(processes, connections, *, host="127.0.0.1", port=6501, expected=None, client_port=None):
    """Pure validation function, allowing genuine offline adversarial tests."""
    if host != "127.0.0.1" or port not in (6501, 6502, 6503):
        raise PermissionError("仅允许本机已核验 SIM 的 6501–6503 端口")
    sims = [p for p in processes.values() if p.get("name", "").lower() == "sim-engine.exe"
            and str(PureWindowsPath(p.get("exe", ""))).lower().endswith("\\rt-engine\\sim\\sim-engine.exe")]
    listeners = [c for c in connections if c["status"] == "LISTEN" and c["local_port"] == port]
    if len(sims) != 1 or len(listeners) != 1:
        raise PermissionError("必须唯一确认 SIM 进程和监听端口")
    sim = sims[0]
    owner = processes.get(listeners[0]["pid"], {})
    if owner.get("name", "").lower() != "nanonis mimea.exe":
        raise PermissionError("目标端口不属于 Nanonis Mimea")
    hp, sp = PureWindowsPath(owner.get("exe", "")), PureWindowsPath(sim["exe"])
    if str(hp.parent).lower() != str(sp.parents[2]).lower() or hp.name.lower() != "nanonis mimea.exe":
        raise PermissionError("主程序与 SIM 不属于同一安装目录")
    active = [c for c in connections if c["status"] == "ESTABLISHED" and c["pid"] in (owner["pid"], sim["pid"])]
    if any(not loopback(c["remote_ip"]) or not loopback(c["local_ip"]) for c in active):
        raise PermissionError("Nanonis/SIM 存在非回环连接，拒绝控制")
    pairs = []
    for c in active:
        if c["pid"] != owner["pid"]:
            continue
        for s in active:
            if (s["pid"] == sim["pid"] and s["local_ip"] == c["remote_ip"] and s["remote_ip"] == c["local_ip"]
                    and s["local_port"] == c["remote_port"] and s["remote_port"] == c["local_port"]):
                pairs.append(c)
    if len(pairs) < 3:
        raise PermissionError("未确认至少三条 Nanonis—SIM 双向本机连接")
    for c in active:
        if c["pid"] == owner["pid"] and c["local_port"] in (6501,6502,6503):
            if not (c["local_port"] == port and client_port is not None and c["remote_port"] == client_port):
                raise PermissionError("已有其他 PI 客户端，拒绝并发写入")
    identity = {"host_pid": owner["pid"], "sim_pid": sim["pid"], "host_created": owner["create_time"],
                "sim_created": sim["create_time"], "host_exe": str(hp), "sim_exe": str(sp), "port": port,
                "reciprocal_connections": len(pairs), "checked_at_unix": time.time()}
    if expected and any(identity[k] != expected[k] for k in IDENTITY_KEYS):
        raise PermissionError("已验证的进程身份发生变化")
    return identity


def fresh_sim_identity(host="127.0.0.1", port=6501, expected=None, client_port=None):
    import psutil
    processes = {}
    for p in psutil.process_iter(["pid", "name", "exe", "create_time"]):
        try:
            i = p.info
            if (i.get("name") or "").lower() in ("nanonis mimea.exe", "sim-engine.exe"):
                processes[p.pid] = i
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    connections = [{"pid": c.pid, "status": c.status, "local_ip": c.laddr.ip, "local_port": c.laddr.port,
                    "remote_ip": c.raddr.ip if c.raddr else "", "remote_port": c.raddr.port if c.raddr else 0}
                   for c in psutil.net_connections(kind="tcp")]
    return verify_inventory(processes, connections, host=host, port=port, expected=expected, client_port=client_port)
