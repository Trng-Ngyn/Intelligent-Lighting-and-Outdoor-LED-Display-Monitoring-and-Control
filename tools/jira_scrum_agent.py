import os
import sys
import json
import base64
import urllib.request
import urllib.error

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "jira_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"[OK] Da luu cau hinh Jira vao: {CONFIG_FILE}")

class JiraClient:
    def __init__(self, domain, email, api_token, project_key="SCRUM"):
        # Format domain
        domain = domain.strip().rstrip("/")
        if not domain.startswith("http"):
            domain = f"https://{domain}.atlassian.net"
        self.domain = domain
        self.email = email.strip()
        self.api_token = api_token.strip()
        self.project_key = project_key.strip()
        
        auth_str = f"{self.email}:{self.api_token}"
        self.auth_header = "Basic " + base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

    def _request(self, endpoint, method="GET", data=None):
        url = f"{self.domain}{endpoint}"
        headers = {
            "Authorization": self.auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        req_data = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status in (200, 201):
                    return json.loads(resp.read().decode("utf-8"))
                return {"status": resp.status}
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"[ERROR] HTTP {e.code} tai {url}: {err_body}")
            return None
        except Exception as e:
            print(f"[ERROR] Request failed: {e}")
            return None

    def test_connection(self):
        print(f"[*] Dang ket noi voi Jira tai: {self.domain}...")
        res = self._request("/rest/api/3/myself")
        if res and "displayName" in res:
            print(f"[SUCCESS] Ket noi thanh cong! Xin chao {res.get('displayName')} ({res.get('emailAddress')})")
            return True
        return False

    def get_project_info(self):
        print(f"[*] Kiem tra project {self.project_key}...")
        res = self._request(f"/rest/api/3/project/{self.project_key}")
        if res:
            print(f"[PROJECT] Ten du an: {res.get('name')} | Key: {res.get('key')}")
            return res
        return None

    def get_issues(self):
        jql = f"project = {self.project_key} ORDER BY created DESC"
        endpoint = f"/rest/api/3/search?jql={urllib.parse.quote(jql)}&maxResults=50"
        res = self._request(endpoint)
        if res and "issues" in res:
            print(f"\n--- DANH SACH TASKS DANG CO TREN JIRA ({len(res['issues'])} items) ---")
            for issue in res["issues"]:
                key = issue.get("key")
                summary = issue.get("fields", {}).get("summary")
                status = issue.get("fields", {}).get("status", {}).get("name")
                print(f"  [{key}] {summary} -> Trạng thái: {status}")
            return res["issues"]
        return []

    def create_task(self, summary, description="", issue_type="Task"):
        data = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description or summary}]
                        }
                    ]
                },
                "issuetype": {"name": issue_type}
            }
        }
        res = self._request("/rest/api/3/issue", method="POST", data=data)
        if res and "key" in res:
            print(f"[CREATED] Tao thanh cong task: {res['key']} - {summary}")
            return res["key"]
        return None

    def seed_rfp_sprint_backlog(self):
        print("\n[*] Dang dong bo Backlog chuan tu RFP 16 tuan vao Jira...")
        epics = [
            ("Package A: Lighting Operations", "Quan ly chieu sang, ban do GIS, lich trinh thien van va che do du phong cuc bo"),
            ("Package B: LED Display Operations", "Quan ly man hinh LED, thu vien noi dung, duyet da tang va phan phoi bao mat"),
            ("Package C: Common Platform & IoT", "Ha tang IoT edge/cloud, MQTT 5, phan quyen RBAC, giam sat va bao mat ASVS"),
            ("Package D: Intelligence & AI/ML", "Dieu khien chieu sang thich ung (AI 01), phat hien bat thuong (AI 02), phan tich nang luong (AI 03)"),
        ]
        
        sprint_1_tasks = [
            ("Sprint 1 (Week 1-2): Nghiem thu Khao sat & Khoi tao Pipeline du an (Gate G0)", "Lead: PO, TL, IoT - Kiem tra inventory va CI/CD"),
            ("Sprint 1 (Week 1-2): Bench test bo dieu khien den & Giao tiep DALI/MQTT", "Lead: IoT, BE - Thu nghiem lenh dieu khien an toan dau tien"),
            ("Sprint 1 (Week 1-2): Thu nghiem phat danh sach noi dung luu dem man hinh LED (Offline Fallback)", "Lead: BE, QA - Kiem tra phat noi dung khi mat cloud"),
            ("Sprint 1 (Week 1-2): Bao cao tien do Tuan 02 va Chuan bi ho so moc G0", "Lead: PO (Trọng) - Chot voi PCCOM CO., LTD"),
        ]
        
        for summary, desc in sprint_1_tasks:
            self.create_task(summary, desc)
        print("[SUCCESS] Hoan tat dong bo cac task co ban vao Jira!")

if __name__ == "__main__":
    print("="*60)
    print("   JIRA SCRUM AGENT - INTELLIGENT LIGHTING & LED DISPLAY")
    print("="*60)
    
    cfg = load_config()
    domain = cfg.get("domain") or input("Nhap Jira Domain (vi du: your-company.atlassian.net): ").strip()
    email = cfg.get("email") or input("Nhap Email tai khoan Jira Atlassian: ").strip()
    token = cfg.get("api_token") or input("Nhap Jira API Token: ").strip()
    proj = cfg.get("project_key") or "SCRUM"
    
    if not cfg:
        save_config({"domain": domain, "email": email, "api_token": token, "project_key": proj})
        
    client = JiraClient(domain, email, token, proj)
    if client.test_connection():
        client.get_project_info()
        client.get_issues()
        choice = input("\nBan co muon tu dong import Backlog & Sprint Tasks tu file du an vao Jira? (y/n): ")
        if choice.lower() == 'y':
            client.seed_rfp_sprint_backlog()
            client.get_issues()

