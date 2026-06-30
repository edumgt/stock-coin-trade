import datetime


def _cpu_to_m(s) -> int:
    """CPU 문자열 → 밀리코어 정수 (n=나노코어, m=밀리코어, 정수=코어)"""
    s = str(s).strip()
    if s.endswith("n"):
        return int(s[:-1]) // 1_000_000
    if s.endswith("u"):
        return int(s[:-1]) // 1_000
    if s.endswith("m"):
        return int(s[:-1])
    return int(float(s) * 1000)


def _mem_to_mib(s) -> int:
    """메모리 문자열 → MiB 정수"""
    s = str(s).strip()
    if s.endswith("Ki"):
        return int(s[:-2]) // 1024
    if s.endswith("Mi"):
        return int(s[:-2])
    if s.endswith("Gi"):
        return int(float(s[:-2]) * 1024)
    if s.endswith("Ti"):
        return int(float(s[:-2]) * 1024 * 1024)
    if s.endswith("K") or s.endswith("k"):
        return int(s[:-1]) // 1000
    return int(s) // (1024 * 1024)


def build_overview() -> dict:
    from kubernetes import client, config
    config.load_incluster_config()

    v1 = client.CoreV1Api()
    custom = client.CustomObjectsApi()

    nodes_raw = v1.list_node().items

    try:
        nm_items = custom.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")["items"]
        node_metrics = {m["metadata"]["name"]: m["usage"] for m in nm_items}
    except Exception:
        node_metrics = {}

    pods_raw = v1.list_pod_for_all_namespaces().items

    pod_metrics = {}
    namespaces = list({p.metadata.namespace for p in pods_raw if p.metadata.namespace})
    for ns in namespaces:
        try:
            pm_items = custom.list_namespaced_custom_object("metrics.k8s.io", "v1beta1", ns, "pods")["items"]
            for pm in pm_items:
                name = pm["metadata"]["name"]
                total_cpu = sum(_cpu_to_m(c["usage"]["cpu"]) for c in pm["containers"])
                total_mem = sum(_mem_to_mib(c["usage"]["memory"]) for c in pm["containers"])
                pod_metrics[f"{ns}/{name}"] = {"cpu_m": total_cpu, "mem_mib": total_mem}
        except Exception:
            pass

    pods_by_node: dict[str, list] = {}
    for pod in pods_raw:
        node_name = pod.spec.node_name or "__unscheduled__"
        key = f"{pod.metadata.namespace}/{pod.metadata.name}"
        pm = pod_metrics.get(key, {})

        restarts = 0
        if pod.status.container_statuses:
            for cs in pod.status.container_statuses:
                restarts += cs.restart_count or 0

        images = []
        for c in (pod.spec.containers or []):
            img = c.image or ""
            images.append(img.split("/")[-1] if "/" in img else img)

        age_min = 0
        if pod.metadata.creation_timestamp:
            delta = datetime.datetime.now(datetime.timezone.utc) - pod.metadata.creation_timestamp
            age_min = int(delta.total_seconds() // 60)

        pod_info = {
            "name": pod.metadata.name,
            "namespace": pod.metadata.namespace,
            "status": pod.status.phase or "Unknown",
            "ip": pod.status.pod_ip or "",
            "node": node_name,
            "images": images,
            "cpu_m": pm.get("cpu_m", 0),
            "mem_mib": pm.get("mem_mib", 0),
            "restarts": restarts,
            "age_min": age_min,
        }
        pods_by_node.setdefault(node_name, []).append(pod_info)

    nodes = []
    total_cpu_cap = 0
    total_mem_cap = 0
    total_cpu_use = 0
    total_mem_use = 0

    for node in nodes_raw:
        n_name = node.metadata.name
        labels = node.metadata.labels or {}

        cap = node.status.capacity or {}
        cpu_cap = _cpu_to_m(cap.get("cpu", "0"))
        mem_cap = _mem_to_mib(cap.get("memory", "0"))

        nm = node_metrics.get(n_name, {})
        cpu_use = _cpu_to_m(nm.get("cpu", "0m"))
        mem_use = _mem_to_mib(nm.get("memory", "0Mi"))

        conditions = {c.type: c.status for c in (node.status.conditions or [])}

        nodes.append({
            "name": n_name,
            "short_name": n_name.split(".")[0],
            "status": "Ready" if conditions.get("Ready") == "True" else "NotReady",
            "instance_type": labels.get("node.kubernetes.io/instance-type", "unknown"),
            "os_image": (node.status.node_info.os_image if node.status.node_info else ""),
            "kernel": (node.status.node_info.kernel_version if node.status.node_info else ""),
            "cpu_cap_m": cpu_cap,
            "mem_cap_mib": mem_cap,
            "cpu_use_m": cpu_use,
            "mem_use_mib": mem_use,
            "cpu_pct": round(cpu_use / cpu_cap * 100, 1) if cpu_cap else 0,
            "mem_pct": round(mem_use / mem_cap * 100, 1) if mem_cap else 0,
            "pod_count": len(pods_by_node.get(n_name, [])),
            "pods": sorted(pods_by_node.get(n_name, []), key=lambda p: p["namespace"] + p["name"]),
        })

        total_cpu_cap += cpu_cap
        total_mem_cap += mem_cap
        total_cpu_use += cpu_use
        total_mem_use += mem_use

    return {
        "nodes": nodes,
        "cluster": {
            "total_nodes": len(nodes),
            "total_pods": sum(len(v) for v in pods_by_node.values()),
            "cpu_cap_m": total_cpu_cap,
            "mem_cap_mib": total_mem_cap,
            "cpu_use_m": total_cpu_use,
            "mem_use_mib": total_mem_use,
            "cpu_pct": round(total_cpu_use / total_cpu_cap * 100, 1) if total_cpu_cap else 0,
            "mem_pct": round(total_mem_use / total_mem_cap * 100, 1) if total_mem_cap else 0,
            "fetched_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    }
