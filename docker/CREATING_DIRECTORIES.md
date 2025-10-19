# Creating per-user workspaces and a global shared directory

This guide shows how to set up:
- Per-user workspace directories at `/home/<USER>/isaaclab_ws` that the user can read/write locally and inside rootless Docker containers.
- A global shared directory at `/srv/isaaclab/shared` where:
  - Everyone can read files.
  - Only the file creator can modify/delete their own files.
  - Creation works from both the host and rootless containers.

The commands are idempotent and safe to re-run.

## Prerequisites
- Linux host with sudo access.
- Rootless Docker users (containers typically run as the host user UID, with unpredictable supplementary groups).
- ACL tools installed (for `getfacl`/`setfacl`).

Install ACL tools (Debian/Ubuntu example):
```bash
sudo apt-get update
sudo apt-get install -y acl
```

## 1) Per-user workspaces at /home/\<USER\>/isaaclab_ws
Goal: each user owns their workspace, with private access by default. Rootless containers will also be able to access it because containers run as that same host user.

- Ownership: `<USER>:<USER>`
- Permissions: `0700` (private). Optionally loosen to `0755` or `0770` for collaboration.

Create/fix for a list of users (adjust the array as needed):
```bash
users=(alice bob)
for u in "${users[@]}"; do
  sudo mkdir -p "/home/$u/isaaclab_ws"
  sudo chown -R "$u:$u" "/home/$u/isaaclab_ws"
  sudo chmod 700 "/home/$u/isaaclab_ws"
  # Optional collaborative modes:
  # sudo chmod 755 "/home/$u/isaaclab_ws"   # world-readable
  # sudo chmod 770 "/home/$u/isaaclab_ws"   # group-collab (requires a shared group)
done
```

Verify:
```bash
for u in "${users[@]}"; do
  sudo ls -ld "/home/$u/isaaclab_ws"
done
```
You should see each directory owned by the user with permissions like `drwx------` (0700).

## 2) Global shared directory at /srv/isaaclab/shared
Goal: any user (and their rootless containers) can create files, everyone can read files, and only the file owner can modify/delete their own files.

We achieve this by:
- Using a sticky, world-writable top-level directory so everyone can create entries, but only the owner (or root) can delete/rename their own files.
- Enforcing defaults so new files are owner-writable and world-readable (0644) and new directories are traversable (0755).
- Ensuring parent directories are traversable by all.

Optional group: if you’d like a tracking group for the share (not strictly required for the policy), create it and add users. This does not need to be present inside containers.
```bash
# Create group if it doesn’t exist
if ! getent group isaaclab_share >/dev/null; then
  sudo groupadd isaaclab_share
fi

# Add users (repeat or loop as needed)
for u in "${users[@]}"; do
  sudo usermod -aG isaaclab_share "$u"
done
```

Create/fix the directory tree and set permissions/ACLs:
```bash
# Ensure parent path exists and is traversable by all
sudo mkdir -p /srv/isaaclab/shared
sudo chmod 755 /srv /srv/isaaclab

# Top-level shared dir: sticky + world-writable (creation allowed from host/containers)
# Keep SGID to preserve group ownership if you use the group.
sudo chown root:isaaclab_share /srv/isaaclab/shared || true
sudo chmod 3777 /srv/isaaclab/shared   # drwxrwsrwt

# Clear any existing ACLs and set defaults so new items are readable by all
sudo setfacl -bk /srv/isaaclab/shared
sudo setfacl -d -m u::rwx,g::r-x,o::r-x /srv/isaaclab/shared

# Normalize existing content (optional but recommended):
# - Files: 0644 (rw-r--r--)
# - Dirs:  0755 (rwxr-xr-x)
sudo find /srv/isaaclab/shared -type f -exec chmod u=rw,go=r {} +
sudo find /srv/isaaclab/shared -type d -exec chmod u=rwx,go=rx {} +
```

Verify:
```bash
# Mode bits and ownership
stat -c "%A %a %U:%G %n" /srv /srv/isaaclab /srv/isaaclab/shared

# ACLs
getfacl -p /srv/isaaclab/shared
```
Expected:
- `/srv/isaaclab/shared` shows `drwxrwsrwt` (3777) with owner `root:isaaclab_share` (group may differ if you skipped the group step).
- Default ACLs include `default:user::rwx`, `default:group::r-x`, and `default:other::r-x`.

### Why this works with rootless Docker
- Rootless containers run as the invoking host user UID, but often without the host’s supplementary groups. Relying on group write alone can fail inside containers.
- Setting the top-level directory to world-writable with the sticky bit (1777/3777) allows file creation without group membership while preventing users from deleting each other’s files.
- Default ACLs and normalized modes ensure that new files are readable by everyone (0644) and only owner-writable; directories are 0755 so others can traverse.

Note on umask: processes with an unusually restrictive umask (e.g., 077) can still create files without group/other read bits. You can:
- Encourage a standard umask of 0022 in container entrypoints.
- Periodically normalize permissions (e.g., with a cron job) if strict consistency is required.

## 3) Quick tests
Assume two users, `alice` and `bob`.

Host tests:
```bash
# As alice
sudo -u alice bash -lc 'echo host_hi > /srv/isaaclab/shared/hello_from_alice.txt; ls -l /srv/isaaclab/shared/hello_from_alice.txt; cat /srv/isaaclab/shared/hello_from_alice.txt'

# As bob (read should succeed; write should fail)
sudo -u bob bash -lc 'cat /srv/isaaclab/shared/hello_from_alice.txt; echo nope >> /srv/isaaclab/shared/hello_from_alice.txt || echo "expected: Permission denied"'
```

Container tests (once Docker is running):
```bash
# As alice, run a rootless container and create a file
sudo -u alice bash -lc 'docker run --rm -v /srv/isaaclab/shared:/root/shared:rw alpine sh -lc "echo from_container > /root/shared/inside.txt && ls -l /root/shared/inside.txt && cat /root/shared/inside.txt"'

# As bob, verify read, but writing to alice’s file should fail
sudo -u bob bash -lc 'docker run --rm -v /srv/isaaclab/shared:/root/shared:rw alpine sh -lc "cat /root/shared/hello_from_alice.txt && (echo nope >> /root/shared/hello_from_alice.txt || echo \"expected: Permission denied\")"'
```

## 4) Troubleshooting
- “Permission denied” on create inside container:
  - Check the shared dir mode: `stat -c "%A %a %n" /srv/isaaclab/shared` should be `drwxrwsrwt` and `3777`.
  - Check parent directories are `0755`: `stat -c "%A %a %n" /srv /srv/isaaclab`.
  - Ensure the bind mount path is correct and not read-only: `-v /srv/isaaclab/shared:/root/shared:rw`.
- Others cannot read files created in container:
  - Confirm umask inside the container: `umask` (expect 0022). If it’s `0077`, files will be private. Adjust container umask or run a periodic permission normalization.
- Group membership not visible in container:
  - Expected with rootless containers; do not rely on group write for create/modify. The 1777 sticky shared dir avoids the need for shared groups inside containers.

---

With the steps above, users have private per-user workspaces and a functional global share that supports read-for-all and owner-only writes, both on the host and from rootless containers.