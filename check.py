import json, os, re, sys, time
import requests
from bs4 import BeautifulSoup

LIST_URL = "https://www.ss.com/lv/transport/cars/bmw/3-series/"
BASE = "https://www.ss.com"
MAX_YEAR = 2004
SEEN_FILE = "seen.json"
TOPIC = os.environ["NTFY_TOPIC"]
HEADERS = {"User-Agent": "Mozilla/5.0 (personal new-listing alert)"}
AD_RE = re.compile(r"^/msg/lv/transport/cars/bmw/[^/]+/[a-z0-9]+\.html$")


def get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def ad_links():
    soup = BeautifulSoup(get(LIST_URL), "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].replace(BASE, "")
        if AD_RE.match(href) and href not in links:
            links.append(href)
    return links


def details(html):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    def last(pattern):
        found = re.findall(pattern, text)
        return found[-1].strip() if found else ""

    year = last(r"Izlaiduma gads:\s*(\d{4})")
    return {
        "year": int(year) if year else None,
        "engine": last(r"Motors:\s*(.*?)\s+(?:Ātrumkārba|Nobraukums|Krāsa|Virsbūves)"),
        "gearbox": last(r"Ātrumkārba:\s*(.*?)\s+(?:Nobraukums|Krāsa|Virsbūves)"),
        "mileage": last(r"Nobraukums, km:\s*([\d\s]*\d)"),
        "price": last(r"Cena:\s*(\d[\d\s]*€)"),
    }


def matches(d):
    return (
        d["year"] is not None
        and d["year"] <= MAX_YEAR
        and "benzīns" in d["engine"].lower()
        and "manuāl" in d["gearbox"].lower()
    )


def notify(title, message, url=None):
    payload = {"topic": TOPIC, "title": title, "message": message, "tags": ["car"]}
    if url:
        payload["click"] = url
    requests.post("https://ntfy.sh/", json=payload, timeout=30).raise_for_status()


def main():
    first_run = not os.path.exists(SEEN_FILE)
    seen = [] if first_run else json.load(open(SEEN_FILE))
    links = ad_links()
    if not links:
        sys.exit("No ads found on listing page")
    for href in [l for l in links if l not in seen]:
        if not first_run:
            url = BASE + href
            try:
                d = details(get(url))
                print(url, d)
            except Exception as e:
                print(f"skip {url}: {e}")
                continue
            if matches(d):
                try:
                    notify(
                        f"BMW 3 · {d['year']} · {d['price']}",
                        f"{d['engine']} · {d['gearbox']} · {d['mileage']} km",
                        url,
                    )
                except Exception as e:
                    print(f"notify failed {url}: {e}")
                    continue
                print(f"match {url}")
            time.sleep(2)
        seen.append(href)
    if first_run:
        notify("ss.lv watcher started", f"{len(links)} current BMW 3 ads indexed; alerts only for new ones")
    json.dump(seen[-500:], open(SEEN_FILE, "w"))


if __name__ == "__main__":
    main()
