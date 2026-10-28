import os
import sys
import json
import urllib.request
import urllib.error
import subprocess

REPO_NAME = "Intelligent-Lighting-and-Outdoor-LED-Display-Monitoring-and-Control"
DESCRIPTION = "AI and ML enabled IoT and cloud platform for outdoor lighting and LED display operations (PCCOM CO., LTD)"

def create_github_repo(token, is_private=False):
    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Antigravity-Git-Agent"
    }
    payload = {
        "name": REPO_NAME,
        "description": DESCRIPTION,
        "private": is_private,
        "auto_init": False
    }
    
    print(f"[*] Dang tao repository '{REPO_NAME}' tren GitHub...")
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            html_url = data.get("html_url")
            clone_url = data.get("clone_url")
            print(f"[SUCCESS] Repo da duoc tao thanh cong: {html_url}")
            return clone_url
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8")
        if "name already exists" in err:
            print(f"[NOTE] Repo '{REPO_NAME}' da ton tai tren GitHub. Dang lay link ket noi...")
            return f"https://github.com/Trng-Ngyn/{REPO_NAME}.git"
        print(f"[ERROR] HTTP {e.code}: {err}")
        return None
    except Exception as e:
        print(f"[ERROR] Khong the ket noi GitHub API: {e}")
        return None

def push_local_to_remote(clone_url, token=None):
    proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print(f"[*] Dang day ma nguon tu thu muc {proj_dir} len GitHub...")
    
    # Configure push URL with token if provided
    push_url = clone_url
    if token and "https://" in clone_url:
        push_url = clone_url.replace("https://", f"https://oauth2:{token}@")
        
    cmds = [
        ["git", "branch", "-M", "main"],
        ["git", "remote", "remove", "origin"],
        ["git", "remote", "add", "origin", push_url],
        ["git", "push", "-u", "origin", "main"]
    ]
    
    for cmd in cmds:
        res = subprocess.run(cmd, cwd=proj_dir, capture_output=True, text=True)
        # remove origin might fail if not exist, ignore
        if cmd[1] == "remove":
            continue
        if res.returncode != 0 and "fatal: remote origin already exists" not in res.stderr:
            print(f"[WARN] Command {' '.join(cmd)}: {res.stderr.strip()}")
            
    print(f"[DONE] Kiem tra lai tren GitHub: {clone_url}")

if __name__ == "__main__":
    print("="*60)
    print("   GITHUB REPOSITORY CREATOR & PUSHER")
    print(f"   Target Repo: {REPO_NAME}")
    print("="*60)
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        token = input("Nhap GitHub Personal Access Token (PAT) cua ban (can quyen 'repo'): ").strip()
        
    if not token:
        print("[!] Khong co token. Ban co the tao thu cong repo tren https://github.com/new voi ten:")
        print(f"    {REPO_NAME}")
        print("\nSau do chay cac lenh sau:")
        print(f"    git remote add origin https://github.com/Trng-Ngyn/{REPO_NAME}.git")
        print("    git branch -M main")
        print("    git push -u origin main")
    else:
        clone_url = create_github_repo(token)
        if clone_url:
            push_local_to_remote(clone_url, token)

