import requests

def fetch_user_data(user_ids=[]):
    results = {}
    for id in user_ids:
        try:
            r = requests.get("https://api.example.com/users/" + str(id))
            data = r.json()
            results[id] = data
        except:
            pass
    return results

def process(user_ids=[]):
    d = fetch_user_data(user_ids)
    out = []
    for k in d:
        if d[k]["status"] == 1:
            out.append(d[k]["name"].upper())
        elif d[k]["status"] == 2:
            out.append(d[k]["name"].lower())
    return out
