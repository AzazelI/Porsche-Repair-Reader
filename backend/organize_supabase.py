import os
import requests
import json

def organize_bucket():
    report = {
        "status": "success",
        "files_found": 0,
        "files_skipped": [],
        "files_deleted": [],
        "files_moved_cache": [],
        "files_moved_manuals": [],
        "errors": []
    }
    
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").replace("\n", "").replace("\r", "").strip()
    
    if not supabase_url or not supabase_key:
        report["status"] = "error"
        report["errors"].append("Supabase credentials not found in environment variables.")
        return report
        
    bucket_name = "repair-manuals"
    headers = {
        "Authorization": f"Bearer {supabase_key}",
        "apikey": supabase_key,
        "Content-Type": "application/json"
    }
    
    list_url = f"{supabase_url.rstrip('/')}/storage/v1/object/list/{bucket_name}"
    payload = {
        "prefix": "",
        "limit": 100,
        "offset": 0,
        "sortBy": {"column": "name", "order": "asc"}
    }
    
    try:
        response = requests.post(list_url, json=payload, headers=headers)
        if response.status_code != 200:
            report["status"] = "error"
            report["errors"].append(f"Failed to list bucket files: {response.status_code} - {response.text}")
            return report
            
        files = response.json()
        report["files_found"] = len(files)
        
        move_url = f"{supabase_url.rstrip('/')}/storage/v1/object/move"
        delete_url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket_name}"
        
        for f in files:
            name = f.get("name", "")
            if not name:
                continue
                
            if "/" in name:
                report["files_skipped"].append(name)
                continue
                
            if name == "test_connection.txt":
                del_payload = {"prefixes": [name]}
                del_resp = requests.delete(delete_url, json=del_payload, headers=headers)
                if del_resp.status_code == 200:
                    report["files_deleted"].append(name)
                else:
                    report["errors"].append(f"Failed to delete {name}: status {del_resp.status_code}")
                continue
                
            if name.startswith("cache_") and name.endswith(".json"):
                dest = f"cache/{name}"
                move_payload = {
                    "bucketId": bucket_name,
                    "sourceKey": name,
                    "destinationKey": dest
                }
                move_resp = requests.post(move_url, json=move_payload, headers=headers)
                if move_resp.status_code == 200:
                    report["files_moved_cache"].append(f"{name} -> {dest}")
                else:
                    report["errors"].append(f"Failed to move cache file {name}: status {move_resp.status_code} - {move_resp.text}")
                continue
                
            if name.endswith(".pdf"):
                dest = f"manuals/{name}"
                move_payload = {
                    "bucketId": bucket_name,
                    "sourceKey": name,
                    "destinationKey": dest
                }
                move_resp = requests.post(move_url, json=move_payload, headers=headers)
                if move_resp.status_code == 200:
                    report["files_moved_manuals"].append(f"{name} -> {dest}")
                else:
                    report["errors"].append(f"Failed to move PDF manual {name}: status {move_resp.status_code} - {move_resp.text}")
                continue
                
    except Exception as e:
        report["status"] = "error"
        report["errors"].append(f"Exception during organization: {str(e)}")
        
    return report

if __name__ == "__main__":
    rep = organize_bucket()
    print(json.dumps(rep, indent=2))
