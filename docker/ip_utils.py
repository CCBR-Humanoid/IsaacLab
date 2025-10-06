import subprocess
import json

def tailscale_ips(dev="tailscale0"):
    out = subprocess.check_output(["ip", "-j", "addr", "show", "dev", dev], text=True)
    data = json.loads(out)
    if not data:
        return {"ipv4": [], "ipv6": []}
    v4, v6 = [], []
    for a in data[0].get("addr_info", []):
        fam = a.get("family")
        addr = a.get("local")
        scope = a.get("scope")
        if fam == "inet" and addr:
            v4.append(addr)
        elif fam == "inet6" and addr and scope == "global":
            v6.append(addr)
    return {"ipv4": v4, "ipv6": v6}